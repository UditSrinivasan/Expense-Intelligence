import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .models import User, UserPreference


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    auth_subject: str


bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=300)


def _subject_from_bearer(credentials: HTTPAuthorizationCredentials, settings: Settings) -> str:
    if not settings.supabase_jwks_url or not settings.supabase_jwt_issuer:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Hosted authentication is not configured")
    try:
        signing_key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        return str(payload["sub"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    dev_user_id: str | None = Header(default=None, alias="X-Dev-User-Id"),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db),
) -> CurrentUser:
    if credentials:
        subject = _subject_from_bearer(credentials, settings)
    elif settings.allow_dev_auth and settings.app_env in {"local", "test"} and dev_user_id:
        try:
            uuid.UUID(dev_user_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid development user ID") from exc
        subject = f"dev:{dev_user_id}"
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("select set_config('app.auth_subject', :subject, true)"), {"subject": subject})
    user = session.scalar(select(User).where(User.auth_subject == subject))
    if user is None:
        try:
            user = User(auth_subject=subject)
            session.add(user)
            session.flush()
            session.add(UserPreference(user_id=user.id))
            session.commit()
        except IntegrityError:
            session.rollback()
            user = session.scalar(select(User).where(User.auth_subject == subject))
            if user is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "Identity provisioning conflict; retry request")
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("select set_config('app.current_user_id', :user_id, true)"), {"user_id": str(user.id)})
    return CurrentUser(id=user.id, auth_subject=user.auth_subject)
