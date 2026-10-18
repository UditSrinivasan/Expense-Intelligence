import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .database import get_db
from .models import AuditEvent, ExpenseAllocation, ExpenseComponent, ExpenseGroup, ExpensePayer, GroupMember, GroupRole, ReceiptDocument, SharedExpense

router = APIRouter(prefix="/v1/groups", tags=["groups"])
QUANTA = {"JPY": Decimal("1"), "KWD": Decimal("0.001")}


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    default_currency: str = Field(min_length=3, max_length=3)
    owner_name: str = Field(default="You", min_length=1, max_length=120)

    @field_validator("default_currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class GroupUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    archived: bool | None = None

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Group name cannot be blank")
        return value


class MemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    linked_user_id: uuid.UUID | None = None


class ShareInput(BaseModel):
    member_id: uuid.UUID
    value: Decimal | None = Field(default=None, ge=0, max_digits=38, decimal_places=12)


class ComponentInput(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(max_digits=38, decimal_places=12)
    strategy: Literal["equal", "percentage", "exact", "weighted", "quantity", "usage", "time"]
    shares: list[ShareInput] = Field(min_length=1, max_length=100)
    category_id: uuid.UUID | None = None


class PayerInput(BaseModel):
    member_id: uuid.UUID
    amount: Decimal = Field(ge=0, max_digits=38, decimal_places=12)


class ExpenseInput(BaseModel):
    idempotency_key: uuid.UUID
    description: str = Field(min_length=1, max_length=280)
    total: Decimal = Field(gt=0, max_digits=38, decimal_places=12)
    currency: str = Field(min_length=3, max_length=3)
    expense_date: date
    category_id: uuid.UUID | None = None
    source_receipt_id: uuid.UUID | None = None
    payers: list[PayerInput] = Field(min_length=1, max_length=100)
    components: list[ComponentInput] = Field(min_length=1, max_length=100)

    @field_validator("currency")
    @classmethod
    def uppercase_expense_currency(cls, value: str) -> str:
        return value.upper()


class AllocationPreview(BaseModel):
    member_id: uuid.UUID
    component_index: int
    component_label: str
    input_value: Decimal | None
    unrounded_amount: Decimal
    amount: Decimal
    received_residual: bool


class BalancePreview(BaseModel):
    member_id: uuid.UUID
    paid: Decimal
    owed: Decimal
    balance: Decimal


class PreviewRead(BaseModel):
    allocation_version: str
    allocations: list[AllocationPreview]
    balances: list[BalancePreview]


class ConfirmedRead(PreviewRead):
    id: uuid.UUID
    state: str


class GroupBalanceRead(BalancePreview):
    display_name: str
    active: bool
    currency: str
    settled_out: Decimal
    settled_in: Decimal


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    default_currency: str
    version: int


def _membership(session: Session, user_id: uuid.UUID, group_id: uuid.UUID) -> GroupMember:
    member = session.scalar(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.linked_user_id == user_id, GroupMember.active.is_(True)))
    if not member:
        raise HTTPException(404, "Group not found")
    return member


def _member_ids(session: Session, group_id: uuid.UUID) -> set[uuid.UUID]:
    return set(session.scalars(select(GroupMember.id).where(GroupMember.group_id == group_id, GroupMember.active.is_(True))).all())


def _allocate(component: ComponentInput, quantum: Decimal) -> list[dict]:
    amount = component.amount
    if amount != amount.quantize(quantum):
        raise ValueError("Amounts must use the currency's minor-unit precision")
    ids = [share.member_id for share in component.shares]
    if len(ids) != len(set(ids)):
        raise ValueError("A participant may appear only once per component")
    if component.strategy == "exact":
        values = [share.value for share in component.shares]
        if any(value is None or value != value.quantize(quantum) for value in values):
            raise ValueError("Exact shares require minor-unit amounts")
        if sum(values, Decimal(0)) != amount:
            raise ValueError("Exact shares must equal the component amount")
        return [{"member_id": share.member_id, "input_value": share.value, "unrounded_amount": share.value, "amount": share.value, "received_residual": False} for share in component.shares]

    if component.strategy == "equal":
        weights = [Decimal(1)] * len(component.shares)
    else:
        weights = [share.value for share in component.shares]
        if any(value is None or value <= 0 for value in weights):
            raise ValueError(f"{component.strategy.title()} shares require positive values")
        if component.strategy == "percentage" and sum(weights, Decimal(0)) != Decimal(100):
            raise ValueError("Percentages must total exactly 100")
    weight_total = sum(weights, Decimal(0))
    sign = Decimal(-1) if amount < 0 else Decimal(1)
    absolute = abs(amount)
    raw = [absolute * weight / weight_total for weight in weights]
    rounded = [value.quantize(quantum, rounding=ROUND_DOWN) for value in raw]
    residual_units = int((absolute - sum(rounded, Decimal(0))) / quantum)
    order = sorted(range(len(raw)), key=lambda index: (-(raw[index] - rounded[index]), str(ids[index])))
    residual = set(order[:residual_units])
    return [{"member_id": share.member_id, "input_value": share.value, "unrounded_amount": raw[index] * sign, "amount": (rounded[index] + (quantum if index in residual else 0)) * sign, "received_residual": index in residual} for index, share in enumerate(component.shares)]


def preview(session: Session, group_id: uuid.UUID, payload: ExpenseInput) -> dict:
    valid_members = _member_ids(session, group_id)
    if len({payer.member_id for payer in payload.payers}) != len(payload.payers):
        raise ValueError("A payer may appear only once")
    referenced = {payer.member_id for payer in payload.payers} | {share.member_id for component in payload.components for share in component.shares}
    if not referenced <= valid_members:
        raise ValueError("Every payer and participant must be an active group member")
    quantum = QUANTA.get(payload.currency, Decimal("0.01"))
    if payload.total != payload.total.quantize(quantum):
        raise ValueError("Total must use the currency's minor-unit precision")
    if sum((payer.amount for payer in payload.payers), Decimal(0)) != payload.total:
        raise ValueError("Payer amounts must equal the expense total")
    if sum((component.amount for component in payload.components), Decimal(0)) != payload.total:
        raise ValueError("Component amounts must equal the expense total")
    allocations = []
    owed = defaultdict(Decimal)
    for index, component in enumerate(payload.components):
        rows = _allocate(component, quantum)
        if sum((row["amount"] for row in rows), Decimal(0)) != component.amount:
            raise ValueError("Allocation reconciliation failed")
        for row in rows:
            row["component_index"] = index
            row["component_label"] = component.label
            owed[row["member_id"]] += row["amount"]
        allocations.extend(rows)
    paid = defaultdict(Decimal)
    for payer in payload.payers:
        paid[payer.member_id] += payer.amount
    balances = [{"member_id": member_id, "paid": paid[member_id], "owed": owed[member_id], "balance": paid[member_id] - owed[member_id]} for member_id in sorted(paid.keys() | owed.keys(), key=str)]
    if sum((row["balance"] for row in balances), Decimal(0)) != 0:
        raise ValueError("Balance reconciliation failed")
    return {"allocation_version": "minor-units-v1", "allocations": allocations, "balances": balances}


def _validated_source(session: Session, user_id: uuid.UUID, payload: ExpenseInput) -> ReceiptDocument | None:
    if not payload.source_receipt_id:
        return None
    receipt = session.scalar(select(ReceiptDocument).where(ReceiptDocument.id == payload.source_receipt_id, ReceiptDocument.owner_user_id == user_id))
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    if receipt.status != "confirmed":
        raise HTTPException(409, "Confirm the reviewed receipt before confirming the group expense")
    from .receipts import ReceiptCandidate
    candidate = ReceiptCandidate.model_validate_json(receipt.candidate_json)
    if candidate.total != payload.total or candidate.currency != payload.currency or candidate.document_date != payload.expense_date:
        raise HTTPException(422, "Receipt provenance must match the expense total, currency, and date")
    return receipt


@router.post("", response_model=GroupRead, status_code=201)
def create_group(payload: GroupCreate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    group = ExpenseGroup(name=payload.name, default_currency=payload.default_currency)
    session.add(group); session.flush()
    session.add(GroupMember(group_id=group.id, linked_user_id=user.id, display_name=payload.owner_name, role=GroupRole.owner))
    session.add(AuditEvent(actor_user_id=user.id, action="group.created", target_type="expense_group", target_id=str(group.id)))
    session.commit(); session.refresh(group)
    return group


@router.get("")
def list_groups(include_archived: bool = Query(False), user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    query = select(ExpenseGroup, GroupMember).join(GroupMember).where(GroupMember.linked_user_id == user.id, GroupMember.active.is_(True))
    if not include_archived:
        query = query.where(ExpenseGroup.archived_at.is_(None))
    rows = session.execute(query.order_by(ExpenseGroup.created_at.desc())).all()
    return [group_payload(session, group, member) for group, member in rows]


def group_payload(session: Session, group: ExpenseGroup, current_member: GroupMember | None = None) -> dict:
    members = session.scalars(select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.active.is_(True)).order_by(GroupMember.created_at)).all()
    from .group_finance import calculate_balances
    outstanding = defaultdict(Decimal)
    for row in calculate_balances(session, group.id):
        if row["balance"] > 0:
            outstanding[row["currency"]] += row["balance"]
    latest = session.scalar(select(func.max(SharedExpense.created_at)).where(SharedExpense.group_id == group.id))
    return {"id": group.id, "name": group.name, "default_currency": group.default_currency, "version": group.version, "archived": group.archived_at is not None, "current_user_role": current_member.role if current_member else None, "last_activity_at": latest, "outstanding_by_currency": outstanding, "members": [{"id": row.id, "display_name": row.display_name, "role": row.role, "is_guest": row.linked_user_id is None} for row in members]}


@router.get("/{group_id}")
def get_group(group_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    member = _membership(session, user.id, group_id)
    return group_payload(session, session.get(ExpenseGroup, group_id), member)


@router.put("/{group_id}")
def update_group(group_id: uuid.UUID, payload: GroupUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    actor = _membership(session, user.id, group_id)
    if actor.role != GroupRole.owner:
        raise HTTPException(403, "Only the group owner can change group settings")
    group = session.scalar(select(ExpenseGroup).where(ExpenseGroup.id == group_id).with_for_update())
    if group.version != payload.expected_version:
        raise HTTPException(409, "The group changed; refresh and try again")
    if payload.name is not None:
        group.name = payload.name
    if payload.archived is not None:
        group.archived_at = datetime.now(timezone.utc) if payload.archived else None
    group.version += 1
    action = "group.archived" if payload.archived else "group.restored" if payload.archived is False else "group.updated"
    session.add(AuditEvent(actor_user_id=user.id, action=action, target_type="expense_group", target_id=str(group.id)))
    session.commit(); session.refresh(group)
    return group_payload(session, group, actor)


@router.post("/{group_id}/members", status_code=201)
def add_member(group_id: uuid.UUID, payload: MemberCreate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    actor = _membership(session, user.id, group_id)
    if actor.role != GroupRole.owner:
        raise HTTPException(403, "Only group owners can add members")
    if payload.linked_user_id:
        raise HTTPException(503, "Registered-user invitations are disabled until secure acceptance is configured")
    group = session.scalar(select(ExpenseGroup).where(ExpenseGroup.id == group_id).with_for_update()); group.version += 1
    member = GroupMember(group_id=group_id, linked_user_id=payload.linked_user_id, guest_name=None if payload.linked_user_id else payload.display_name, display_name=payload.display_name)
    session.add(member); session.add(AuditEvent(actor_user_id=user.id, action="group.member_added", target_type="expense_group", target_id=str(group_id)))
    session.commit(); session.refresh(member)
    return {"id": member.id, "display_name": member.display_name, "role": member.role, "is_guest": member.linked_user_id is None}


@router.post("/{group_id}/expenses/preview", response_model=PreviewRead)
def preview_expense(group_id: uuid.UUID, payload: ExpenseInput, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    try:
        return preview(session, group_id, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{group_id}/expenses", response_model=ConfirmedRead, status_code=201)
def confirm_expense(group_id: uuid.UUID, payload: ExpenseInput, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    try:
        result = preview(session, group_id, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = session.scalar(select(SharedExpense).where(SharedExpense.group_id == group_id, SharedExpense.idempotency_key == payload.idempotency_key))
    if existing:
        return {"id": existing.id, "state": existing.state, **result}
    group = session.scalar(select(ExpenseGroup).where(ExpenseGroup.id == group_id).with_for_update())
    if group.archived_at is not None:
        raise HTTPException(409, "Archived groups cannot accept new expenses")
    receipt = _validated_source(session, user.id, payload)
    category_ids = {component.category_id for component in payload.components if component.category_id} | ({payload.category_id} if payload.category_id else set())
    if category_ids:
        from .classification import category_for_owner
        if any(not category_for_owner(session, user.id, category_id) for category_id in category_ids):
            raise HTTPException(422, "An expense category is unavailable")
    if receipt and session.scalar(select(SharedExpense.id).where(SharedExpense.source_receipt_id == receipt.id)):
        raise HTTPException(409, "This receipt is already linked to a group expense")
    group.version += 1
    expense = SharedExpense(group_id=group_id, creator_user_id=user.id, description=payload.description, total=payload.total, currency=payload.currency, expense_date=payload.expense_date, idempotency_key=payload.idempotency_key, category_id=payload.category_id, source_receipt_id=receipt.id if receipt else None, linked_transaction_id=receipt.linked_transaction_id if receipt else None)
    session.add(expense); session.flush()
    for payer in payload.payers:
        session.add(ExpensePayer(expense_id=expense.id, member_id=payer.member_id, amount=payer.amount))
    components = []
    for component in payload.components:
        row = ExpenseComponent(expense_id=expense.id, label=component.label, amount=component.amount, strategy=component.strategy, category_id=component.category_id)
        session.add(row); session.flush(); components.append(row)
    for allocation in result["allocations"]:
        session.add(ExpenseAllocation(expense_id=expense.id, component_id=components[allocation["component_index"]].id, member_id=allocation["member_id"], input_value=allocation["input_value"], unrounded_amount=allocation["unrounded_amount"], amount=allocation["amount"], received_residual=allocation["received_residual"]))
    session.add(AuditEvent(actor_user_id=user.id, action="shared_expense.confirmed", target_type="shared_expense", target_id=str(expense.id)))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(SharedExpense).where(SharedExpense.group_id == group_id, SharedExpense.idempotency_key == payload.idempotency_key))
        if not existing:
            raise
        expense = existing
    return {"id": expense.id, "state": expense.state, **result}


@router.get("/{group_id}/balances", response_model=list[GroupBalanceRead])
def balances(group_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    _membership(session, user.id, group_id)
    from .group_finance import calculate_balances
    return calculate_balances(session, group_id)
