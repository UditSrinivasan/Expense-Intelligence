import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TransactionDirection(str, enum.Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"


class TransactionType(str, enum.Enum):
    purchase = "purchase"
    income = "income"
    transfer = "transfer"
    refund = "refund"
    credit_card_repayment = "credit_card_repayment"
    account_movement = "account_movement"


class ClassificationSource(str, enum.Enum):
    manual = "manual"
    user_rule = "user_rule"
    merchant_history = "merchant_history"
    receipt = "receipt"
    ai_suggestion = "ai_suggestion"
    unclassified = "unclassified"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    preference: Mapped["UserPreference"] = relationship(back_populates="user", uselist=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    country_code: Mapped[str] = mapped_column(String(2), default="IN")
    locale: Mapped[str] = mapped_column(String(35), default="en-IN")
    home_currency: Mapped[str] = mapped_column(String(3), default="INR")
    display_currency: Mapped[str] = mapped_column(String(3), default="INR")
    time_zone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    tour_state: Mapped[str] = mapped_column(String(20), default="never_started")
    tour_step: Mapped[int] = mapped_column(Integer, default=0)
    checklist_dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    dashboard_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="preference")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_owner_date", "owner_user_id", "effective_date"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(280))
    raw_description: Mapped[str | None] = mapped_column(String(500))
    normalized_description: Mapped[str | None] = mapped_column(String(280), index=True)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"), index=True)
    category: Mapped[str] = mapped_column(String(64), default="Other")
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), default=TransactionType.purchase)
    classification_source: Mapped[ClassificationSource] = mapped_column(Enum(ClassificationSource), default=ClassificationSource.unclassified)
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    direction: Mapped[TransactionDirection] = mapped_column(Enum(TransactionDirection))
    original_amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    original_currency: Mapped[str] = mapped_column(String(3))
    effective_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_batches.id", ondelete="RESTRICT"), index=True)
    import_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_rows.id", ondelete="RESTRICT"), unique=True, index=True)
    posting_date: Mapped[date | None] = mapped_column(Date)
    source_reference: Mapped[str | None] = mapped_column(String(160), index=True)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "slug", name="uq_categories_owner_slug"),
        Index("ix_categories_parent_order", "parent_id", "sort_order"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300), default="")
    icon: Mapped[str] = mapped_column(String(40), default="circle")
    market: Mapped[str] = mapped_column(String(8), default="GLOBAL")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CategoryAlias(Base):
    __tablename__ = "category_aliases"
    __table_args__ = (UniqueConstraint("owner_user_id", "normalized_alias", name="uq_category_alias_owner_value"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(100))
    normalized_alias: Mapped[str] = mapped_column(String(100))


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (UniqueConstraint("owner_user_id", "normalized_name", name="uq_merchant_owner_name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="verified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MerchantAlias(Base):
    __tablename__ = "merchant_aliases"
    __table_args__ = (UniqueConstraint("owner_user_id", "normalized_alias", name="uq_merchant_alias_owner_value"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    raw_alias: Mapped[str] = mapped_column(String(280))
    normalized_alias: Mapped[str] = mapped_column(String(280))


class ClassificationRule(Base):
    __tablename__ = "classification_rules"
    __table_args__ = (Index("ix_rules_owner_match", "owner_user_id", "match_type", "match_value", "active"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_type: Mapped[str] = mapped_column(String(40))
    match_value: Mapped[str] = mapped_column(String(280))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    precedence: Mapped[int] = mapped_column(Integer, default=100)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TransactionAllocation(Base):
    __tablename__ = "transaction_allocations"
    __table_args__ = (Index("ix_allocations_transaction_current", "transaction_id", "current"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    currency: Mapped[str] = mapped_column(String(3))
    source: Mapped[ClassificationSource] = mapped_column(Enum(ClassificationSource))
    confidence: Mapped[float | None] = mapped_column(Float)
    current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BudgetStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class BudgetPeriod(str, enum.Enum):
    monthly = "monthly"
    custom = "custom"


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (Index("ix_budgets_owner_period", "owner_user_id", "start_date", "end_date"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    currency: Mapped[str] = mapped_column(String(3))
    period_type: Mapped[BudgetPeriod] = mapped_column(Enum(BudgetPeriod))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    time_zone: Mapped[str] = mapped_column(String(64))
    warning_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("80"))
    status: Mapped[BudgetStatus] = mapped_column(Enum(BudgetStatus), default=BudgetStatus.active)
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BudgetRevision(Base):
    __tablename__ = "budget_revisions"
    __table_args__ = (UniqueConstraint("budget_id", "version", name="uq_budget_revision_version"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budgets.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupRole(str, enum.Enum):
    owner = "owner"
    member = "member"


class ExpenseGroup(Base):
    __tablename__ = "expense_groups"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    default_currency: Mapped[str] = mapped_column(String(3))
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        CheckConstraint("linked_user_id IS NOT NULL OR guest_name IS NOT NULL", name="ck_group_member_identity"),
        UniqueConstraint("group_id", "linked_user_id", name="uq_group_member_linked_user"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_groups.id", ondelete="CASCADE"), index=True)
    linked_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    guest_name: Mapped[str | None] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[GroupRole] = mapped_column(Enum(GroupRole), default=GroupRole.member)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupInvitation(Base):
    __tablename__ = "group_invitations"
    __table_args__ = (Index("ix_group_invitations_group_email", "group_id", "invited_email"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_groups.id", ondelete="CASCADE"), index=True)
    guest_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("group_members.id", ondelete="RESTRICT"), index=True)
    invited_email: Mapped[str] = mapped_column(String(320))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SharedExpense(Base):
    __tablename__ = "shared_expenses"
    __table_args__ = (Index("ix_shared_expenses_group_date", "group_id", "expense_date"), UniqueConstraint("group_id", "idempotency_key", name="uq_shared_expense_idempotency"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_groups.id", ondelete="CASCADE"), index=True)
    creator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    description: Mapped[str] = mapped_column(String(280))
    total: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    currency: Mapped[str] = mapped_column(String(3))
    expense_date: Mapped[date] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(20), default="confirmed")
    allocation_version: Mapped[str] = mapped_column(String(30), default="minor-units-v1")
    idempotency_key: Mapped[uuid.UUID] = mapped_column(index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    source_receipt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("receipt_documents.id", ondelete="RESTRICT"), unique=True, index=True)
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), index=True)
    corrects_expense_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shared_expenses.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExpensePayer(Base):
    __tablename__ = "expense_payers"
    __table_args__ = (UniqueConstraint("expense_id", "member_id", name="uq_expense_payer_member"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shared_expenses.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("group_members.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))


class ExpenseComponent(Base):
    __tablename__ = "expense_components"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shared_expenses.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(160))
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    strategy: Mapped[str] = mapped_column(String(30))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30), default="largest-remainder-v1")


class ExpenseAllocation(Base):
    __tablename__ = "expense_allocations"
    __table_args__ = (UniqueConstraint("component_id", "member_id", name="uq_component_allocation_member"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shared_expenses.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_components.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("group_members.id", ondelete="RESTRICT"), index=True)
    input_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    unrounded_amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    received_residual: Mapped[bool] = mapped_column(Boolean, default=False)


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (UniqueConstraint("group_id", "idempotency_key", name="uq_settlement_idempotency"), Index("ix_settlements_group_currency", "group_id", "currency"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_groups.id", ondelete="CASCADE"), index=True)
    payer_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("group_members.id", ondelete="RESTRICT"), index=True)
    payee_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("group_members.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    currency: Mapped[str] = mapped_column(String(3))
    settlement_date: Mapped[date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    kind: Mapped[str] = mapped_column(String(20), default="payment")
    reverses_settlement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("settlements.id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SplitTemplate(Base):
    __tablename__ = "split_templates"
    __table_args__ = (UniqueConstraint("group_id", "name", name="uq_split_template_group_name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_groups.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(280))
    currency: Mapped[str] = mapped_column(String(3))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    components_json: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (UniqueConstraint("owner_user_id", "name", name="uq_financial_account_owner_name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("owner_user_id", "idempotency_key", name="uq_import_batch_idempotency"), Index("ix_import_batches_owner_created", "owner_user_id", "created_at"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(index=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_name: Mapped[str] = mapped_column(String(200))
    file_format: Mapped[str] = mapped_column(String(10))
    parser_version: Mapped[str] = mapped_column(String(40))
    mapping_version: Mapped[str] = mapped_column(String(40))
    sheet_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="review")
    version: Mapped[int] = mapped_column(Integer, default=1)
    row_count: Mapped[int] = mapped_column(Integer)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    excluded_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (UniqueConstraint("batch_id", "source_row", name="uq_import_row_source"), Index("ix_import_rows_batch_state", "batch_id", "review_state"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    candidate_json: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    review_state: Mapped[str] = mapped_column(String(20))
    duplicate_kind: Mapped[str | None] = mapped_column(String(20))
    duplicate_transaction_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    issues_json: Mapped[str] = mapped_column(Text, default="[]")


class ImportMappingProfile(Base):
    __tablename__ = "import_mapping_profiles"
    __table_args__ = (UniqueConstraint("owner_user_id", "name", name="uq_import_mapping_owner_name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    mapping_json: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReceiptDocument(Base):
    __tablename__ = "receipt_documents"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "idempotency_key", name="uq_receipt_owner_idempotency"),
        Index("ix_receipts_owner_created", "owner_user_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("financial_accounts.id", ondelete="RESTRICT"), index=True)
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(index=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_name: Mapped[str] = mapped_column(String(200))
    source_format: Mapped[str] = mapped_column(String(10))
    document_type: Mapped[str] = mapped_column(String(30))
    extractor_version: Mapped[str] = mapped_column(String(40))
    page_count: Mapped[int] = mapped_column(Integer)
    used_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer)
    candidate_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="review")
    version: Mapped[int] = mapped_column(Integer, default=1)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("provider", "base_currency", "quote_currency", "rate_date"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(40))
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    rate_date: Mapped[date] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    attribution: Mapped[str] = mapped_column(String(255))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(String(300))


class ChatThread(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (Index("ix_chat_threads_owner_updated", "owner_user_id", "updated_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_thread_created", "thread_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    feedback: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatCheckpoint(Base):
    __tablename__ = "chat_checkpoints"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True)
    workflow_version: Mapped[str] = mapped_column(String(40))
    state_json: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserMemory(Base):
    __tablename__ = "user_memories"
    __table_args__ = (Index("ix_user_memories_owner_type", "owner_user_id", "memory_type"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    memory_type: Mapped[str] = mapped_column(String(50))
    content_json: Mapped[str] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(120))
    editable: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductFeedback(Base):
    __tablename__ = "product_feedback"
    __table_args__ = (Index("ix_product_feedback_owner_created", "owner_user_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    sentiment: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InsightRecord(Base):
    __tablename__ = "insight_records"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "fingerprint", name="uq_insight_owner_fingerprint"),
        Index("ix_insights_owner_period", "owner_user_id", "period_end"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    insight_type: Mapped[str] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(3))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(200))
    explanation: Mapped[str] = mapped_column(String(600))
    evidence_json: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(12), default="info")
    status: Mapped[str] = mapped_column(String(12), default="active")
    feedback: Mapped[str | None] = mapped_column(String(12))
    algorithm_version: Mapped[str] = mapped_column(String(24), default="rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalyticsPreference(Base):
    __tablename__ = "analytics_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    sensitivity: Mapped[str] = mapped_column(String(12), default="balanced")


class RecurringDecision(Base):
    __tablename__ = "recurring_decisions"
    __table_args__ = (UniqueConstraint("owner_user_id", "series_key", name="uq_recurring_owner_series"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    series_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="suggested")
    label: Mapped[str | None] = mapped_column(String(160))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
