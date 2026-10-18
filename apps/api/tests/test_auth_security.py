from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.security import HTTPAuthorizationCredentials

from expense_intelligence.auth import _subject_from_bearer
from expense_intelligence.config import Settings, get_settings
from expense_intelligence.main import app


ISSUER = "https://synthetic.supabase.co/auth/v1"
SUBJECT = "10000000-0000-4000-8000-000000000001"


class StaticJwks:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        return type("SigningKey", (), {"key": self.key.public_key()})()


def token(key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {"sub": SUBJECT, "iss": ISSUER, "aud": "authenticated", "iat": now, "exp": now + timedelta(minutes=5)}
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def credentials(value):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=value)


def test_supabase_jwt_requires_signature_issuer_audience_and_expiry(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr("expense_intelligence.auth._jwks_client", lambda _url: StaticJwks(key))
    settings = Settings(supabase_jwks_url="https://synthetic.invalid/jwks", supabase_jwt_issuer=ISSUER)
    assert _subject_from_bearer(credentials(token(key)), settings) == SUBJECT
    with pytest.raises(Exception) as wrong_issuer:
        _subject_from_bearer(credentials(token(key, iss="https://attacker.invalid")), settings)
    assert wrong_issuer.value.status_code == 401
    with pytest.raises(Exception) as expired:
        _subject_from_bearer(credentials(token(key, exp=datetime.now(timezone.utc) - timedelta(seconds=1))), settings)
    assert expired.value.status_code == 401


def test_hosted_auth_configuration_requires_issuer():
    with pytest.raises(Exception) as missing:
        _subject_from_bearer(credentials("not-a-token"), Settings(supabase_jwks_url="https://synthetic.invalid/jwks", supabase_jwt_issuer=None))
    assert missing.value.status_code == 503


def test_development_identity_header_is_rejected_in_hosted_mode(client):
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="hosted", allow_dev_auth=False)
    response = client.get("/v1/transactions", headers={"X-Dev-User-Id": SUBJECT})
    assert response.status_code == 401
