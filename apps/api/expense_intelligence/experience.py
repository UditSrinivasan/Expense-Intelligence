import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .database import get_db
from .group_finance import simplify_debts
from .models import Budget, ChatMessage, GroupMember, ImportBatch, ProductFeedback, ReceiptDocument, SharedExpense, Transaction, UserPreference
from .schemas import ExperienceRead, ExperienceUpdate, ProductFeedbackCreate, ProductFeedbackRead
from .splitting import ComponentInput, ShareInput, _allocate

router = APIRouter(prefix="/v1", tags=["experience"])


def _has(session: Session, model, *criteria) -> bool:
    return bool(session.scalar(select(func.count()).select_from(model).where(*criteria)))


def _experience(session: Session, user: CurrentUser) -> ExperienceRead:
    preference = session.get(UserPreference, user.id)
    group_ids = select(GroupMember.group_id).where(GroupMember.linked_user_id == user.id)
    checklist = [
        {"key": "profile", "label": "Complete your profile", "href": "/settings", "completed": preference.onboarding_completed},
        {"key": "transaction", "label": "Add your first transaction", "href": "/transactions?add=true", "completed": _has(session, Transaction, Transaction.owner_user_id == user.id)},
        {"key": "import", "label": "Import a statement or scan a receipt", "href": "/imports", "completed": _has(session, ImportBatch, ImportBatch.owner_user_id == user.id) or _has(session, ReceiptDocument, ReceiptDocument.owner_user_id == user.id)},
        {"key": "budget", "label": "Create a budget", "href": "/budgets", "completed": _has(session, Budget, Budget.owner_user_id == user.id, Budget.deleted_at.is_(None))},
        {"key": "group", "label": "Create or join a group", "href": "/groups", "completed": _has(session, GroupMember, GroupMember.linked_user_id == user.id, GroupMember.active.is_(True))},
        {"key": "split", "label": "Try an expense split", "href": "/groups/tutorial", "completed": _has(session, SharedExpense, SharedExpense.group_id.in_(group_ids), SharedExpense.state == "confirmed")},
        {"key": "dashboard", "label": "Review your dashboard", "href": "/", "completed": preference.dashboard_reviewed_at is not None},
    ]
    return ExperienceRead(tour_state=preference.tour_state, tour_step=preference.tour_step, checklist_dismissed=preference.checklist_dismissed, checklist=checklist)


@router.get("/experience", response_model=ExperienceRead)
def get_experience(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    return _experience(session, user)


@router.put("/experience", response_model=ExperienceRead)
def update_experience(payload: ExperienceUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    preference = session.get(UserPreference, user.id)
    changes = payload.model_dump(exclude_none=True)
    dashboard_reviewed = changes.pop("dashboard_reviewed", None)
    for key, value in changes.items():
        setattr(preference, key, value)
    if dashboard_reviewed:
        preference.dashboard_reviewed_at = datetime.now(timezone.utc)
    session.commit()
    return _experience(session, user)


@router.post("/feedback", response_model=ProductFeedbackRead, status_code=201)
def submit_feedback(payload: ProductFeedbackCreate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if payload.kind == "assistant" and payload.target_id:
        try:
            message_id = uuid.UUID(payload.target_id)
        except ValueError as exc:
            raise HTTPException(422, "Invalid assistant message") from exc
        message = session.scalar(select(ChatMessage).where(ChatMessage.id == message_id, ChatMessage.owner_user_id == user.id, ChatMessage.role == "assistant"))
        if not message:
            raise HTTPException(404, "Assistant message not found")
        message.feedback = payload.sentiment
    row = ProductFeedback(owner_user_id=user.id, **payload.model_dump())
    session.add(row)
    session.commit()
    return ProductFeedbackRead(id=row.id)


@router.get("/tutorials/five-friends-split")
def five_friends_split(_: CurrentUser = Depends(get_current_user)):
    names = ["Asha", "Ben", "Chitra", "Dev", "Ella"]
    ids = {name: uuid.uuid5(uuid.NAMESPACE_URL, f"expense-intelligence-tutorial:{name}") for name in names}
    items = [
        ("Shared starters", Decimal("900"), names, "Shared equally by everyone"),
        ("Chicken mains", Decimal("1200"), names[:3], "Only the three diners who ordered them"),
        ("Wine", Decimal("1500"), names[:2], "Non-drinkers are excluded"),
        ("Desserts", Decimal("600"), names[2:], "Shared by the three people who ordered dessert"),
    ]
    owed = {name: Decimal("0") for name in names}
    breakdown = []
    for label, amount, participants, rule in items:
        component = ComponentInput(label=label, amount=amount, strategy="equal", shares=[ShareInput(member_id=ids[name]) for name in participants])
        rows = _allocate(component, Decimal("0.01"))
        allocations = []
        for row in rows:
            name = next(item for item in names if ids[item] == row["member_id"])
            owed[name] += row["amount"]
            allocations.append({"name": name, "amount": row["amount"]})
        breakdown.append({"label": label, "amount": amount, "rule": rule, "allocations": allocations})
    subtotal = sum(owed.values(), Decimal("0"))
    adjustments = [("Service charge", Decimal("420")), ("Tax", Decimal("378")), ("Discount", Decimal("-200"))]
    for label, amount in adjustments:
        component = ComponentInput(label=label, amount=amount, strategy="weighted", shares=[ShareInput(member_id=ids[name], value=owed[name]) for name in names])
        rows = _allocate(component, Decimal("0.01"))
        allocations = []
        for row in rows:
            name = next(item for item in names if ids[item] == row["member_id"])
            owed[name] += row["amount"]
            allocations.append({"name": name, "amount": row["amount"]})
        breakdown.append({"label": label, "amount": amount, "rule": "Allocated in proportion to item consumption", "allocations": allocations})
    paid = {"Asha": Decimal("3000"), "Ben": Decimal("0"), "Chitra": Decimal("0"), "Dev": Decimal("1798"), "Ella": Decimal("0")}
    balances = [{"member_id": ids[name], "display_name": name, "currency": "INR", "paid": paid[name], "owed": owed[name], "balance": paid[name] - owed[name]} for name in names]
    return {
        "label": "Tutorial example — never saved to your ledger",
        "currency": "INR",
        "subtotal": subtotal,
        "total": sum(owed.values(), Decimal("0")),
        "participants": [{"name": name, "paid": paid[name], "consumed": owed[name], "balance": paid[name] - owed[name]} for name in names],
        "components": breakdown,
        "settlements": simplify_debts(balances),
        "reconciled": sum(paid.values(), Decimal("0")) == sum(owed.values(), Decimal("0")),
    }
