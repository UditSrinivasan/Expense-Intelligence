import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import BudgetPeriod, BudgetStatus, ClassificationSource, TransactionDirection, TransactionType


SUPPORTED_CURRENCIES = {"INR", "GBP", "USD", "EUR", "JPY", "KWD"}


class PreferenceUpdate(BaseModel):
    country_code: str = Field(pattern="^(IN|GB)$")
    locale: str = Field(pattern="^(en-IN|en-GB)$")
    home_currency: str
    display_currency: str
    time_zone: str

    @field_validator("home_currency", "display_currency")
    @classmethod
    def currency_supported(cls, value: str) -> str:
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("unsupported currency")
        return value

    @model_validator(mode="after")
    def regional_values_are_consistent(self):
        expected = {"IN": ("en-IN", "Asia/Kolkata"), "GB": ("en-GB", "Europe/London")}[self.country_code]
        if (self.locale, self.time_zone) != expected:
            raise ValueError("locale and time zone must match the selected country")
        return self


class PreferenceRead(PreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(PreferenceUpdate):
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def display_name_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display name is required")
        return value


class ProfileRead(PreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)
    display_name: str
    onboarding_completed: bool


class TransactionCreate(BaseModel):
    description: str = Field(min_length=1, max_length=280)
    category: str = Field(default="Other", min_length=1, max_length=64)
    direction: TransactionDirection
    original_amount: Decimal = Field(gt=0, max_digits=38, decimal_places=12)
    original_currency: str
    effective_date: date
    transaction_type: TransactionType = TransactionType.purchase
    account_id: uuid.UUID | None = None

    @field_validator("original_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("unsupported currency")
        return value


class TransactionRead(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    category_id: uuid.UUID | None = None
    normalized_description: str | None = None
    classification_source: ClassificationSource
    classification_confidence: float | None = None
    needs_review: bool
    account_id: uuid.UUID | None = None
    import_batch_id: uuid.UUID | None = None
    import_row_id: uuid.UUID | None = None
    posting_date: date | None = None
    source_reference: str | None = None


class DashboardSummary(BaseModel):
    currency: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    transaction_count: int


class FxConversionRead(BaseModel):
    amount: Decimal
    base_currency: str
    quote_currency: str
    rate: Decimal
    result: Decimal
    rate_date: date
    provider: str
    attribution: str
    rate_type: str = "latest_available_daily_reference"


class ChatThreadCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class ChatThreadRead(ChatThreadCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    feedback: str | None
    created_at: datetime


class AgentReply(BaseModel):
    thread_id: uuid.UUID
    message: ChatMessageRead
    tools_used: list[str]
    data_mode: str = "synthetic_demo"
    model: str


class AgentChatRequest(ChatMessageCreate):
    thread_id: uuid.UUID | None = None


class FlagRead(BaseModel):
    name: str
    enabled: bool
    description: str


class FlagUpdate(BaseModel):
    enabled: bool


class DemoMemoryWrite(BaseModel):
    preferred_currency: Literal["INR", "GBP"]
    response_style: Literal["concise", "detailed"]


class DemoMemoryRead(DemoMemoryWrite):
    id: uuid.UUID
    provenance: str
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    description: str = Field(default="", max_length=300)
    icon: str = Field(default="circle", min_length=1, max_length=40)


class CategoryRead(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    market: str
    sort_order: int
    version: int
    active: bool
    owner_user_id: uuid.UUID | None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, min_length=1, max_length=40)
    active: bool | None = None


class AllocationWrite(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=38, decimal_places=12)


class CategorizeTransaction(BaseModel):
    allocations: list[AllocationWrite] = Field(min_length=1, max_length=30)
    create_future_rule: bool = False


class AllocationRead(AllocationWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    currency: str
    source: ClassificationSource
    current: bool


class CategorizationResult(BaseModel):
    transaction: TransactionRead
    allocations: list[AllocationRead]
    rule_id: uuid.UUID | None = None


class BulkCategorizationRequest(BaseModel):
    transaction_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    category_id: uuid.UUID


class BulkCategorizationPreview(BaseModel):
    eligible_transaction_ids: list[uuid.UUID]
    rejected: dict[uuid.UUID, str]
    totals_by_currency: dict[str, Decimal]
    category: CategoryRead


class BulkCategorizationResult(BaseModel):
    updated: int
    transaction_ids: list[uuid.UUID]
    category_id: uuid.UUID


class ClassificationRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    match_type: str
    match_value: str
    category_id: uuid.UUID
    precedence: int
    confidence: float
    evidence_count: int
    version: int
    active: bool
    last_matched_at: datetime | None
    created_at: datetime
    merchant_name: str | None = None


class RuleUpdate(BaseModel):
    active: bool


class CategorySpendRead(BaseModel):
    category_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    amount: Decimal
    currency: str


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: uuid.UUID | None = None
    amount: Decimal = Field(gt=0, max_digits=38, decimal_places=12)
    currency: str
    period_type: BudgetPeriod
    start_date: date
    end_date: date
    time_zone: str = Field(min_length=1, max_length=64)
    warning_percent: Decimal = Field(default=Decimal("80"), gt=0, le=100, max_digits=5, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def budget_currency_supported(cls, value: str) -> str:
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("unsupported currency")
        return value


class BudgetUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=38, decimal_places=12)
    currency: str | None = None
    period_type: BudgetPeriod | None = None
    start_date: date | None = None
    end_date: date | None = None
    time_zone: str | None = Field(default=None, min_length=1, max_length=64)
    warning_percent: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    status: BudgetStatus | None = None

    @field_validator("currency")
    @classmethod
    def optional_budget_currency_supported(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("unsupported currency")
        return value


class BudgetRead(BudgetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: BudgetStatus
    version: int
    created_at: datetime
    updated_at: datetime


class BudgetContribution(BaseModel):
    transaction_id: uuid.UUID
    description: str
    effective_date: date
    category_id: uuid.UUID | None
    original_amount: Decimal
    original_currency: str
    converted_amount: Decimal | None
    budget_currency: str
    rate: Decimal | None
    rate_date: date | None
    rate_provider: str | None
    excluded_reason: str | None = None


class BudgetCategoryContribution(BaseModel):
    category_id: uuid.UUID
    name: str
    amount: Decimal


class BudgetEvaluation(BaseModel):
    budget: BudgetRead
    spent: Decimal
    remaining: Decimal
    over_budget: Decimal
    utilization_percent: Decimal
    warning_state: Literal["ok", "near_limit", "over_budget"]
    complete: bool
    excluded_by_currency: dict[str, Decimal]
    conversion_policy: str
    previous_period_spent: Decimal
    previous_period_difference: Decimal
    largest_subcategories: list[BudgetCategoryContribution]
    contributions: list[BudgetContribution]


class BudgetRevisionRead(BaseModel):
    id: uuid.UUID
    budget_id: uuid.UUID
    version: int
    snapshot: dict
    created_at: datetime
