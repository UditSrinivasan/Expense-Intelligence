import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .database import get_db
from .models import AuditEvent, Category, ExpenseAllocation, ExpenseComponent, ExpenseGroup, ExpensePayer, GroupMember, GroupRole, Settlement, SharedExpense, SplitTemplate
from .splitting import ComponentInput, ExpenseInput, QUANTA, _allocate, _membership, preview

router = APIRouter(prefix="/v1/groups", tags=["group-finance"])


class SettlementCreate(BaseModel):
    idempotency_key: uuid.UUID
    expected_group_version: int = Field(ge=1)
    payer_member_id: uuid.UUID
    payee_member_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=38, decimal_places=12)
    currency: str = Field(min_length=3, max_length=3)
    settlement_date: date
    reference: str | None = Field(default=None, max_length=160)
    status: Literal["pending", "confirmed"] = "confirmed"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class SettlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    payer_member_id: uuid.UUID
    payee_member_id: uuid.UUID
    amount: Decimal
    currency: str
    settlement_date: date
    reference: str | None
    status: str
    kind: str
    reverses_settlement_id: uuid.UUID | None
    created_at: datetime


class ReverseSettlement(BaseModel):
    idempotency_key: uuid.UUID
    expected_group_version: int = Field(ge=1)
    reference: str | None = Field(default=None, max_length=160)


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=280)
    currency: str = Field(min_length=3, max_length=3)
    category_id: uuid.UUID | None = None
    components: list[ComponentInput] = Field(min_length=1, max_length=100)

    @field_validator("currency")
    @classmethod
    def template_currency(cls, value: str) -> str:
        return value.upper()


class TemplateUpdate(TemplateCreate):
    expected_version: int = Field(ge=1)


class MemberUpdate(BaseModel):
    expected_group_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None


class CorrectionRequest(BaseModel):
    expected_group_version: int = Field(ge=1)
    replacement: ExpenseInput


def _expense_net(session: Session, expense_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    net = defaultdict(Decimal)
    for row in session.scalars(select(ExpensePayer).where(ExpensePayer.expense_id == expense_id)).all(): net[row.member_id] += row.amount
    for row in session.scalars(select(ExpenseAllocation).where(ExpenseAllocation.expense_id == expense_id)).all(): net[row.member_id] -= row.amount
    return net


def _persist_expense(session: Session, group_id: uuid.UUID, user_id: uuid.UUID, payload: ExpenseInput, result: dict, corrects: uuid.UUID | None = None) -> SharedExpense:
    expense = SharedExpense(group_id=group_id, creator_user_id=user_id, description=payload.description, total=payload.total, currency=payload.currency, expense_date=payload.expense_date, idempotency_key=payload.idempotency_key, category_id=payload.category_id, corrects_expense_id=corrects)
    session.add(expense); session.flush()
    for payer in payload.payers: session.add(ExpensePayer(expense_id=expense.id, member_id=payer.member_id, amount=payer.amount))
    components = []
    for component in payload.components:
        row = ExpenseComponent(expense_id=expense.id, label=component.label, amount=component.amount, strategy=component.strategy, category_id=component.category_id)
        session.add(row); session.flush(); components.append(row)
    for allocation in result["allocations"]:
        session.add(ExpenseAllocation(expense_id=expense.id, component_id=components[allocation["component_index"]].id, member_id=allocation["member_id"], input_value=allocation["input_value"], unrounded_amount=allocation["unrounded_amount"], amount=allocation["amount"], received_residual=allocation["received_residual"]))
    return expense


def _members(session: Session, group_id: uuid.UUID) -> list[GroupMember]:
    return list(session.scalars(select(GroupMember).where(GroupMember.group_id == group_id).order_by(GroupMember.created_at)).all())


def calculate_balances(session: Session, group_id: uuid.UUID) -> list[dict]:
    members = _members(session, group_id)
    currencies = set(session.scalars(select(SharedExpense.currency).where(SharedExpense.group_id == group_id, SharedExpense.state == "confirmed").distinct()).all())
    currencies.update(session.scalars(select(Settlement.currency).where(Settlement.group_id == group_id).distinct()).all())
    output = []
    for currency in sorted(currencies):
        paid = dict(session.execute(select(ExpensePayer.member_id, func.sum(ExpensePayer.amount)).join(SharedExpense).where(SharedExpense.group_id == group_id, SharedExpense.currency == currency, SharedExpense.state == "confirmed").group_by(ExpensePayer.member_id)).all())
        owed = dict(session.execute(select(ExpenseAllocation.member_id, func.sum(ExpenseAllocation.amount)).join(SharedExpense).where(SharedExpense.group_id == group_id, SharedExpense.currency == currency, SharedExpense.state == "confirmed").group_by(ExpenseAllocation.member_id)).all())
        outgoing = defaultdict(Decimal); incoming = defaultdict(Decimal)
        payments = session.scalars(select(Settlement).where(Settlement.group_id == group_id, Settlement.currency == currency, Settlement.status == "confirmed", Settlement.kind == "payment")).all()
        for payment in payments:
            outgoing[payment.payer_member_id] += payment.amount
            incoming[payment.payee_member_id] += payment.amount
        for member in members:
            member_paid = Decimal(paid.get(member.id, 0)); member_owed = Decimal(owed.get(member.id, 0))
            balance = member_paid - member_owed + outgoing[member.id] - incoming[member.id]
            output.append({"member_id": member.id, "display_name": member.display_name, "active": member.active, "currency": currency, "paid": member_paid, "owed": member_owed, "settled_out": outgoing[member.id], "settled_in": incoming[member.id], "balance": balance})
        if sum((row["balance"] for row in output if row["currency"] == currency), Decimal(0)) != 0:
            raise RuntimeError("Group balance conservation failed")
    return output


def simplify_debts(rows: list[dict]) -> list[dict]:
    suggestions = []
    for currency in sorted({row["currency"] for row in rows}):
        debtors = [[row["member_id"], row["display_name"], -row["balance"]] for row in rows if row["currency"] == currency and row["balance"] < 0]
        creditors = [[row["member_id"], row["display_name"], row["balance"]] for row in rows if row["currency"] == currency and row["balance"] > 0]
        debtors.sort(key=lambda row: (-row[2], str(row[0]))); creditors.sort(key=lambda row: (-row[2], str(row[0])))
        while debtors and creditors:
            debtor, creditor = debtors[0], creditors[0]; amount = min(debtor[2], creditor[2])
            suggestions.append({"payer_member_id": debtor[0], "payer_name": debtor[1], "payee_member_id": creditor[0], "payee_name": creditor[1], "amount": amount, "currency": currency, "explanation": "Greedy net-balance match; this is a suggestion only and does not record payment."})
            debtor[2] -= amount; creditor[2] -= amount
            if debtor[2] == 0: debtors.pop(0)
            if creditor[2] == 0: creditors.pop(0)
    return suggestions


def _bump_group(session: Session, group_id: uuid.UUID, expected: int) -> ExpenseGroup:
    group = session.scalar(select(ExpenseGroup).where(ExpenseGroup.id == group_id).with_for_update())
    if not group or group.version != expected:
        raise RuntimeError("Group changed; refresh and retry")
    group.version += 1
    return group


def _settlement_obligation(session: Session, group_id: uuid.UUID, payer_id: uuid.UUID, payee_id: uuid.UUID, currency: str) -> Decimal:
    indexed = {row["member_id"]: row for row in calculate_balances(session, group_id) if row["currency"] == currency}
    payer = indexed.get(payer_id); payee = indexed.get(payee_id)
    return min(-payer["balance"] if payer and payer["balance"] < 0 else Decimal(0), payee["balance"] if payee and payee["balance"] > 0 else Decimal(0))


@router.get("/{group_id}/settlements", response_model=list[SettlementRead])
def settlement_history(group_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    return list(session.scalars(select(Settlement).where(Settlement.group_id == group_id).order_by(Settlement.settlement_date.desc(), Settlement.created_at.desc())).all())


@router.post("/{group_id}/settlements", response_model=SettlementRead, status_code=201)
def record_settlement(group_id: uuid.UUID, payload: SettlementCreate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    existing = session.scalar(select(Settlement).where(Settlement.group_id == group_id, Settlement.idempotency_key == payload.idempotency_key))
    if existing: return existing
    if payload.payer_member_id == payload.payee_member_id: raise HTTPException(422, "Payer and payee must differ")
    member_ids = {member.id for member in _members(session, group_id)}
    if not {payload.payer_member_id, payload.payee_member_id} <= member_ids: raise HTTPException(422, "Settlement participants must belong to the group")
    quantum = QUANTA.get(payload.currency, Decimal("0.01"))
    if payload.amount != payload.amount.quantize(quantum): raise HTTPException(422, "Amount must use the currency's minor-unit precision")
    try: _bump_group(session, group_id, payload.expected_group_version)
    except RuntimeError as exc: raise HTTPException(409, str(exc)) from exc
    obligation = _settlement_obligation(session, group_id, payload.payer_member_id, payload.payee_member_id, payload.currency)
    if payload.amount > obligation: raise HTTPException(422, f"Settlement exceeds the current obligation of {obligation} {payload.currency}")
    row = Settlement(group_id=group_id, payer_member_id=payload.payer_member_id, payee_member_id=payload.payee_member_id, amount=payload.amount, currency=payload.currency, settlement_date=payload.settlement_date, reference=payload.reference, status=payload.status, idempotency_key=payload.idempotency_key, created_by_user_id=user.id)
    session.add(row); session.add(AuditEvent(actor_user_id=user.id, action="settlement.recorded", target_type="settlement", target_id=str(row.id)))
    try: session.commit()
    except IntegrityError:
        session.rollback(); row = session.scalar(select(Settlement).where(Settlement.group_id == group_id, Settlement.idempotency_key == payload.idempotency_key))
        if not row: raise
    session.refresh(row); return row


@router.post("/{group_id}/settlements/{settlement_id}/confirm", response_model=SettlementRead)
def confirm_pending(group_id: uuid.UUID, settlement_id: uuid.UUID, expected_group_version: int, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id); row = session.scalar(select(Settlement).where(Settlement.id == settlement_id, Settlement.group_id == group_id).with_for_update())
    if not row: raise HTTPException(404, "Settlement not found")
    if row.status == "confirmed": return row
    if row.status != "pending": raise HTTPException(409, "Only pending settlements can be confirmed")
    try: _bump_group(session, group_id, expected_group_version)
    except RuntimeError as exc: raise HTTPException(409, str(exc)) from exc
    if row.amount > _settlement_obligation(session, group_id, row.payer_member_id, row.payee_member_id, row.currency): raise HTTPException(422, "Settlement exceeds the current obligation")
    row.status = "confirmed"; session.add(AuditEvent(actor_user_id=user.id, action="settlement.confirmed", target_type="settlement", target_id=str(row.id))); session.commit(); session.refresh(row); return row


@router.post("/{group_id}/settlements/{settlement_id}/reverse", response_model=SettlementRead, status_code=201)
def reverse_settlement(group_id: uuid.UUID, settlement_id: uuid.UUID, payload: ReverseSettlement, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    existing = session.scalar(select(Settlement).where(Settlement.group_id == group_id, Settlement.idempotency_key == payload.idempotency_key))
    if existing: return existing
    original = session.scalar(select(Settlement).where(Settlement.id == settlement_id, Settlement.group_id == group_id).with_for_update())
    if not original: raise HTTPException(404, "Settlement not found")
    if original.status != "confirmed" or original.kind != "payment": raise HTTPException(409, "Only confirmed payments can be reversed")
    try: _bump_group(session, group_id, payload.expected_group_version)
    except RuntimeError as exc: raise HTTPException(409, str(exc)) from exc
    original.status = "reversed"
    reversal = Settlement(group_id=group_id, payer_member_id=original.payee_member_id, payee_member_id=original.payer_member_id, amount=original.amount, currency=original.currency, settlement_date=date.today(), reference=payload.reference, status="confirmed", kind="reversal", reverses_settlement_id=original.id, idempotency_key=payload.idempotency_key, created_by_user_id=user.id)
    session.add(reversal); session.add(AuditEvent(actor_user_id=user.id, action="settlement.reversed", target_type="settlement", target_id=str(original.id))); session.commit(); session.refresh(reversal); return reversal


@router.get("/{group_id}/debt-suggestions")
def debt_suggestions(group_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id); rows = calculate_balances(session, group_id)
    return {"balances": rows, "suggestions": simplify_debts(rows), "policy": "Each currency is simplified independently. Suggestions preserve net balances and do not record settlements."}


def _validate_template(session: Session, group_id: uuid.UUID, payload: TemplateCreate):
    valid = {member.id for member in _members(session, group_id) if member.active}
    quantum = QUANTA.get(payload.currency, Decimal("0.01"))
    for component in payload.components:
        if not {share.member_id for share in component.shares} <= valid: raise ValueError("Template participants must be active group members")
        _allocate(component, quantum)
    if payload.category_id and not session.scalar(select(Category.id).where(Category.id == payload.category_id, (Category.owner_user_id.is_(None) | (Category.owner_user_id.in_(select(GroupMember.linked_user_id).where(GroupMember.group_id == group_id)))))):
        raise ValueError("Category is not available")


def _template_json(row: SplitTemplate) -> dict:
    return {"id": row.id, "name": row.name, "description": row.description, "currency": row.currency, "category_id": row.category_id, "components": json.loads(row.components_json), "version": row.version, "active": row.active}


@router.get("/{group_id}/templates")
def list_templates(group_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id); return [_template_json(row) for row in session.scalars(select(SplitTemplate).where(SplitTemplate.group_id == group_id, SplitTemplate.active.is_(True)).order_by(SplitTemplate.name)).all()]


@router.post("/{group_id}/templates", status_code=201)
def create_template(group_id: uuid.UUID, payload: TemplateCreate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    try: _validate_template(session, group_id, payload)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    row = SplitTemplate(group_id=group_id, name=payload.name, description=payload.description, currency=payload.currency, category_id=payload.category_id, components_json=json.dumps([component.model_dump(mode="json") for component in payload.components]), created_by_user_id=user.id)
    session.add(row); session.add(AuditEvent(actor_user_id=user.id, action="split_template.created", target_type="split_template", target_id=str(row.id)))
    try: session.commit()
    except IntegrityError as exc: session.rollback(); raise HTTPException(409, "A template with this name already exists") from exc
    session.refresh(row); return _template_json(row)


@router.put("/{group_id}/templates/{template_id}")
def update_template(group_id: uuid.UUID, template_id: uuid.UUID, payload: TemplateUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id); row = session.scalar(select(SplitTemplate).where(SplitTemplate.id == template_id, SplitTemplate.group_id == group_id).with_for_update())
    if not row: raise HTTPException(404, "Template not found")
    if row.version != payload.expected_version: raise HTTPException(409, "Template changed; refresh and retry")
    try: _validate_template(session, group_id, payload)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    row.name = payload.name; row.description = payload.description; row.currency = payload.currency; row.category_id = payload.category_id; row.components_json = json.dumps([component.model_dump(mode="json") for component in payload.components]); row.version += 1; row.updated_at = datetime.now(timezone.utc)
    session.add(AuditEvent(actor_user_id=user.id, action="split_template.updated", target_type="split_template", target_id=str(row.id))); session.commit(); session.refresh(row); return _template_json(row)


@router.post("/{group_id}/templates/{template_id}/apply")
def apply_template(group_id: uuid.UUID, template_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id); row = session.scalar(select(SplitTemplate).where(SplitTemplate.id == template_id, SplitTemplate.group_id == group_id, SplitTemplate.active.is_(True)))
    if not row: raise HTTPException(404, "Template not found")
    return {"template_id": row.id, "template_version": row.version, "idempotency_key": uuid.uuid4(), "description": row.description, "currency": row.currency, "category_id": row.category_id, "expense_date": date.today(), "components": json.loads(row.components_json), "payers": []}


@router.get("/{group_id}/members/all")
def all_members(group_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id); return [{"id": row.id, "display_name": row.display_name, "role": row.role, "active": row.active, "is_guest": row.linked_user_id is None} for row in _members(session, group_id)]


@router.put("/{group_id}/members/{member_id}")
def update_member(group_id: uuid.UUID, member_id: uuid.UUID, payload: MemberUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    actor = _membership(session, user.id, group_id)
    if actor.role != GroupRole.owner: raise HTTPException(403, "Only group owners can manage members")
    member = session.scalar(select(GroupMember).where(GroupMember.id == member_id, GroupMember.group_id == group_id).with_for_update())
    if not member: raise HTTPException(404, "Member not found")
    if member.role == GroupRole.owner and payload.active is False: raise HTTPException(422, "The group owner cannot be deactivated")
    try: _bump_group(session, group_id, payload.expected_group_version)
    except RuntimeError as exc: raise HTTPException(409, str(exc)) from exc
    if payload.display_name is not None: member.display_name = payload.display_name; member.guest_name = payload.display_name if member.linked_user_id is None else None
    if payload.active is not None: member.active = payload.active
    session.add(AuditEvent(actor_user_id=user.id, action="group.member_updated", target_type="group_member", target_id=str(member.id))); session.commit()
    balances = [row for row in calculate_balances(session, group_id) if row["member_id"] == member.id and row["balance"] != 0]
    return {"id": member.id, "display_name": member.display_name, "active": member.active, "outstanding_balances": balances}


@router.get("/{group_id}/analytics")
def group_analytics(group_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    expenses = list(session.scalars(select(SharedExpense).where(SharedExpense.group_id == group_id, SharedExpense.state == "confirmed").order_by(SharedExpense.expense_date.desc())).all())
    category_ids = {expense.category_id for expense in expenses if expense.category_id}
    category_names = dict(session.execute(select(Category.id, Category.name).where(Category.id.in_(category_ids))).all()) if category_ids else {}
    totals = defaultdict(Decimal); by_category = defaultdict(lambda: defaultdict(Decimal)); timeline = defaultdict(lambda: defaultdict(Decimal))
    for expense in expenses:
        totals[expense.currency] += expense.total; by_category[category_names.get(expense.category_id, "uncategorized")][expense.currency] += expense.total; timeline[expense.expense_date.isoformat()][expense.currency] += expense.total
    balances = calculate_balances(session, group_id)
    settlements = list(session.scalars(select(Settlement).where(Settlement.group_id == group_id).order_by(Settlement.created_at.desc())).all())
    participant = [{"member_id": row["member_id"], "display_name": row["display_name"], "currency": row["currency"], "paid": row["paid"], "consumed": row["owed"]} for row in balances]
    return {"totals_by_currency": totals, "spending_by_category": by_category, "spending_over_time": timeline, "participants": participant, "balances": balances, "settlements_completed": len([row for row in settlements if row.status == "confirmed" and row.kind == "payment"]), "recent_expenses": [{"id": row.id, "description": row.description, "total": row.total, "currency": row.currency, "expense_date": row.expense_date} for row in expenses[:10]], "largest_expenses": [{"id": row.id, "description": row.description, "total": row.total, "currency": row.currency} for row in sorted(expenses, key=lambda item: (-item.total, str(item.id)))[:5]], "unsettled_obligations": simplify_debts(balances), "currency_policy": "Original-currency totals remain separate; no FX amounts are merged."}


def _amount(value: Decimal) -> str:
    return format(value, "f")


@router.get("/{group_id}/expenses/{expense_id}")
def expense_detail(group_id: uuid.UUID, expense_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    expense = session.scalar(select(SharedExpense).where(SharedExpense.id == expense_id, SharedExpense.group_id == group_id))
    if not expense:
        raise HTTPException(404, "Expense not found")
    members = {row.id: row for row in _members(session, group_id)}
    payers = list(session.scalars(select(ExpensePayer).where(ExpensePayer.expense_id == expense.id)).all())
    components = list(session.scalars(select(ExpenseComponent).where(ExpenseComponent.expense_id == expense.id).order_by(ExpenseComponent.id)).all())
    allocations = list(session.scalars(select(ExpenseAllocation).where(ExpenseAllocation.expense_id == expense.id)).all())
    by_component = defaultdict(list); liabilities = defaultdict(Decimal)
    for row in allocations:
        liabilities[row.member_id] += row.amount
        by_component[row.component_id].append(row)
    paid = defaultdict(Decimal)
    for row in payers: paid[row.member_id] += row.amount
    quantum = QUANTA.get(expense.currency, Decimal("0.01"))
    if sum(paid.values(), Decimal(0)) != expense.total or sum((row.amount for row in components), Decimal(0)) != expense.total or sum(liabilities.values(), Decimal(0)) != expense.total:
        raise HTTPException(409, "Stored expense does not reconcile")
    for component in components:
        if sum((row.amount for row in by_component[component.id]), Decimal(0)) != component.amount:
            raise HTTPException(409, "Stored component does not reconcile")
    balances = [{"member_id": member_id, "display_name": members[member_id].display_name, "currency": expense.currency, "balance": paid[member_id] - liabilities[member_id]} for member_id in sorted(set(paid) | set(liabilities), key=str)]
    replacement = session.scalar(select(SharedExpense.id).where(SharedExpense.corrects_expense_id == expense.id))
    def adjustment_type(component):
        label = component.label.lower()
        if component.amount < 0 or "discount" in label or "rebate" in label: return "discount"
        if "tax" in label or "gst" in label or "vat" in label: return "tax"
        if "service" in label: return "service_charge"
        if "tip" in label or "gratuity" in label: return "tip"
        if "round" in label: return "rounding"
        return "item"
    return {
        "id": expense.id, "group_id": expense.group_id, "title": expense.description, "expense_date": expense.expense_date,
        "currency": expense.currency, "currency_quantum": _amount(quantum), "total": _amount(expense.total), "status": expense.state,
        "payers": [{"member_id": row.member_id, "display_name": members[row.member_id].display_name, "amount": _amount(row.amount)} for row in payers],
        "participants": [{"member_id": member_id, "display_name": members[member_id].display_name, "share": _amount(liabilities[member_id]), "paid": _amount(paid[member_id]), "balance": _amount(paid[member_id] - liabilities[member_id])} for member_id in sorted(set(paid) | set(liabilities), key=str)],
        "components": [{"id": component.id, "label": component.label, "amount": _amount(component.amount), "strategy": component.strategy, "category_id": component.category_id, "adjustment_type": adjustment_type(component), "allocations": [{"member_id": row.member_id, "display_name": members[row.member_id].display_name, "input_value": _amount(row.input_value) if row.input_value is not None else None, "unrounded_amount": _amount(row.unrounded_amount), "amount": _amount(row.amount), "received_residual": row.received_residual} for row in by_component[component.id]]} for component in components],
        "obligations": [{**row, "amount": _amount(row["amount"])} for row in simplify_debts(balances)],
        "correction": {"corrects_expense_id": expense.corrects_expense_id, "replacement_expense_id": replacement},
        "reconciliation": {"payer_total": _amount(sum(paid.values(), Decimal(0))), "component_total": _amount(sum((row.amount for row in components), Decimal(0))), "allocation_total": _amount(sum(liabilities.values(), Decimal(0))), "reconciled": True},
    }


def _correction_preview(session: Session, group_id: uuid.UUID, original: SharedExpense, replacement: ExpenseInput) -> dict:
    if replacement.currency != original.currency: raise ValueError("Corrections must preserve the original currency")
    result = preview(session, group_id, replacement)
    before = calculate_balances(session, group_id); projected = {(row["member_id"], row["currency"]): row["balance"] for row in before}
    for member_id, amount in _expense_net(session, original.id).items(): projected[(member_id, original.currency)] -= amount
    for row in result["balances"]: projected[(row["member_id"], replacement.currency)] = projected.get((row["member_id"], replacement.currency), Decimal(0)) + row["balance"]
    confirmed_settlements = session.scalar(select(func.count(Settlement.id)).where(Settlement.group_id == group_id, Settlement.currency == original.currency, Settlement.status == "confirmed", Settlement.kind == "payment")) or 0
    return {"original_expense_id": original.id, "before": before, "projected_balances": [{"member_id": key[0], "currency": key[1], "balance": value} for key, value in sorted(projected.items(), key=lambda item: (item[0][1], str(item[0][0])))], "replacement_preview": result, "blocked_by_confirmed_settlements": confirmed_settlements > 0}


@router.post("/{group_id}/expenses/{expense_id}/correction-preview")
def correction_preview(group_id: uuid.UUID, expense_id: uuid.UUID, payload: CorrectionRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id); original = session.scalar(select(SharedExpense).where(SharedExpense.id == expense_id, SharedExpense.group_id == group_id, SharedExpense.state == "confirmed"))
    if not original: raise HTTPException(404, "Confirmed expense not found")
    try: return _correction_preview(session, group_id, original, payload.replacement)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.post("/{group_id}/expenses/{expense_id}/correct", status_code=201)
def correct_expense(group_id: uuid.UUID, expense_id: uuid.UUID, payload: CorrectionRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    actor = _membership(session, user.id, group_id); original = session.scalar(select(SharedExpense).where(SharedExpense.id == expense_id, SharedExpense.group_id == group_id).with_for_update())
    if not original or original.state != "confirmed": raise HTTPException(404, "Confirmed expense not found")
    if session.get(ExpenseGroup, group_id).archived_at is not None: raise HTTPException(409, "Archived groups cannot accept expense corrections")
    if actor.role != GroupRole.owner and original.creator_user_id != user.id: raise HTTPException(403, "Only the expense creator or group owner can correct it")
    existing = session.scalar(select(SharedExpense).where(SharedExpense.group_id == group_id, SharedExpense.idempotency_key == payload.replacement.idempotency_key))
    if existing: return {"original_expense_id": original.id, "replacement_expense_id": existing.id, "state": existing.state}
    try: proposal = _correction_preview(session, group_id, original, payload.replacement)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    if proposal["blocked_by_confirmed_settlements"]: raise HTTPException(409, "Reverse affected confirmed settlements before correcting this expense")
    try: _bump_group(session, group_id, payload.expected_group_version)
    except RuntimeError as exc: raise HTTPException(409, str(exc)) from exc
    original.state = "reversed"; replacement = _persist_expense(session, group_id, user.id, payload.replacement, proposal["replacement_preview"], original.id)
    session.add(AuditEvent(actor_user_id=user.id, action="shared_expense.corrected", target_type="shared_expense", target_id=str(original.id))); session.commit(); session.refresh(replacement)
    return {"original_expense_id": original.id, "replacement_expense_id": replacement.id, "state": replacement.state}
