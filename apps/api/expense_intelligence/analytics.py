import hashlib
import json
import statistics
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .database import get_db
from .models import (AnalyticsPreference, Category, ExpenseAllocation, ExpenseComponent, GroupMember,
                     InsightRecord, RecurringDecision, SharedExpense, Transaction,
                     TransactionAllocation, TransactionDirection, TransactionType)

router = APIRouter(prefix="/v1", tags=["analytics"])
ALGORITHM_VERSION = "rules-v1"


class InsightUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(active|dismissed)$")
    feedback: str | None = Field(None, pattern="^(helpful|unhelpful)$")


class PreferenceUpdate(BaseModel):
    sensitivity: str = Field(pattern="^(low|balanced|high)$")


class RecurringUpdate(BaseModel):
    status: str = Field(pattern="^(confirmed|rejected|suggested)$")
    label: str | None = Field(None, max_length=160)


def _key(transaction: Transaction) -> str:
    return (transaction.normalized_description or transaction.description).strip().lower()


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _insight(kind: str, currency: str, title: str, explanation: str, ids: list[uuid.UUID],
             start: date, end: date, severity: str = "info", **evidence) -> dict:
    identity = f"{kind}|{currency}|{','.join(sorted(map(str, ids)))}"
    return {"fingerprint": hashlib.sha256(identity.encode()).hexdigest(), "insight_type": kind,
            "currency": currency, "period_start": start, "period_end": end, "title": title,
            "explanation": explanation, "severity": severity,
            "evidence": {"transaction_ids": [str(item) for item in ids], **evidence}}


def _detect(rows: list[Transaction], start: date, end: date, sensitivity: str) -> tuple[list[dict], dict, list[dict]]:
    purchases = [r for r in rows if r.transaction_type == TransactionType.purchase and r.direction == TransactionDirection.expense]
    current = [r for r in purchases if start <= r.effective_date <= end]
    by_currency: dict[str, list[Transaction]] = defaultdict(list)
    for row in purchases:
        by_currency[row.original_currency].append(row)
    insights: list[dict] = []
    recurring: list[dict] = []
    enough = {"unusual_amount": False, "recurring": False, "duplicate": bool(current)}
    multiplier = {"low": Decimal("5"), "balanced": Decimal("3"), "high": Decimal("2")}[sensitivity]

    for currency, items in by_currency.items():
        history = [r for r in items if r.effective_date < start]
        if len(history) >= 6:
            enough["unusual_amount"] = True
            values = [r.original_amount for r in history]
            median = Decimal(str(statistics.median(values)))
            mad = Decimal(str(statistics.median([abs(v - median) for v in values])))
            threshold = median + max(multiplier * mad, median)
            for row in current:
                if row.original_currency == currency and row.original_amount > threshold:
                    insights.append(_insight("unusual_amount", currency, f"Unusually large {row.description}",
                        f"{_money(row.original_amount)} is above the {_money(threshold)} robust historical threshold.",
                        [row.id], start, end, "warning", amount=_money(row.original_amount), threshold=_money(threshold), method="median + robust deviation"))

        series: dict[str, list[Transaction]] = defaultdict(list)
        for row in items:
            series[_key(row)].append(row)
        for merchant, occurrences in series.items():
            occurrences.sort(key=lambda row: row.effective_date)
            if len(occurrences) < 3:
                continue
            gaps = [(b.effective_date - a.effective_date).days for a, b in zip(occurrences, occurrences[1:])]
            typical_gap = statistics.median(gaps)
            amounts = [r.original_amount for r in occurrences]
            middle = Decimal(str(statistics.median(amounts)))
            stable = middle > 0 and max(abs(amount - middle) / middle for amount in amounts) <= Decimal("0.20")
            frequency = "monthly" if 25 <= typical_gap <= 35 else "weekly" if 6 <= typical_gap <= 8 else None
            if frequency and stable:
                enough["recurring"] = True
                series_key = hashlib.sha256(f"{currency}|{merchant}".encode()).hexdigest()
                recurring.append({"series_key": series_key, "merchant": merchant.title(), "currency": currency,
                    "frequency": frequency, "typical_amount": _money(middle), "occurrences": len(occurrences),
                    "transaction_ids": [str(r.id) for r in occurrences]})

    seen: dict[tuple, Transaction] = {}
    for row in sorted(current, key=lambda item: item.effective_date):
        identity = (row.original_currency, row.original_amount, _key(row))
        previous = seen.get(identity)
        if previous and (row.effective_date - previous.effective_date).days <= 1:
            insights.append(_insight("possible_duplicate", row.original_currency, f"Possible duplicate: {row.description}",
                "Same merchant and amount appeared within one day. Review before deleting either entry.",
                [previous.id, row.id], start, end, "warning", amount=_money(row.original_amount), method="exact amount + merchant within 1 day"))
        seen[identity] = row
    return insights, enough, recurring


def _persist(session: Session, user_id: uuid.UUID, candidates: list[dict]) -> list[InsightRecord]:
    fingerprints = {candidate["fingerprint"] for candidate in candidates}
    existing = {row.fingerprint: row for row in session.scalars(select(InsightRecord).where(InsightRecord.owner_user_id == user_id)).all()}
    for row in existing.values():
        if row.status == "active" and row.fingerprint not in fingerprints:
            row.status = "expired"
    for candidate in candidates:
        fingerprint = candidate["fingerprint"]
        row = existing.get(fingerprint)
        values = {**candidate, "evidence_json": json.dumps(candidate["evidence"]), "updated_at": datetime.now(timezone.utc)}
        values.pop("evidence", None)
        values.pop("fingerprint", None)
        if row:
            for key, value in values.items(): setattr(row, key, value)
        else:
            row = InsightRecord(owner_user_id=user_id, fingerprint=fingerprint, **values)
            session.add(row)
    session.commit()
    return list(session.scalars(select(InsightRecord).where(InsightRecord.owner_user_id == user_id, InsightRecord.status != "expired").order_by(InsightRecord.period_end.desc())).all())


def _serialize(row: InsightRecord) -> dict:
    return {"id": str(row.id), "type": row.insight_type, "currency": row.currency, "title": row.title,
            "explanation": row.explanation, "severity": row.severity, "status": row.status,
            "feedback": row.feedback, "evidence": json.loads(row.evidence_json),
            "period_start": row.period_start.isoformat(), "period_end": row.period_end.isoformat(),
            "algorithm_version": row.algorithm_version}


@router.get("/analytics/overview")
def overview(start: date, end: date, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if start > end or (end - start).days > 366:
        raise HTTPException(422, "Date range must be ordered and no longer than 366 days")
    member_ids = list(session.scalars(select(GroupMember.id).where(GroupMember.linked_user_id == user.id)).all())
    linked_transaction_ids = set(session.scalars(select(SharedExpense.linked_transaction_id).join(ExpenseAllocation, ExpenseAllocation.expense_id == SharedExpense.id).where(ExpenseAllocation.member_id.in_(member_ids), SharedExpense.state == "confirmed", SharedExpense.linked_transaction_id.is_not(None))).all()) if member_ids else set()
    rows = list(session.scalars(select(Transaction).where(Transaction.owner_user_id == user.id, Transaction.effective_date <= end, ~Transaction.id.in_(linked_transaction_ids)).order_by(Transaction.effective_date)).all())
    preference = session.get(AnalyticsPreference, user.id) or AnalyticsPreference(user_id=user.id)
    if not session.get(AnalyticsPreference, user.id): session.add(preference); session.commit()
    candidates, history, recurring = _detect(rows, start, end, preference.sensitivity)
    insights = _persist(session, user.id, candidates)
    decisions = {row.series_key: row for row in session.scalars(select(RecurringDecision).where(RecurringDecision.owner_user_id == user.id)).all()}
    for item in recurring:
        decision = decisions.get(item["series_key"])
        item.update(status=decision.status if decision else "suggested", label=decision.label if decision else None)

    period = [r for r in rows if start <= r.effective_date <= end]
    allocations = list(session.scalars(select(TransactionAllocation).where(TransactionAllocation.owner_user_id == user.id, TransactionAllocation.current.is_(True))).all())
    by_transaction: dict[uuid.UUID, list[TransactionAllocation]] = defaultdict(list)
    for allocation in allocations: by_transaction[allocation.transaction_id].append(allocation)
    categories = {row.id: row for row in session.scalars(select(Category)).all()}
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"spend": Decimal(0), "income": Decimal(0), "refunds": Decimal(0)})
    category_totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    monthly: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    merchants: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    unclassified: dict[str, Decimal] = defaultdict(Decimal)
    for row in period:
        amount = row.original_amount
        if row.transaction_type == TransactionType.purchase and row.direction == TransactionDirection.expense:
            totals[row.original_currency]["spend"] += amount
            monthly[(row.original_currency, row.effective_date.strftime("%Y-%m"))] += amount
            merchants[(row.original_currency, _key(row).title())] += amount
            current_allocations = by_transaction.get(row.id, [])
            if current_allocations:
                for allocation in current_allocations:
                    category_totals[(row.original_currency, categories.get(allocation.category_id).name if categories.get(allocation.category_id) else "Other")] += allocation.amount
            else:
                category_totals[(row.original_currency, row.category)] += amount
            if row.needs_review or (not row.category_id and row.category == "Other"):
                unclassified[row.original_currency] += amount
        elif row.transaction_type == TransactionType.refund:
            totals[row.original_currency]["spend"] -= amount
            totals[row.original_currency]["refunds"] += amount
        elif row.transaction_type == TransactionType.income and row.direction == TransactionDirection.income:
            totals[row.original_currency]["income"] += amount

    shared: dict[str, Decimal] = defaultdict(Decimal)
    if member_ids:
        shared_rows = session.execute(select(ExpenseAllocation.amount, SharedExpense.currency, SharedExpense.expense_date, SharedExpense.description, ExpenseComponent.category_id, SharedExpense.category_id).join(SharedExpense, SharedExpense.id == ExpenseAllocation.expense_id).join(ExpenseComponent, ExpenseComponent.id == ExpenseAllocation.component_id).where(ExpenseAllocation.member_id.in_(member_ids), SharedExpense.state == "confirmed", SharedExpense.expense_date.between(start, end))).all()
        for amount, currency, expense_date, description, component_category_id, expense_category_id in shared_rows:
            shared[currency] += amount
            totals[currency]["spend"] += amount
            monthly[(currency, expense_date.strftime("%Y-%m"))] += amount
            merchants[(currency, description)] += amount
            category_id = component_category_id or expense_category_id
            category_totals[(currency, categories.get(category_id).name if categories.get(category_id) else "Other")] += amount
            if category_id is None:
                unclassified[currency] += amount

    return {"period": {"start": start, "end": end}, "sensitivity": preference.sensitivity,
        "fx_policy": "Currencies are never combined. No implicit conversion is performed.",
        "totals": [{"currency": c, **{k: _money(v) for k, v in values.items()}, "net": _money(values["income"] - values["spend"]), "unclassified": _money(unclassified[c]), "shared_consumption": _money(shared[c])} for c, values in sorted(totals.items())],
        "time_series": [{"currency": c, "period": p, "spend": _money(v)} for (c, p), v in sorted(monthly.items())],
        "categories": [{"currency": c, "name": n, "spend": _money(v)} for (c, n), v in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)],
        "merchants": [{"currency": c, "name": n, "spend": _money(v)} for (c, n), v in sorted(merchants.items(), key=lambda item: item[1], reverse=True)[:12]],
        "history": history, "insights": [_serialize(row) for row in insights if row.status == "active"], "recurring": [r for r in recurring if r["status"] != "rejected"]}


@router.get("/insights")
def list_insights(include_dismissed: bool = False, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    query = select(InsightRecord).where(InsightRecord.owner_user_id == user.id, InsightRecord.status != "expired")
    if not include_dismissed: query = query.where(InsightRecord.status == "active")
    return [_serialize(row) for row in session.scalars(query.order_by(InsightRecord.period_end.desc())).all()]


@router.put("/insights/{insight_id}")
def update_insight(insight_id: uuid.UUID, payload: InsightUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.scalar(select(InsightRecord).where(InsightRecord.id == insight_id, InsightRecord.owner_user_id == user.id))
    if not row: raise HTTPException(404, "Insight not found")
    if payload.status is not None: row.status = payload.status
    if payload.feedback is not None: row.feedback = payload.feedback
    row.updated_at = datetime.now(timezone.utc); session.commit(); session.refresh(row)
    return _serialize(row)


@router.get("/analytics/preferences")
def get_preferences(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(AnalyticsPreference, user.id)
    return {"sensitivity": row.sensitivity if row else "balanced"}


@router.put("/analytics/preferences")
def update_preferences(payload: PreferenceUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.get(AnalyticsPreference, user.id) or AnalyticsPreference(user_id=user.id)
    row.sensitivity = payload.sensitivity; session.add(row); session.commit()
    return {"sensitivity": row.sensitivity}


@router.put("/analytics/recurring/{series_key}")
def update_recurring(series_key: str, payload: RecurringUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if len(series_key) != 64: raise HTTPException(422, "Invalid series key")
    row = session.scalar(select(RecurringDecision).where(RecurringDecision.owner_user_id == user.id, RecurringDecision.series_key == series_key))
    if not row: row = RecurringDecision(owner_user_id=user.id, series_key=series_key)
    row.status = payload.status; row.label = payload.label; row.updated_at = datetime.now(timezone.utc)
    session.add(row); session.commit()
    return {"series_key": series_key, "status": row.status, "label": row.label}
