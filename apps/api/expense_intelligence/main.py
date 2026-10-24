import uuid
import json
from datetime import date
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .budgets import create_budget, delete_budget, evaluate_budget, owned_budget, update_budget
from .config import get_settings
from .database import get_db
from .chat import chat, list_messages, list_threads
from .classification import apply_bulk_categorization, available_categories, categorize_transaction, category_spend, create_custom_category, preview_bulk_categorization, seed_taxonomy, update_custom_category
from .flags import FlagName, is_enabled
from .models import AuditEvent, Budget, BudgetRevision, BudgetStatus, ClassificationRule, FeatureFlag, Merchant, UserMemory, UserPreference
from .schemas import AgentChatRequest, AgentReply, BudgetCreate, BudgetEvaluation, BudgetRead, BudgetRevisionRead, BudgetUpdate, BulkCategorizationPreview, BulkCategorizationRequest, BulkCategorizationResult, CategorizationResult, CategorizeTransaction, CategoryCreate, CategoryRead, CategorySpendRead, CategoryUpdate, ChatMessageRead, ChatThreadRead, ClassificationRuleRead, DashboardSummary, DemoMemoryRead, DemoMemoryWrite, FlagRead, FlagUpdate, FxConversionRead, PreferenceRead, PreferenceUpdate, ProfileRead, ProfileUpdate, RuleUpdate, TransactionCreate, TransactionRead
from .services import FxService, create_transaction, dashboard_summary, list_transactions, update_preferences
from .splitting import router as groups_router
from .group_finance import router as group_finance_router
from .ingestion import router as ingestion_router
from .receipts import router as receipts_router
from .analytics import router as analytics_router
from .agent.providers import selected_model


settings = get_settings()
app = FastAPI(title="Expense Intelligence API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"] + (["X-Dev-User-Id"] if settings.app_env in {"local", "test"} and settings.allow_dev_auth else []),
)
app.include_router(groups_router)
app.include_router(group_finance_router)
app.include_router(ingestion_router)
app.include_router(receipts_router)
app.include_router(analytics_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/v1/preferences", response_model=PreferenceRead)
def get_preferences(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    return session.get(UserPreference, user.id)


@app.put("/v1/preferences", response_model=PreferenceRead)
def put_preferences(
    payload: PreferenceUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return update_preferences(session, user.id, payload)


@app.get("/v1/profile", response_model=ProfileRead)
def get_profile(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    return session.get(UserPreference, user.id)


@app.put("/v1/profile", response_model=ProfileRead)
def put_profile(payload: ProfileUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    preference = session.get(UserPreference, user.id)
    for key, value in payload.model_dump().items():
        setattr(preference, key, value)
    preference.onboarding_completed = True
    session.add(AuditEvent(actor_user_id=user.id, action="profile.updated", target_type="user_preference", target_id=str(user.id)))
    session.commit()
    session.refresh(preference)
    return preference


@app.post("/v1/transactions", response_model=TransactionRead, status_code=201)
def post_transaction(
    payload: TransactionCreate,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return create_transaction(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/v1/transactions", response_model=list[TransactionRead])
def get_transactions(
    limit: int = Query(50, ge=1, le=500),
    query: str | None = Query(None, max_length=120),
    currency: str | None = Query(None, pattern="^(INR|GBP|USD|EUR|JPY|KWD)$"),
    account_id: uuid.UUID | None = None,
    start: date | None = None,
    end: date | None = None,
    transaction_type: str | None = Query(None, pattern="^(purchase|income|refund|transfer)$"),
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if start and end and start > end:
        raise HTTPException(422, "Start date must not be after end date")
    from .models import TransactionType
    return list_transactions(session, user.id, limit, query=query, currency=currency, account_id=account_id, start=start, end=end, transaction_type=TransactionType(transaction_type) if transaction_type else None)


@app.get("/v1/categories", response_model=list[CategoryRead])
def get_categories(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    seed_taxonomy(session)
    return available_categories(session, user.id)


@app.post("/v1/categories", response_model=CategoryRead, status_code=201)
def post_category(payload: CategoryCreate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    seed_taxonomy(session)
    try:
        return create_custom_category(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.put("/v1/categories/{category_id}", response_model=CategoryRead)
def put_category(category_id: uuid.UUID, payload: CategoryUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        return update_custom_category(session, user.id, category_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.put("/v1/transactions/{transaction_id}/categorization", response_model=CategorizationResult)
def put_categorization(transaction_id: uuid.UUID, payload: CategorizeTransaction, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    seed_taxonomy(session)
    try:
        transaction, allocations, rule = categorize_transaction(session, user.id, transaction_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return CategorizationResult(transaction=transaction, allocations=allocations, rule_id=rule.id if rule else None)


@app.post("/v1/transactions/bulk-categorization/preview", response_model=BulkCategorizationPreview)
def post_bulk_categorization_preview(payload: BulkCategorizationRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    seed_taxonomy(session)
    try:
        return preview_bulk_categorization(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/transactions/bulk-categorization/apply", response_model=BulkCategorizationResult)
def post_bulk_categorization_apply(payload: BulkCategorizationRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        updated = apply_bulk_categorization(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return BulkCategorizationResult(updated=len(updated), transaction_ids=updated, category_id=payload.category_id)


@app.get("/v1/classification-rules", response_model=list[ClassificationRuleRead])
def get_classification_rules(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    rules = session.scalars(select(ClassificationRule).where(ClassificationRule.owner_user_id == user.id).order_by(ClassificationRule.created_at.desc())).all()
    return [ClassificationRuleRead.model_validate(rule).model_copy(update={"merchant_name": session.get(Merchant, uuid.UUID(rule.match_value)).display_name if rule.match_type == "merchant_id" and session.get(Merchant, uuid.UUID(rule.match_value)) else None}) for rule in rules]


@app.put("/v1/classification-rules/{rule_id}", response_model=ClassificationRuleRead)
def put_classification_rule(rule_id: uuid.UUID, payload: RuleUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    rule = session.scalar(select(ClassificationRule).where(ClassificationRule.id == rule_id, ClassificationRule.owner_user_id == user.id))
    if not rule:
        raise HTTPException(404, "Classification rule not found")
    rule.active = payload.active; rule.version += 1
    session.add(AuditEvent(actor_user_id=user.id, action="classification_rule.updated", target_type="classification_rule", target_id=str(rule.id)))
    session.commit(); session.refresh(rule)
    merchant = session.get(Merchant, uuid.UUID(rule.match_value)) if rule.match_type == "merchant_id" else None
    return ClassificationRuleRead.model_validate(rule).model_copy(update={"merchant_name": merchant.display_name if merchant else None})


@app.delete("/v1/classification-rules/{rule_id}", status_code=204)
def delete_classification_rule(rule_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    rule = session.scalar(select(ClassificationRule).where(ClassificationRule.id == rule_id, ClassificationRule.owner_user_id == user.id))
    if not rule:
        raise HTTPException(404, "Classification rule not found")
    session.delete(rule)
    session.add(AuditEvent(actor_user_id=user.id, action="classification_rule.deleted", target_type="classification_rule", target_id=str(rule.id)))
    session.commit()


@app.get("/v1/reports/category-spend", response_model=list[CategorySpendRead])
def get_category_spend(start: date, end: date, currency: str = Query(pattern="^(INR|GBP|USD|EUR)$"), user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if start > end:
        raise HTTPException(422, "Start date must not be after end date")
    seed_taxonomy(session)
    return category_spend(session, user.id, currency, start, end)


@app.post("/v1/budgets", response_model=BudgetRead, status_code=201)
def post_budget(payload: BudgetCreate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    seed_taxonomy(session)
    try:
        return create_budget(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/v1/budgets", response_model=list[BudgetEvaluation])
def get_budgets(include_archived: bool = False, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    query = select(Budget).where(Budget.owner_user_id == user.id, Budget.deleted_at.is_(None))
    if not include_archived:
        query = query.where(Budget.status == BudgetStatus.active)
    budgets = session.scalars(query.order_by(Budget.start_date.desc(), Budget.created_at.desc())).all()
    return [evaluate_budget(session, user.id, budget) for budget in budgets]


@app.get("/v1/budgets/{budget_id}", response_model=BudgetEvaluation)
def get_budget(budget_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    budget = owned_budget(session, user.id, budget_id)
    if not budget:
        raise HTTPException(404, "Budget not found")
    return evaluate_budget(session, user.id, budget)


@app.put("/v1/budgets/{budget_id}", response_model=BudgetRead)
def put_budget(budget_id: uuid.UUID, payload: BudgetUpdate, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        return update_budget(session, user.id, budget_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/v1/budgets/{budget_id}", status_code=204)
def remove_budget(budget_id: uuid.UUID, expected_version: int = Query(ge=1), user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        delete_budget(session, user.id, budget_id, expected_version)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/v1/budgets/{budget_id}/history", response_model=list[BudgetRevisionRead])
def get_budget_history(budget_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    budget = session.scalar(select(Budget.id).where(Budget.id == budget_id, Budget.owner_user_id == user.id))
    if not budget:
        raise HTTPException(404, "Budget not found")
    rows = session.scalars(select(BudgetRevision).where(BudgetRevision.budget_id == budget_id, BudgetRevision.owner_user_id == user.id).order_by(BudgetRevision.version.desc())).all()
    return [BudgetRevisionRead(id=row.id, budget_id=row.budget_id, version=row.version, snapshot=json.loads(row.snapshot_json), created_at=row.created_at) for row in rows]


@app.get("/v1/dashboard", response_model=DashboardSummary)
def get_dashboard(
    currency: str = Query(pattern="^(INR|GBP|USD|EUR)$"),
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return dashboard_summary(session, user.id, currency)


@app.get("/v1/fx/convert", response_model=FxConversionRead)
def convert_fx(
    amount: Decimal = Query(gt=0),
    base: str = Query(pattern="^(INR|GBP|USD|EUR)$"),
    quote: str = Query(pattern="^(INR|GBP|USD|EUR)$"),
    on: date | None = None,
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return FxService(settings.fx_base_url).convert(session, amount, base, quote, on)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/v1/flags", response_model=list[FlagRead])
def get_flags(_: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    return list(session.scalars(select(FeatureFlag).order_by(FeatureFlag.name)).all())


@app.put("/v1/dev/flags/{name}", response_model=FlagRead)
def put_dev_flag(name: FlagName, payload: FlagUpdate, _: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if settings.app_env != "local" or not settings.allow_dev_auth:
        raise HTTPException(404, "Not found")
    flag = session.get(FeatureFlag, name.value)
    if not flag:
        raise HTTPException(404, "Flag not found")
    flag.enabled = payload.enabled
    session.commit()
    session.refresh(flag)
    return flag


@app.get("/v1/chat/threads", response_model=list[ChatThreadRead])
def get_chat_threads(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if not is_enabled(session, FlagName.CHAT_HISTORY):
        return []
    return list_threads(session, user.id)


@app.get("/v1/chat/threads/{thread_id}/messages", response_model=list[ChatMessageRead])
def get_chat_messages(thread_id: uuid.UUID, limit: int = Query(100, ge=1, le=200), user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if not is_enabled(session, FlagName.CHAT_HISTORY):
        return []
    return list_messages(session, user.id, thread_id, limit)


@app.post("/v1/agent/chat", response_model=AgentReply)
def post_agent_chat(payload: AgentChatRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        thread_id, message, result = chat(session, settings, user.id, payload.content, payload.thread_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return AgentReply(thread_id=thread_id, message=message, tools_used=result.tools_used, model=selected_model(settings))


@app.get("/v1/memories", response_model=list[DemoMemoryRead])
def get_memories(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if not is_enabled(session, FlagName.LONG_TERM_MEMORY):
        return []
    rows = session.scalars(select(UserMemory).where(UserMemory.owner_user_id == user.id, UserMemory.memory_type == "synthetic_demo_preference", UserMemory.deleted_at.is_(None)).order_by(UserMemory.updated_at.desc())).all()
    return [DemoMemoryRead(id=row.id, provenance=row.provenance, created_at=row.created_at, **json.loads(row.content_json)) for row in rows]


@app.post("/v1/memories", response_model=DemoMemoryRead, status_code=201)
def post_memory(payload: DemoMemoryWrite, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    if not is_enabled(session, FlagName.LONG_TERM_MEMORY):
        raise HTTPException(404, "Long-term memory is disabled")
    row = UserMemory(owner_user_id=user.id, memory_type="synthetic_demo_preference", content_json=payload.model_dump_json(), provenance="explicit_user_synthetic_demo", editable=True)
    session.add(row); session.commit(); session.refresh(row)
    return DemoMemoryRead(id=row.id, provenance=row.provenance, created_at=row.created_at, **payload.model_dump())


@app.delete("/v1/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    row = session.scalar(select(UserMemory).where(UserMemory.id == memory_id, UserMemory.owner_user_id == user.id, UserMemory.deleted_at.is_(None)))
    if not row:
        raise HTTPException(404, "Memory not found")
    row.deleted_at = datetime.now(timezone.utc); session.commit()
