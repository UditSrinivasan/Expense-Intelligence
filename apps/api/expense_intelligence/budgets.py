import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from .classification import available_categories, category_for_owner, descendant_category_ids, spending_allocations
from .models import AuditEvent, Budget, BudgetPeriod, BudgetRevision, BudgetStatus, ExpenseAllocation, ExpenseComponent, FxRate, GroupMember, SharedExpense, Transaction, TransactionDirection, TransactionType
from .schemas import BudgetCategoryContribution, BudgetContribution, BudgetCreate, BudgetEvaluation, BudgetRead, BudgetUpdate

CURRENCY_QUANTA = {"JPY": Decimal("1"), "KWD": Decimal("0.001")}
DEFAULT_QUANTUM = Decimal("0.01")
CONVERSION_POLICY = "Historical daily reference rate on or before each transaction date; missing rates are excluded."


def _quantize(value: Decimal, currency: str) -> Decimal:
    return value.quantize(CURRENCY_QUANTA.get(currency, DEFAULT_QUANTUM), rounding=ROUND_HALF_EVEN)


def _validate_period(period_type: BudgetPeriod, start: date, end: date, time_zone: str) -> None:
    try:
        ZoneInfo(time_zone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown IANA time zone") from exc
    if start > end:
        raise ValueError("Start date must not be after end date")
    if period_type == BudgetPeriod.monthly:
        next_month = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
        if start.day != 1 or end != next_month - timedelta(days=1):
            raise ValueError("Monthly budgets must span one complete calendar month")


def _snapshot(budget: Budget, deleted: bool = False) -> str:
    body = BudgetRead.model_validate(budget).model_dump(mode="json")
    body["deleted"] = deleted
    return json.dumps(body, separators=(",", ":"))


def _revision(session: Session, budget: Budget, deleted: bool = False) -> None:
    session.add(BudgetRevision(budget_id=budget.id, owner_user_id=budget.owner_user_id, version=budget.version, snapshot_json=_snapshot(budget, deleted)))


def create_budget(session: Session, owner_id: uuid.UUID, payload: BudgetCreate) -> Budget:
    _validate_period(payload.period_type, payload.start_date, payload.end_date, payload.time_zone)
    if payload.category_id and not category_for_owner(session, owner_id, payload.category_id):
        raise LookupError("Category not found")
    budget = Budget(owner_user_id=owner_id, **payload.model_dump())
    session.add(budget); session.flush(); _revision(session, budget)
    session.add(AuditEvent(actor_user_id=owner_id, action="budget.created", target_type="budget", target_id=str(budget.id)))
    session.commit(); session.refresh(budget)
    return budget


def owned_budget(session: Session, owner_id: uuid.UUID, budget_id: uuid.UUID) -> Budget | None:
    return session.scalar(select(Budget).where(Budget.id == budget_id, Budget.owner_user_id == owner_id, Budget.deleted_at.is_(None)))


def update_budget(session: Session, owner_id: uuid.UUID, budget_id: uuid.UUID, payload: BudgetUpdate) -> Budget:
    budget = owned_budget(session, owner_id, budget_id)
    if not budget:
        raise LookupError("Budget not found")
    if budget.version != payload.expected_version:
        raise RuntimeError("Budget changed since it was loaded")
    values = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if "category_id" in values and values["category_id"] and not category_for_owner(session, owner_id, values["category_id"]):
        raise LookupError("Category not found")
    period = values.get("period_type", budget.period_type)
    start = values.get("start_date", budget.start_date)
    end = values.get("end_date", budget.end_date)
    zone = values.get("time_zone", budget.time_zone)
    _validate_period(period, start, end, zone)
    for key, value in values.items():
        setattr(budget, key, value)
    budget.version += 1; budget.updated_at = datetime.now(timezone.utc)
    session.flush(); _revision(session, budget)
    session.add(AuditEvent(actor_user_id=owner_id, action="budget.updated", target_type="budget", target_id=str(budget.id)))
    session.commit(); session.refresh(budget)
    return budget


def delete_budget(session: Session, owner_id: uuid.UUID, budget_id: uuid.UUID, expected_version: int) -> None:
    budget = owned_budget(session, owner_id, budget_id)
    if not budget:
        raise LookupError("Budget not found")
    if budget.version != expected_version:
        raise RuntimeError("Budget changed since it was loaded")
    budget.version += 1; budget.deleted_at = datetime.now(timezone.utc); budget.updated_at = budget.deleted_at
    session.flush(); _revision(session, budget, deleted=True)
    session.add(AuditEvent(actor_user_id=owner_id, action="budget.deleted", target_type="budget", target_id=str(budget.id)))
    session.commit()


def _rate(session: Session, base: str, quote: str, on: date) -> FxRate | None:
    return session.scalar(select(FxRate).where(FxRate.base_currency == base, FxRate.quote_currency == quote, FxRate.rate_date <= on).order_by(FxRate.rate_date.desc()).limit(1))


def _convert(session: Session, amount: Decimal, source_currency: str, budget: Budget, on: date):
    if source_currency == budget.currency:
        return amount, None, None
    rate_row = _rate(session, source_currency, budget.currency, on)
    if rate_row is None:
        return None, None, "Missing historical FX rate"
    return _quantize(amount * rate_row.rate, budget.currency), rate_row, None


def _collect_spending(session: Session, owner_id: uuid.UUID, budget: Budget, start: date, end: date, include_contributions: bool):
    category_ids = descendant_category_ids(session, owner_id, budget.category_id) if budget.category_id else None
    contributions: list[BudgetContribution] = []
    excluded: dict[str, Decimal] = {}
    subcategory_totals: dict[uuid.UUID, Decimal] = {}
    allocated_transaction_ids: set[uuid.UUID] = set()
    member_ids = list(session.scalars(select(GroupMember.id).where(GroupMember.linked_user_id == owner_id)).all())
    linked_transaction_ids = set(session.scalars(select(SharedExpense.linked_transaction_id).join(ExpenseAllocation, ExpenseAllocation.expense_id == SharedExpense.id).where(ExpenseAllocation.member_id.in_(member_ids), SharedExpense.state == "confirmed", SharedExpense.linked_transaction_id.is_not(None))).all()) if member_ids else set()
    spent = Decimal("0")
    for allocation, transaction in spending_allocations(session, owner_id, start, end):
        if transaction.id in linked_transaction_ids:
            continue
        allocated_transaction_ids.add(transaction.id)
        if category_ids is not None and allocation.category_id not in category_ids:
            continue
        sign = Decimal("-1") if transaction.transaction_type == TransactionType.refund else Decimal("1")
        original = allocation.amount * sign
        converted, rate_row, reason = _convert(session, original, allocation.currency, budget, transaction.effective_date)
        if converted is None:
            excluded[allocation.currency] = excluded.get(allocation.currency, Decimal("0")) + original
        if converted is not None:
            spent += converted
            subcategory_totals[allocation.category_id] = subcategory_totals.get(allocation.category_id, Decimal("0")) + converted
        if include_contributions:
            contributions.append(BudgetContribution(transaction_id=transaction.id, description=transaction.description, effective_date=transaction.effective_date, category_id=allocation.category_id, original_amount=original, original_currency=allocation.currency, converted_amount=converted, budget_currency=budget.currency, rate=rate_row.rate if rate_row else (Decimal("1") if converted is not None else None), rate_date=rate_row.rate_date if rate_row else (transaction.effective_date if converted is not None else None), rate_provider=rate_row.provider if rate_row else ("identity" if converted is not None else None), excluded_reason=reason))
    if category_ids is None:
        unallocated = session.scalars(select(Transaction).where(Transaction.owner_user_id == owner_id, Transaction.effective_date.between(start, end), ~Transaction.id.in_(allocated_transaction_ids), ~Transaction.id.in_(linked_transaction_ids), ((Transaction.direction == TransactionDirection.expense) & (Transaction.transaction_type == TransactionType.purchase)) | ((Transaction.direction == TransactionDirection.income) & (Transaction.transaction_type == TransactionType.refund)))).all()
        for transaction in unallocated:
            original = transaction.original_amount * (Decimal("-1") if transaction.transaction_type == TransactionType.refund else Decimal("1"))
            converted, rate_row, reason = _convert(session, original, transaction.original_currency, budget, transaction.effective_date)
            if converted is None:
                excluded[transaction.original_currency] = excluded.get(transaction.original_currency, Decimal("0")) + original
            else:
                spent += converted
            if include_contributions:
                contributions.append(BudgetContribution(transaction_id=transaction.id, description=transaction.description, effective_date=transaction.effective_date, category_id=None, original_amount=original, original_currency=transaction.original_currency, converted_amount=converted, budget_currency=budget.currency, rate=rate_row.rate if rate_row else (Decimal("1") if converted is not None else None), rate_date=rate_row.rate_date if rate_row else (transaction.effective_date if converted is not None else None), rate_provider=rate_row.provider if rate_row else ("identity" if converted is not None else None), excluded_reason=reason))
    if member_ids:
        shared_rows = session.execute(select(ExpenseAllocation, ExpenseComponent, SharedExpense).join(ExpenseComponent, ExpenseComponent.id == ExpenseAllocation.component_id).join(SharedExpense, SharedExpense.id == ExpenseAllocation.expense_id).where(ExpenseAllocation.member_id.in_(member_ids), SharedExpense.state == "confirmed", SharedExpense.expense_date.between(start, end))).all()
        for allocation, component, expense in shared_rows:
            category_id = component.category_id or expense.category_id
            if category_ids is not None and category_id not in category_ids:
                continue
            converted, rate_row, reason = _convert(session, allocation.amount, expense.currency, budget, expense.expense_date)
            if converted is None:
                excluded[expense.currency] = excluded.get(expense.currency, Decimal("0")) + allocation.amount
            else:
                spent += converted
                if category_id:
                    subcategory_totals[category_id] = subcategory_totals.get(category_id, Decimal("0")) + converted
            if include_contributions:
                contributions.append(BudgetContribution(transaction_id=expense.id, description=f"Shared: {expense.description}", effective_date=expense.expense_date, category_id=category_id, original_amount=allocation.amount, original_currency=expense.currency, converted_amount=converted, budget_currency=budget.currency, rate=rate_row.rate if rate_row else (Decimal("1") if converted is not None else None), rate_date=rate_row.rate_date if rate_row else (expense.expense_date if converted is not None else None), rate_provider=rate_row.provider if rate_row else ("identity" if converted is not None else None), excluded_reason=reason))
    return _quantize(spent, budget.currency), excluded, subcategory_totals, contributions


def evaluate_budget(session: Session, owner_id: uuid.UUID, budget: Budget) -> BudgetEvaluation:
    spent, excluded, subcategory_totals, contributions = _collect_spending(session, owner_id, budget, budget.start_date, budget.end_date, True)
    remaining = _quantize(max(budget.amount - spent, Decimal("0")), budget.currency)
    over = _quantize(max(spent - budget.amount, Decimal("0")), budget.currency)
    utilization = (spent / budget.amount * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    warning = "over_budget" if spent > budget.amount else "near_limit" if utilization >= budget.warning_percent else "ok"
    duration = (budget.end_date - budget.start_date).days + 1
    previous_start = budget.start_date - timedelta(days=duration)
    previous_end = budget.start_date - timedelta(days=1)
    previous_spent, _, _, _ = _collect_spending(session, owner_id, budget, previous_start, previous_end, False)
    names = {row.id: row.name for row in available_categories(session, owner_id)}
    largest = [BudgetCategoryContribution(category_id=category_id, name=names.get(category_id, "Unavailable category"), amount=_quantize(amount, budget.currency)) for category_id, amount in sorted(subcategory_totals.items(), key=lambda item: item[1], reverse=True)[:5]]
    return BudgetEvaluation(budget=budget, spent=spent, remaining=remaining, over_budget=over, utilization_percent=utilization, warning_state=warning, complete=not excluded, excluded_by_currency=excluded, conversion_policy=CONVERSION_POLICY, previous_period_spent=previous_spent, previous_period_difference=_quantize(spent - previous_spent, budget.currency), largest_subcategories=largest, contributions=contributions)
