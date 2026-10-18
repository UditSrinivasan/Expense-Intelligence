import re
import unicodedata
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent, Category, ClassificationRule, ClassificationSource, Merchant, MerchantAlias, Transaction, TransactionAllocation, TransactionDirection, TransactionType
from .schemas import BulkCategorizationPreview, BulkCategorizationRequest, CategorizeTransaction, CategoryCreate, CategorySpendRead, CategoryUpdate
from .taxonomy import DEFAULT_TAXONOMY

_SPACE = re.compile(r"\s+")


def normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return _SPACE.sub(" ", "".join(character if character.isalnum() else " " for character in normalized))


def slugify(value: str) -> str:
    return normalize_label(value).replace(" ", "-")


def seed_taxonomy(session: Session) -> None:
    order = 0
    for parent_name, children in DEFAULT_TAXONOMY.items():
        parent = session.scalar(select(Category).where(Category.owner_user_id.is_(None), Category.slug == slugify(parent_name)))
        if parent is None:
            parent = Category(slug=slugify(parent_name), name=parent_name, sort_order=order)
            session.add(parent); session.flush()
        for child_order, child_name in enumerate(children):
            if session.scalar(select(Category.id).where(Category.owner_user_id.is_(None), Category.slug == slugify(child_name))) is None:
                session.add(Category(parent_id=parent.id, slug=slugify(child_name), name=child_name, sort_order=child_order))
        order += 1
    session.commit()


def available_categories(session: Session, owner_id: uuid.UUID) -> list[Category]:
    return list(session.scalars(select(Category).where(Category.active.is_(True), (Category.owner_user_id.is_(None) | (Category.owner_user_id == owner_id))).order_by(Category.sort_order, Category.name)).all())


def create_custom_category(session: Session, owner_id: uuid.UUID, payload: CategoryCreate) -> Category:
    if payload.parent_id and not session.scalar(select(Category.id).where(Category.id == payload.parent_id, Category.active.is_(True), (Category.owner_user_id.is_(None) | (Category.owner_user_id == owner_id)))):
        raise LookupError("Parent category not found")
    slug = slugify(payload.name)
    if session.scalar(select(Category.id).where(Category.owner_user_id == owner_id, Category.slug == slug)):
        raise ValueError("A custom category with this name already exists")
    row = Category(owner_user_id=owner_id, slug=slug, name=payload.name, parent_id=payload.parent_id, description=payload.description, icon=payload.icon, market="CUSTOM")
    session.add(row); session.flush()
    session.add(AuditEvent(actor_user_id=owner_id, action="category.created", target_type="category", target_id=str(row.id)))
    session.commit(); session.refresh(row)
    return row


def update_custom_category(session: Session, owner_id: uuid.UUID, category_id: uuid.UUID, payload: CategoryUpdate) -> Category:
    row = session.scalar(select(Category).where(Category.id == category_id, Category.owner_user_id == owner_id))
    if not row:
        raise LookupError("Custom category not found")
    values = payload.model_dump(exclude_none=True)
    if "name" in values:
        slug = slugify(values["name"])
        if session.scalar(select(Category.id).where(Category.owner_user_id == owner_id, Category.slug == slug, Category.id != row.id)):
            raise ValueError("A custom category with this name already exists")
        row.slug = slug
    for key, value in values.items():
        setattr(row, key, value)
    row.version += 1
    session.add(AuditEvent(actor_user_id=owner_id, action="category.updated", target_type="category", target_id=str(row.id)))
    session.commit(); session.refresh(row)
    return row


def category_for_owner(session: Session, owner_id: uuid.UUID, category_id: uuid.UUID) -> Category | None:
    return session.scalar(select(Category).where(Category.id == category_id, Category.active.is_(True), (Category.owner_user_id.is_(None) | (Category.owner_user_id == owner_id))))


def matching_rule(session: Session, owner_id: uuid.UUID, normalized_description: str) -> ClassificationRule | None:
    alias = session.scalar(select(MerchantAlias).where(MerchantAlias.owner_user_id == owner_id, MerchantAlias.normalized_alias == normalized_description))
    match_type, match_value = ("merchant_id", str(alias.merchant_id)) if alias else ("exact_normalized_description", normalized_description)
    rules = list(session.scalars(select(ClassificationRule).where(ClassificationRule.owner_user_id == owner_id, ClassificationRule.active.is_(True), ClassificationRule.match_type == match_type, ClassificationRule.match_value == match_value).order_by(ClassificationRule.precedence.desc())).all())
    if not rules or (len(rules) > 1 and rules[0].precedence == rules[1].precedence and rules[0].category_id != rules[1].category_id):
        return None
    return rules[0]


def apply_rule(session: Session, transaction: Transaction) -> None:
    if transaction.transaction_type != TransactionType.purchase or not transaction.normalized_description:
        return
    rule = matching_rule(session, transaction.owner_user_id, transaction.normalized_description)
    if not rule or not category_for_owner(session, transaction.owner_user_id, rule.category_id):
        return
    transaction.category_id = rule.category_id
    if rule.match_type == "merchant_id":
        transaction.merchant_id = uuid.UUID(rule.match_value)
    transaction.category = session.get(Category, rule.category_id).name
    transaction.classification_source = ClassificationSource.user_rule
    transaction.classification_confidence = rule.confidence
    transaction.needs_review = False
    rule.last_matched_at = datetime.now(timezone.utc)
    session.add(TransactionAllocation(owner_user_id=transaction.owner_user_id, transaction_id=transaction.id, category_id=rule.category_id, amount=transaction.original_amount, currency=transaction.original_currency, source=ClassificationSource.user_rule, confidence=rule.confidence))


def categorize_transaction(session: Session, owner_id: uuid.UUID, transaction_id: uuid.UUID, payload: CategorizeTransaction, commit: bool = True):
    transaction = session.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.owner_user_id == owner_id))
    if not transaction:
        raise LookupError("Transaction not found")
    if not ((transaction.transaction_type == TransactionType.purchase and transaction.direction == TransactionDirection.expense) or (transaction.transaction_type == TransactionType.refund and transaction.direction == TransactionDirection.income)):
        raise ValueError("Only purchase expenses and refunds can receive spending allocations")
    total = sum((item.amount for item in payload.allocations), Decimal("0"))
    if total != transaction.original_amount:
        raise ValueError("Allocations must exactly equal the transaction amount")
    for item in payload.allocations:
        if not category_for_owner(session, owner_id, item.category_id):
            raise LookupError("Category not found")
    session.query(TransactionAllocation).filter(TransactionAllocation.transaction_id == transaction.id, TransactionAllocation.current.is_(True)).update({"current": False})
    rows = [TransactionAllocation(owner_user_id=owner_id, transaction_id=transaction.id, category_id=item.category_id, amount=item.amount, currency=transaction.original_currency, source=ClassificationSource.manual, confidence=1.0) for item in payload.allocations]
    session.add_all(rows)
    transaction.category_id = payload.allocations[0].category_id if len(payload.allocations) == 1 else None
    transaction.category = session.get(Category, payload.allocations[0].category_id).name if len(payload.allocations) == 1 else "Mixed"
    transaction.classification_source = ClassificationSource.manual
    transaction.classification_confidence = 1.0
    transaction.needs_review = False
    rule = None
    if payload.create_future_rule:
        if len(payload.allocations) != 1:
            raise ValueError("Future rules require one category")
        normalized = transaction.normalized_description or normalize_label(transaction.description)
        merchant = session.scalar(select(Merchant).where(Merchant.owner_user_id == owner_id, Merchant.normalized_name == normalized))
        if merchant is None:
            merchant = Merchant(owner_user_id=owner_id, display_name=transaction.description, normalized_name=normalized)
            session.add(merchant); session.flush()
            session.add(MerchantAlias(owner_user_id=owner_id, merchant_id=merchant.id, raw_alias=transaction.raw_description or transaction.description, normalized_alias=normalized))
        transaction.merchant_id = merchant.id
        rule = ClassificationRule(owner_user_id=owner_id, match_type="merchant_id", match_value=str(merchant.id), category_id=payload.allocations[0].category_id, precedence=100, confidence=1.0, evidence_count=1)
        session.add(rule); session.flush()
        session.add(AuditEvent(actor_user_id=owner_id, action="classification_rule.created", target_type="classification_rule", target_id=str(rule.id)))
    session.add(AuditEvent(actor_user_id=owner_id, action="transaction.categorized", target_type="transaction", target_id=str(transaction.id)))
    if commit:
        session.commit()
    return transaction, rows, rule


def preview_bulk_categorization(session: Session, owner_id: uuid.UUID, payload: BulkCategorizationRequest) -> BulkCategorizationPreview:
    category = category_for_owner(session, owner_id, payload.category_id)
    if not category:
        raise LookupError("Category not found")
    rows = session.scalars(select(Transaction).where(Transaction.id.in_(payload.transaction_ids), Transaction.owner_user_id == owner_id)).all()
    by_id = {row.id: row for row in rows}
    eligible: list[uuid.UUID] = []
    rejected: dict[uuid.UUID, str] = {}
    totals: dict[str, Decimal] = {}
    for transaction_id in payload.transaction_ids:
        row = by_id.get(transaction_id)
        if not row:
            rejected[transaction_id] = "Transaction not found"
        elif row.direction != TransactionDirection.expense or row.transaction_type != TransactionType.purchase:
            rejected[transaction_id] = "Only purchase expenses can be categorized"
        else:
            eligible.append(transaction_id)
            totals[row.original_currency] = totals.get(row.original_currency, Decimal("0")) + row.original_amount
    return BulkCategorizationPreview(eligible_transaction_ids=eligible, rejected=rejected, totals_by_currency=totals, category=category)


def apply_bulk_categorization(session: Session, owner_id: uuid.UUID, payload: BulkCategorizationRequest) -> list[uuid.UUID]:
    preview = preview_bulk_categorization(session, owner_id, payload)
    if preview.rejected:
        raise ValueError("Bulk correction contains unavailable or ineligible transactions")
    try:
        for transaction_id in preview.eligible_transaction_ids:
            row = session.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.owner_user_id == owner_id))
            categorize_transaction(session, owner_id, transaction_id, CategorizeTransaction(allocations=[{"category_id": payload.category_id, "amount": row.original_amount}]), commit=False)
        session.add(AuditEvent(actor_user_id=owner_id, action="transactions.bulk_categorized", target_type="category", target_id=str(payload.category_id)))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return preview.eligible_transaction_ids


def category_spend(session: Session, owner_id: uuid.UUID, currency: str, start: date, end: date) -> list[CategorySpendRead]:
    categories = available_categories(session, owner_id)
    by_id = {row.id: row for row in categories}
    totals = {row.id: Decimal("0") for row in categories}
    for allocation, transaction in spending_allocations(session, owner_id, start, end):
        if allocation.currency != currency:
            continue
        category_id, amount = allocation.category_id, allocation.amount * (-1 if transaction.transaction_type == TransactionType.refund else 1)
        cursor = category_id
        while cursor in by_id:
            totals[cursor] += Decimal(str(amount))
            cursor = by_id[cursor].parent_id
    return [CategorySpendRead(category_id=row.id, name=row.name, parent_id=row.parent_id, amount=totals[row.id], currency=currency) for row in categories if totals[row.id] != 0]


def descendant_category_ids(session: Session, owner_id: uuid.UUID, category_id: uuid.UUID) -> set[uuid.UUID]:
    categories = available_categories(session, owner_id)
    result = {category_id}
    changed = True
    while changed:
        changed = False
        for category in categories:
            if category.parent_id in result and category.id not in result:
                result.add(category.id); changed = True
    return result


def spending_allocations(session: Session, owner_id: uuid.UUID, start: date, end: date):
    return session.execute(select(TransactionAllocation, Transaction).join(Transaction, Transaction.id == TransactionAllocation.transaction_id).where(TransactionAllocation.owner_user_id == owner_id, TransactionAllocation.current.is_(True), Transaction.effective_date.between(start, end), ((Transaction.direction == TransactionDirection.expense) & (Transaction.transaction_type == TransactionType.purchase)) | ((Transaction.direction == TransactionDirection.income) & (Transaction.transaction_type == TransactionType.refund)))).all()
