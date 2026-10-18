import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .classification import category_for_owner, normalize_label
from .database import get_db
from .models import AuditEvent, ClassificationSource, FinancialAccount, ReceiptDocument, Transaction, TransactionAllocation, TransactionDirection
from .schemas import SUPPORTED_CURRENCIES

router = APIRouter(prefix="/v1/receipts", tags=["receipts"])


class Evidence(BaseModel):
    page: int = Field(ge=1, le=20)
    text: str = Field(max_length=500)
    confidence: float = Field(ge=0, le=1)


class ReceiptItem(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_price: Decimal = Field(max_digits=38, decimal_places=12)
    line_total: Decimal = Field(max_digits=38, decimal_places=12)
    category_id: uuid.UUID | None = None
    evidence: Evidence | None = None


class ReceiptCandidate(BaseModel):
    merchant: str = Field(min_length=1, max_length=160)
    document_date: date
    currency: str
    items: list[ReceiptItem] = Field(min_length=1, max_length=100)
    discount: Decimal = Field(default=Decimal(0), max_digits=38, decimal_places=12)
    tax: Decimal = Field(default=Decimal(0), max_digits=38, decimal_places=12)
    service_charge: Decimal = Field(default=Decimal(0), max_digits=38, decimal_places=12)
    tip: Decimal = Field(default=Decimal(0), max_digits=38, decimal_places=12)
    rounding: Decimal = Field(default=Decimal(0), max_digits=38, decimal_places=12)
    total: Decimal = Field(gt=0, max_digits=38, decimal_places=12)
    confidence: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("currency")
    @classmethod
    def supported_currency(cls, value: str) -> str:
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("unsupported currency")
        return value

    @model_validator(mode="after")
    def reconciles(self):
        calculated = sum((item.line_total for item in self.items), Decimal(0)) + self.discount + self.tax + self.service_charge + self.tip + self.rounding
        if calculated != self.total:
            raise ValueError(f"receipt components reconcile to {calculated}, not {self.total}")
        return self


class ReceiptStage(BaseModel):
    idempotency_key: uuid.UUID
    account_id: uuid.UUID | None = None
    source_hash: str = Field(pattern="^[a-f0-9]{64}$")
    file_name: str = Field(min_length=1, max_length=200)
    source_format: Literal["pdf", "jpg", "png", "webp"]
    document_type: Literal["receipt", "itemized_bill", "other"]
    page_count: int = Field(ge=1, le=20)
    used_ocr: bool
    elapsed_ms: int = Field(ge=0, le=60_000)
    candidate: ReceiptCandidate


class ReceiptUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    candidate: ReceiptCandidate
    linked_transaction_id: uuid.UUID | None = None


class ReceiptConfirm(BaseModel):
    expected_version: int = Field(ge=1)
    linked_transaction_id: uuid.UUID | None = None


def _receipt(session: Session, owner_id: uuid.UUID, receipt_id: uuid.UUID, lock: bool = False) -> ReceiptDocument:
    query = select(ReceiptDocument).where(ReceiptDocument.id == receipt_id, ReceiptDocument.owner_user_id == owner_id)
    row = session.scalar(query.with_for_update() if lock else query)
    if not row:
        raise HTTPException(404, "Receipt not found")
    return row


def _matches(session: Session, owner_id: uuid.UUID, candidate: ReceiptCandidate, account_id: uuid.UUID | None) -> list[dict]:
    query = select(Transaction).where(
        Transaction.owner_user_id == owner_id,
        Transaction.direction == TransactionDirection.expense,
        Transaction.original_amount == candidate.total,
        Transaction.original_currency == candidate.currency,
        Transaction.effective_date.between(candidate.document_date - timedelta(days=3), candidate.document_date + timedelta(days=3)),
    )
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    output = []
    merchant = normalize_label(candidate.merchant)
    for row in session.scalars(query.order_by(Transaction.effective_date)).all():
        similarity = SequenceMatcher(None, merchant, row.normalized_description or normalize_label(row.description)).ratio()
        evidence = ["same amount and currency", f"date difference {abs((row.effective_date - candidate.document_date).days)} day(s)"]
        if similarity >= 0.45:
            evidence.append("merchant description is similar")
        output.append({"transaction_id": row.id, "description": row.description, "date": row.effective_date, "amount": row.original_amount, "currency": row.original_currency, "merchant_similarity": round(similarity, 3), "evidence": evidence, "suggested": similarity >= 0.45})
    return sorted(output, key=lambda item: (not item["suggested"], abs((item["date"] - candidate.document_date).days), -item["merchant_similarity"]))[:10]


def _payload(session: Session, row: ReceiptDocument) -> dict:
    candidate = ReceiptCandidate.model_validate_json(row.candidate_json)
    return {"id": row.id, "account_id": row.account_id, "linked_transaction_id": row.linked_transaction_id, "file_name": row.file_name, "source_format": row.source_format, "document_type": row.document_type, "page_count": row.page_count, "used_ocr": row.used_ocr, "elapsed_ms": row.elapsed_ms, "status": row.status, "version": row.version, "candidate": candidate.model_dump(mode="json"), "matches": _matches(session, row.owner_user_id, candidate, row.account_id), "confirmed_at": row.confirmed_at, "created_at": row.created_at}


@router.post("", status_code=201)
def stage_receipt(payload: ReceiptStage, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    existing = session.scalar(select(ReceiptDocument).where(ReceiptDocument.owner_user_id == user.id, ReceiptDocument.idempotency_key == payload.idempotency_key))
    if existing:
        return _payload(session, existing)
    if payload.account_id and not session.scalar(select(FinancialAccount.id).where(FinancialAccount.id == payload.account_id, FinancialAccount.owner_user_id == user.id, FinancialAccount.active.is_(True))):
        raise HTTPException(404, "Account not found")
    for item in payload.candidate.items:
        if item.category_id and not category_for_owner(session, user.id, item.category_id):
            raise HTTPException(422, "A receipt category is unavailable")
    row = ReceiptDocument(owner_user_id=user.id, account_id=payload.account_id, idempotency_key=payload.idempotency_key, source_hash=payload.source_hash, file_name=payload.file_name, source_format=payload.source_format, document_type=payload.document_type, extractor_version="browser-document-v1", page_count=payload.page_count, used_ocr=payload.used_ocr, elapsed_ms=payload.elapsed_ms, candidate_json=payload.candidate.model_dump_json())
    session.add(row); session.flush(); session.add(AuditEvent(actor_user_id=user.id, action="receipt.staged", target_type="receipt_document", target_id=str(row.id))); session.commit(); session.refresh(row)
    return _payload(session, row)


@router.get("")
def receipt_history(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    rows = session.scalars(select(ReceiptDocument).where(ReceiptDocument.owner_user_id == user.id).order_by(ReceiptDocument.created_at.desc()).limit(50)).all()
    return [{"id": row.id, "file_name": row.file_name, "document_type": row.document_type, "status": row.status, "linked_transaction_id": row.linked_transaction_id, "used_ocr": row.used_ocr, "created_at": row.created_at} for row in rows]


@router.get("/{receipt_id}")
def get_receipt(receipt_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    return _payload(session, _receipt(session, user.id, receipt_id))


@router.put("/{receipt_id}")
def update_receipt(receipt_id: uuid.UUID, payload: ReceiptUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    row = _receipt(session, user.id, receipt_id, True)
    if row.status != "review" or row.version != payload.expected_version:
        raise HTTPException(409, "Receipt changed or is already confirmed")
    if payload.linked_transaction_id and not session.scalar(select(Transaction.id).where(Transaction.id == payload.linked_transaction_id, Transaction.owner_user_id == user.id)):
        raise HTTPException(404, "Transaction not found")
    row.candidate_json = payload.candidate.model_dump_json(); row.linked_transaction_id = payload.linked_transaction_id; row.version += 1
    session.commit(); return _payload(session, row)


@router.post("/{receipt_id}/confirm")
def confirm_receipt(receipt_id: uuid.UUID, payload: ReceiptConfirm, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    row = _receipt(session, user.id, receipt_id, True)
    if row.status == "confirmed":
        return _payload(session, row)
    if row.version != payload.expected_version:
        raise HTTPException(409, "Receipt changed; refresh and retry")
    candidate = ReceiptCandidate.model_validate_json(row.candidate_json)
    transaction_id = payload.linked_transaction_id or row.linked_transaction_id
    if transaction_id:
        transaction = session.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.owner_user_id == user.id).with_for_update())
        if not transaction:
            raise HTTPException(404, "Transaction not found")
        if transaction.original_amount != candidate.total or transaction.original_currency != candidate.currency or abs((transaction.effective_date - candidate.document_date).days) > 3:
            raise HTTPException(422, "The selected transaction no longer matches the receipt total, currency, and date")
        allocations: dict[uuid.UUID, Decimal] = {}
        for item in candidate.items:
            if item.category_id:
                if not category_for_owner(session, user.id, item.category_id):
                    raise HTTPException(422, "A receipt category is unavailable")
                allocations[item.category_id] = allocations.get(item.category_id, Decimal(0)) + item.line_total
        if allocations and any(item.category_id is None for item in candidate.items):
            raise HTTPException(422, "Categorize every receipt item before replacing transaction allocations")
        if allocations:
            # Non-item charges follow the first reviewed item category so the ledger remains exact.
            first_category = candidate.items[0].category_id
            adjustment = candidate.total - sum(allocations.values(), Decimal(0))
            allocations[first_category] = allocations.get(first_category, Decimal(0)) + adjustment
            for allocation in session.scalars(select(TransactionAllocation).where(TransactionAllocation.transaction_id == transaction.id, TransactionAllocation.current.is_(True))).all():
                allocation.current = False
            for category_id, amount in allocations.items():
                session.add(TransactionAllocation(owner_user_id=user.id, transaction_id=transaction.id, category_id=category_id, amount=amount, currency=candidate.currency, source=ClassificationSource.manual, confidence=candidate.confidence))
            transaction.classification_source = ClassificationSource.manual; transaction.needs_review = False
        row.linked_transaction_id = transaction.id
    row.status = "confirmed"; row.confirmed_at = datetime.now(timezone.utc); row.version += 1
    session.add(AuditEvent(actor_user_id=user.id, action="receipt.confirmed", target_type="receipt_document", target_id=str(row.id))); session.commit(); session.refresh(row)
    return _payload(session, row)
