import hashlib
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .classification import apply_rule, category_for_owner, matching_rule, normalize_label
from .database import get_db
from .models import AuditEvent, ClassificationSource, FinancialAccount, ImportBatch, ImportMappingProfile, ImportRow, Transaction, TransactionAllocation, TransactionDirection, TransactionType
from .schemas import SUPPORTED_CURRENCIES

router = APIRouter(prefix="/v1", tags=["imports"])
MAX_ROWS = 10_000


class AccountWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency: str
    @field_validator("currency")
    @classmethod
    def currency_supported(cls, value: str) -> str:
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES: raise ValueError("unsupported currency")
        return value


class AccountRead(AccountWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class CandidateWrite(BaseModel):
    source_row: int = Field(ge=1, le=MAX_ROWS + 100)
    transaction_date: date
    posting_date: date | None = None
    description: str = Field(min_length=1, max_length=280)
    merchant: str | None = Field(default=None, max_length=160)
    direction: TransactionDirection
    transaction_type: TransactionType | None = None
    amount: Decimal = Field(gt=0, max_digits=38, decimal_places=12)
    currency: str
    reference: str | None = Field(default=None, max_length=160)
    category_id: uuid.UUID | None = None
    included: bool = True

    @field_validator("currency")
    @classmethod
    def candidate_currency(cls, value: str) -> str:
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES: raise ValueError("unsupported currency")
        return value


class StageImport(BaseModel):
    idempotency_key: uuid.UUID
    account_id: uuid.UUID
    source_hash: str = Field(pattern="^[a-f0-9]{64}$")
    file_name: str = Field(min_length=1, max_length=200)
    file_format: Literal["csv", "xlsx", "pdf"]
    sheet_name: str | None = Field(default=None, max_length=120)
    mapping: dict[str, str] = Field(default_factory=dict)
    mapping_profile_name: str | None = Field(default=None, max_length=120)
    candidates: list[CandidateWrite] = Field(min_length=1, max_length=MAX_ROWS)


class RowUpdate(BaseModel):
    expected_batch_version: int = Field(ge=1)
    included: bool | None = None
    transaction_date: date | None = None
    posting_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=280)
    direction: TransactionDirection | None = None
    transaction_type: TransactionType | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=38, decimal_places=12)
    currency: str | None = None
    reference: str | None = Field(default=None, max_length=160)
    category_id: uuid.UUID | None = None
    duplicate_action: Literal["import", "exclude"] | None = None


class ConfirmImport(BaseModel):
    expected_version: int = Field(ge=1)


def recognize_type(description: str, direction: TransactionDirection) -> tuple[TransactionType, bool, str]:
    text = normalize_label(description)
    if direction == TransactionDirection.income and any(word in text for word in ("refund", "reversal", "chargeback")): return TransactionType.refund, False, "refund marker"
    if any(word in text for word in ("own account", "self transfer")): return TransactionType.transfer, False, "own-account transfer marker"
    if any(word in text for word in ("upi", "neft", "imps", "faster payment", "bank transfer")): return TransactionType.transfer, True, "transfer rail requires review"
    if direction == TransactionDirection.income: return TransactionType.income, False, "credit direction"
    return TransactionType.purchase, False, "purchase/default debit"


def fingerprint(account_id: uuid.UUID, candidate: CandidateWrite | dict) -> str:
    get = (lambda key: getattr(candidate, key)) if not isinstance(candidate, dict) else candidate.get
    parts = [str(account_id), str(get("transaction_date")), str(get("amount")), str(get("currency")), str(get("direction")), normalize_label(str(get("description")))]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _account(session: Session, owner_id: uuid.UUID, account_id: uuid.UUID) -> FinancialAccount:
    row = session.scalar(select(FinancialAccount).where(FinancialAccount.id == account_id, FinancialAccount.owner_user_id == owner_id, FinancialAccount.active.is_(True)))
    if not row: raise HTTPException(404, "Account not found")
    return row


def _duplicate(session: Session, owner_id: uuid.UUID, account_id: uuid.UUID, candidate: CandidateWrite) -> tuple[str | None, uuid.UUID | None, list[str]]:
    if candidate.reference:
        row = session.scalar(select(Transaction).where(Transaction.owner_user_id == owner_id, Transaction.account_id == account_id, Transaction.source_reference == candidate.reference))
        if row: return "exact", row.id, ["same account and source reference"]
    normalized = normalize_label(candidate.description)
    rows = session.scalars(select(Transaction).where(Transaction.owner_user_id == owner_id, Transaction.account_id == account_id, Transaction.original_amount == candidate.amount, Transaction.original_currency == candidate.currency, Transaction.direction == candidate.direction, Transaction.effective_date.between(candidate.transaction_date - timedelta(days=3), candidate.transaction_date + timedelta(days=3)))).all()
    for row in rows:
        if row.effective_date == candidate.transaction_date and row.normalized_description == normalized: return "exact", row.id, ["same account, date, amount, currency, direction and description"]
    for row in rows:
        if row.normalized_description == normalized: return "likely", row.id, ["same account, amount, currency, direction and description within three days"]
    return None, None, []


def batch_payload(session: Session, batch: ImportBatch) -> dict:
    rows = session.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.source_row)).all()
    transaction_ids = dict(session.execute(select(Transaction.import_row_id, Transaction.id).where(Transaction.import_batch_id == batch.id)).all())
    return {"id": batch.id, "account_id": batch.account_id, "file_name": batch.file_name, "file_format": batch.file_format, "sheet_name": batch.sheet_name, "status": batch.status, "version": batch.version, "row_count": batch.row_count, "accepted_count": batch.accepted_count, "excluded_count": batch.excluded_count, "duplicate_count": batch.duplicate_count, "invalid_count": batch.invalid_count, "confirmed_at": batch.confirmed_at, "created_at": batch.created_at, "rows": [{"id": row.id, "source_row": row.source_row, **json.loads(row.candidate_json), "review_state": row.review_state, "duplicate_kind": row.duplicate_kind, "duplicate_transaction_id": row.duplicate_transaction_id, "issues": json.loads(row.issues_json), "transaction_id": transaction_ids.get(row.id)} for row in rows]}


@router.get("/accounts", response_model=list[AccountRead])
def accounts(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    return list(session.scalars(select(FinancialAccount).where(FinancialAccount.owner_user_id == user.id, FinancialAccount.active.is_(True)).order_by(FinancialAccount.name)).all())


@router.post("/accounts", response_model=AccountRead, status_code=201)
def create_account(payload: AccountWrite, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    row = FinancialAccount(owner_user_id=user.id, **payload.model_dump()); session.add(row)
    try: session.commit()
    except IntegrityError as exc: session.rollback(); raise HTTPException(409, "An account with this name already exists") from exc
    session.refresh(row); return row


@router.post("/imports/stage", status_code=201)
def stage_import(payload: StageImport, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    account = _account(session, user.id, payload.account_id)
    existing = session.scalar(select(ImportBatch).where(ImportBatch.owner_user_id == user.id, ImportBatch.idempotency_key == payload.idempotency_key))
    if existing: return batch_payload(session, existing)
    if len({row.source_row for row in payload.candidates}) != len(payload.candidates): raise HTTPException(422, "Source rows must be unique")
    parser_version = "browser-document-v1" if payload.file_format == "pdf" else "browser-tabular-v1"
    batch = ImportBatch(owner_user_id=user.id, account_id=account.id, idempotency_key=payload.idempotency_key, source_hash=payload.source_hash, file_name=payload.file_name, file_format=payload.file_format, parser_version=parser_version, mapping_version="column-map-v1", sheet_name=payload.sheet_name, row_count=len(payload.candidates))
    session.add(batch); session.flush(); duplicate_count = excluded_count = invalid_count = 0
    for candidate in payload.candidates:
        issues = []
        if candidate.currency != account.currency: issues.append(f"currency differs from account default {account.currency}")
        tx_type, ambiguous, evidence = recognize_type(candidate.description, candidate.direction)
        values = candidate.model_dump(mode="json"); values["transaction_type"] = (candidate.transaction_type or tx_type).value; values["type_evidence"] = evidence
        rule = matching_rule(session, user.id, normalize_label(candidate.merchant or candidate.description))
        if not candidate.category_id and rule: values["category_id"] = str(rule.category_id); values["classification_source"] = "user_rule"
        else: values["classification_source"] = "manual" if candidate.category_id else "unclassified"
        if values.get("category_id") and not category_for_owner(session, user.id, uuid.UUID(str(values["category_id"]))): issues.append("category is unavailable")
        kind, duplicate_id, evidence_rows = _duplicate(session, user.id, account.id, candidate); issues.extend(evidence_rows)
        state = "excluded" if not candidate.included else "needs_review" if issues or ambiguous or kind else "accepted"
        duplicate_count += int(kind is not None); excluded_count += int(state == "excluded"); invalid_count += int("category is unavailable" in issues)
        session.add(ImportRow(batch_id=batch.id, owner_user_id=user.id, source_row=candidate.source_row, candidate_json=json.dumps(values), fingerprint=fingerprint(account.id, candidate), review_state=state, duplicate_kind=kind, duplicate_transaction_id=duplicate_id, issues_json=json.dumps(issues)))
    batch.duplicate_count = duplicate_count; batch.excluded_count = excluded_count; batch.invalid_count = invalid_count; batch.accepted_count = len(payload.candidates) - excluded_count - invalid_count
    if payload.mapping_profile_name:
        profile = session.scalar(select(ImportMappingProfile).where(ImportMappingProfile.owner_user_id == user.id, ImportMappingProfile.name == payload.mapping_profile_name))
        if profile: profile.mapping_json = json.dumps(payload.mapping); profile.version += 1
        else: session.add(ImportMappingProfile(owner_user_id=user.id, name=payload.mapping_profile_name, mapping_json=json.dumps(payload.mapping)))
    session.add(AuditEvent(actor_user_id=user.id, action="import.staged", target_type="import_batch", target_id=str(batch.id))); session.commit(); session.refresh(batch); return batch_payload(session, batch)


@router.get("/imports")
def import_history(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    rows = session.scalars(select(ImportBatch).where(ImportBatch.owner_user_id == user.id).order_by(ImportBatch.created_at.desc()).limit(50)).all()
    return [{"id": row.id, "file_name": row.file_name, "file_format": row.file_format, "status": row.status, "row_count": row.row_count, "accepted_count": row.accepted_count, "excluded_count": row.excluded_count, "duplicate_count": row.duplicate_count, "invalid_count": row.invalid_count, "confirmed_at": row.confirmed_at, "created_at": row.created_at} for row in rows]


@router.get("/imports/{batch_id}")
def get_import(batch_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    batch = session.scalar(select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.owner_user_id == user.id))
    if not batch: raise HTTPException(404, "Import not found")
    return batch_payload(session, batch)


@router.put("/imports/{batch_id}/rows/{row_id}")
def update_import_row(batch_id: uuid.UUID, row_id: uuid.UUID, payload: RowUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    batch = session.scalar(select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.owner_user_id == user.id).with_for_update())
    if not batch: raise HTTPException(404, "Import not found")
    if batch.status != "review": raise HTTPException(409, "Confirmed imports cannot be edited")
    if batch.version != payload.expected_batch_version: raise HTTPException(409, "Import changed; refresh and retry")
    row = session.scalar(select(ImportRow).where(ImportRow.id == row_id, ImportRow.batch_id == batch.id, ImportRow.owner_user_id == user.id))
    if not row: raise HTTPException(404, "Import row not found")
    values = json.loads(row.candidate_json); changes = payload.model_dump(exclude_none=True); action = changes.pop("duplicate_action", None)
    for key, value in changes.items(): values[key] = value.isoformat() if isinstance(value, date) else value.value if hasattr(value, "value") else str(value) if isinstance(value, Decimal) else value
    if changes.get("included") is False or action == "exclude": row.review_state = "excluded"
    else: row.review_state = "accepted"
    row.candidate_json = json.dumps(values); batch.version += 1; session.commit(); return batch_payload(session, batch)


@router.post("/imports/{batch_id}/confirm")
def confirm_import(batch_id: uuid.UUID, payload: ConfirmImport, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    batch = session.scalar(select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.owner_user_id == user.id).with_for_update())
    if not batch: raise HTTPException(404, "Import not found")
    if batch.status == "confirmed": return batch_payload(session, batch)
    if batch.version != payload.expected_version: raise HTTPException(409, "Import changed; refresh and retry")
    rows = session.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.source_row)).all()
    blocked = [row for row in rows if row.review_state not in {"accepted", "excluded"}]
    if blocked: raise HTTPException(422, f"{len(blocked)} rows still require review")
    try:
        for row in rows:
            if row.review_state == "excluded": continue
            values = json.loads(row.candidate_json); category_id = uuid.UUID(values["category_id"]) if values.get("category_id") else None
            transaction = Transaction(owner_user_id=user.id, account_id=batch.account_id, import_batch_id=batch.id, import_row_id=row.id, description=values["description"], raw_description=values["description"], normalized_description=normalize_label(values.get("merchant") or values["description"]), category="Other", category_id=category_id, direction=TransactionDirection(values["direction"]), transaction_type=TransactionType(values["transaction_type"]), classification_source=ClassificationSource(values.get("classification_source", "unclassified")), needs_review=not bool(category_id), original_amount=Decimal(values["amount"]), original_currency=values["currency"], effective_date=date.fromisoformat(values["transaction_date"]), posting_date=date.fromisoformat(values["posting_date"]) if values.get("posting_date") else None, source_reference=values.get("reference"))
            session.add(transaction); session.flush()
            if category_id:
                category = category_for_owner(session, user.id, category_id)
                if not category: raise ValueError("Reviewed category is no longer available")
                transaction.category = category.name; transaction.needs_review = False; session.add(TransactionAllocation(owner_user_id=user.id, transaction_id=transaction.id, category_id=category_id, amount=transaction.original_amount, currency=transaction.original_currency, source=transaction.classification_source, confidence=1.0))
            else: apply_rule(session, transaction)
        batch.status = "confirmed"; batch.confirmed_at = datetime.now(timezone.utc); batch.version += 1; session.add(AuditEvent(actor_user_id=user.id, action="import.confirmed", target_type="import_batch", target_id=str(batch.id))); session.commit()
    except Exception:
        session.rollback(); raise
    return batch_payload(session, batch)
