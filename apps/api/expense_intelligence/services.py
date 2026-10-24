from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .classification import apply_rule, normalize_label
from .models import AuditEvent, FinancialAccount, FxRate, Transaction, TransactionDirection, TransactionType, UserPreference
from .schemas import DashboardSummary, FxConversionRead, PreferenceUpdate, TransactionCreate


MONEY_QUANTUM = Decimal("0.01")


def record_audit(session: Session, user_id, action: str, target_type: str, target_id: str) -> None:
    session.add(AuditEvent(actor_user_id=user_id, action=action, target_type=target_type, target_id=target_id))


def update_preferences(session: Session, user_id, update: PreferenceUpdate) -> UserPreference:
    preference = session.get(UserPreference, user_id)
    if preference is None:
        preference = UserPreference(user_id=user_id)
        session.add(preference)
    for key, value in update.model_dump().items():
        setattr(preference, key, value)
    record_audit(session, user_id, "preferences.updated", "user_preference", str(user_id))
    session.commit()
    session.refresh(preference)
    return preference


def create_transaction(session: Session, user_id, payload: TransactionCreate) -> Transaction:
    values = payload.model_dump()
    if payload.account_id and not session.scalar(select(FinancialAccount.id).where(FinancialAccount.id == payload.account_id, FinancialAccount.owner_user_id == user_id, FinancialAccount.active.is_(True))):
        raise LookupError("Financial account not found")
    if payload.direction == TransactionDirection.transfer:
        values["transaction_type"] = TransactionType.transfer
    elif payload.direction == TransactionDirection.income and payload.transaction_type == TransactionType.purchase:
        values["transaction_type"] = TransactionType.income
    transaction = Transaction(owner_user_id=user_id, raw_description=payload.description, normalized_description=normalize_label(payload.description), **values)
    session.add(transaction)
    session.flush()
    apply_rule(session, transaction)
    record_audit(session, user_id, "transaction.created", "transaction", str(transaction.id))
    session.commit()
    session.refresh(transaction)
    return transaction


def list_transactions(
    session: Session,
    user_id,
    limit: int = 50,
    *,
    query: str | None = None,
    currency: str | None = None,
    account_id=None,
    start: date | None = None,
    end: date | None = None,
    transaction_type: TransactionType | None = None,
) -> list[Transaction]:
    statement = select(Transaction).where(Transaction.owner_user_id == user_id)
    if query:
        statement = statement.where(Transaction.description.ilike(f"%{query.strip()}%"))
    if currency:
        statement = statement.where(Transaction.original_currency == currency.upper())
    if account_id:
        statement = statement.where(Transaction.account_id == account_id)
    if start:
        statement = statement.where(Transaction.effective_date >= start)
    if end:
        statement = statement.where(Transaction.effective_date <= end)
    if transaction_type:
        statement = statement.where(Transaction.transaction_type == transaction_type)
    return list(
        session.scalars(
            statement.order_by(Transaction.effective_date.desc(), Transaction.id.desc()).limit(limit)
        )
    )


def dashboard_summary(session: Session, user_id, currency: str) -> DashboardSummary:
    rows = session.execute(
        select(Transaction.direction, func.coalesce(func.sum(Transaction.original_amount), 0), func.count())
        .where(
            Transaction.owner_user_id == user_id,
            Transaction.original_currency == currency,
            ((Transaction.direction == TransactionDirection.expense) & (Transaction.transaction_type == TransactionType.purchase))
            | ((Transaction.direction == TransactionDirection.income) & (Transaction.transaction_type == TransactionType.income)),
        )
        .group_by(Transaction.direction)
    ).all()
    totals = {direction: Decimal(str(total)) for direction, total, _ in rows}
    count = sum(row_count for _, _, row_count in rows)
    income = totals.get(TransactionDirection.income, Decimal(0))
    expenses = totals.get(TransactionDirection.expense, Decimal(0))
    return DashboardSummary(currency=currency, income=income, expenses=expenses, net=income - expenses, transaction_count=count)


class FxService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def convert(
        self, session: Session, amount: Decimal, base: str, quote: str, requested_date: date | None = None
    ) -> FxConversionRead:
        if base == quote:
            rate, rate_date = Decimal(1), requested_date or date.today()
        else:
            rate_row = self._cached(session, base, quote, requested_date)
            if rate_row is None:
                rate_row = self._fetch_and_cache(session, base, quote, requested_date)
            rate, rate_date = rate_row.rate, rate_row.rate_date
        result = (amount * rate).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)
        return FxConversionRead(
            amount=amount,
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            result=result,
            rate_date=rate_date,
            provider="Frankfurter",
            attribution="Frankfurter blended rates from central banks and official sources",
        )

    @staticmethod
    def _cached(session: Session, base: str, quote: str, requested_date: date | None) -> FxRate | None:
        query = select(FxRate).where(FxRate.base_currency == base, FxRate.quote_currency == quote)
        if requested_date:
            query = query.where(FxRate.rate_date <= requested_date)
        return session.scalar(query.order_by(FxRate.rate_date.desc()).limit(1))

    def _fetch_and_cache(self, session: Session, base: str, quote: str, requested_date: date | None) -> FxRate:
        params = {"date": requested_date.isoformat()} if requested_date else {}
        try:
            response = httpx.get(f"{self.base_url}/rate/{base.lower()}/{quote.lower()}", params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            rate = Decimal(str(data["rate"]))
            rate_date = date.fromisoformat(data["date"])
        except (httpx.HTTPError, KeyError, ValueError, ArithmeticError) as exc:
            raise RuntimeError("Latest available exchange rate is unavailable") from exc
        if rate <= 0:
            raise RuntimeError("Exchange-rate provider returned an invalid rate")
        row = FxRate(
            provider="frankfurter",
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            rate_date=rate_date,
            attribution="Frankfurter blended rates from central banks and official sources",
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
