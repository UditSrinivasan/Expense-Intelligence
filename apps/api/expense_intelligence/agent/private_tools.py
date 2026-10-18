"""Authenticated real-ledger tools. Deliberately not registered with Gemini yet."""

import uuid
from datetime import date
from decimal import Decimal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..budgets import evaluate_budget
from ..classification import category_spend
from ..group_finance import calculate_balances
from ..models import (Budget, BudgetStatus, ExpenseGroup, FxRate, GroupMember,
                      ImportBatch, InsightRecord, Merchant, RecurringDecision, Settlement)
from ..services import list_transactions


class PeriodInput(BaseModel):
    start: date
    end: date
    currency: str = Field(pattern="^(INR|GBP|USD|EUR)$")


class SearchInput(BaseModel):
    query: str = Field(default="", max_length=120)
    limit: int = Field(default=20, ge=1, le=50)


class ConversionInput(BaseModel):
    amount: Decimal = Field(gt=0)
    base: str = Field(pattern="^(INR|GBP|USD|EUR)$")
    quote: str = Field(pattern="^(INR|GBP|USD|EUR)$")
    on: date


def build_private_finance_tools(session: Session, owner_id: uuid.UUID) -> list[StructuredTool]:
    """Build read-only tools closed over one authenticated owner.

    This registry is tested for future private processing, but runtime.py intentionally
    exposes only the immutable synthetic registry to Gemini.
    """

    def transactions(query: str = "", limit: int = 20) -> dict:
        needle = query.casefold().strip()
        rows = [row for row in list_transactions(session, owner_id, 100) if not needle or needle in row.description.casefold()][:limit]
        return {"data_mode": "real_private_local", "transactions": [{"id": str(row.id), "date": row.effective_date.isoformat(), "description": row.description, "amount": str(row.original_amount), "currency": row.original_currency, "type": row.transaction_type.value} for row in rows]}

    def spending(start: date, end: date, currency: str) -> dict:
        if start > end: raise ValueError("Start date must not be after end date")
        rows = category_spend(session, owner_id, currency, start, end)
        return {"data_mode": "real_private_local", "currency": currency, "categories": [{"category": row.category_name, "amount": str(row.amount), "transaction_count": row.transaction_count} for row in rows]}

    def merchants() -> dict:
        rows = session.scalars(select(Merchant).where(Merchant.owner_user_id == owner_id).order_by(Merchant.display_name).limit(100)).all()
        return {"data_mode": "real_private_local", "merchants": [{"id": str(row.id), "name": row.display_name, "status": row.status} for row in rows]}

    def budgets() -> dict:
        rows = session.scalars(select(Budget).where(Budget.owner_user_id == owner_id, Budget.status == BudgetStatus.active, Budget.deleted_at.is_(None))).all()
        values = [evaluate_budget(session, owner_id, row) for row in rows]
        return {"data_mode": "real_private_local", "budgets": [{"id": str(item.budget.id), "name": item.budget.name, "currency": item.budget.currency, "limit": str(item.budget.amount), "spent": str(item.spent), "remaining": str(item.remaining), "warning_state": item.warning_state} for item in values]}

    def insights() -> dict:
        rows = session.scalars(select(InsightRecord).where(InsightRecord.owner_user_id == owner_id, InsightRecord.status == "active").order_by(InsightRecord.period_end.desc()).limit(50)).all()
        recurring = session.scalars(select(RecurringDecision).where(RecurringDecision.owner_user_id == owner_id, RecurringDecision.status != "rejected")).all()
        return {"data_mode": "real_private_local", "insights": [{"id": str(row.id), "type": row.insight_type, "currency": row.currency, "title": row.title, "explanation": row.explanation, "evidence": row.evidence_json} for row in rows], "recurring_decisions": [{"series_key": row.series_key, "status": row.status, "label": row.label} for row in recurring]}

    def groups() -> dict:
        memberships = session.scalars(select(GroupMember).where(GroupMember.linked_user_id == owner_id, GroupMember.active.is_(True))).all()
        result = []
        for membership in memberships:
            group = session.get(ExpenseGroup, membership.group_id)
            if group:
                balances = [{key: str(value) if isinstance(value, (uuid.UUID, Decimal)) else value for key, value in row.items()} for row in calculate_balances(session, group.id)]
                result.append({"id": str(group.id), "name": group.name, "currency": group.default_currency, "balances": balances})
        return {"data_mode": "real_private_local", "groups": result}

    def settlements() -> dict:
        group_ids = select(GroupMember.group_id).where(GroupMember.linked_user_id == owner_id, GroupMember.active.is_(True))
        rows = session.scalars(select(Settlement).where(Settlement.group_id.in_(group_ids)).order_by(Settlement.settlement_date.desc()).limit(100)).all()
        return {"data_mode": "real_private_local", "settlements": [{"id": str(row.id), "group_id": str(row.group_id), "date": row.settlement_date.isoformat(), "amount": str(row.amount), "currency": row.currency, "status": row.status} for row in rows]}

    def imports() -> dict:
        rows = session.scalars(select(ImportBatch).where(ImportBatch.owner_user_id == owner_id).order_by(ImportBatch.created_at.desc()).limit(50)).all()
        return {"data_mode": "real_private_local", "imports": [{"id": str(row.id), "file_name": row.file_name, "status": row.status, "row_count": row.row_count, "accepted_count": row.accepted_count, "created_at": row.created_at.isoformat()} for row in rows]}

    def cached_conversion(amount: Decimal, base: str, quote: str, on: date) -> dict:
        if base == quote: return {"data_mode": "real_private_local", "amount": str(amount), "result": str(amount), "rate": "1", "provider": "identity", "rate_date": on.isoformat()}
        rate = session.scalar(select(FxRate).where(FxRate.base_currency == base, FxRate.quote_currency == quote, FxRate.rate_date <= on).order_by(FxRate.rate_date.desc()).limit(1))
        if not rate: return {"data_mode": "real_private_local", "error": "No cached rate; conversion was not estimated"}
        return {"data_mode": "real_private_local", "amount": str(amount), "result": str(amount * rate.rate), "rate": str(rate.rate), "provider": rate.provider, "attribution": rate.attribution, "rate_date": rate.rate_date.isoformat()}

    return [
        StructuredTool.from_function(transactions, name="search_real_transactions", description="Search this authenticated user's real transactions.", args_schema=SearchInput),
        StructuredTool.from_function(spending, name="real_category_spending", description="Calculate deterministic category spending for one currency and period.", args_schema=PeriodInput),
        StructuredTool.from_function(merchants, name="list_real_merchants", description="List this authenticated user's known merchants."),
        StructuredTool.from_function(budgets, name="real_budget_progress", description="Get deterministic progress for this authenticated user's active budgets."),
        StructuredTool.from_function(insights, name="real_finance_insights", description="Read persisted anomalies and recurring-expense decisions with evidence."),
        StructuredTool.from_function(groups, name="real_group_balances", description="Get balances only for groups the authenticated user belongs to."),
        StructuredTool.from_function(settlements, name="real_settlement_history", description="Read settlements only from authorized groups."),
        StructuredTool.from_function(imports, name="real_import_history", description="Read this authenticated user's statement import history."),
        StructuredTool.from_function(cached_conversion, name="cached_real_currency_conversion", description="Convert with an existing cached reference rate and provenance; never fetch or estimate.", args_schema=ConversionInput),
    ]
