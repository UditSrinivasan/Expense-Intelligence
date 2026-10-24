from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "hosted"] = "local"
    database_url: str = "sqlite:///./expense-intelligence.db"
    allow_dev_auth: bool = False
    supabase_jwks_url: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_audience: str = "authenticated"
    web_origin: str = "http://localhost:3000"
    invited_user_emails: str = ""
    feedback_admin_emails: str = ""
    rate_limit_enabled: bool = True
    database_pool_size: int = 5
    database_max_overflow: int = 2
    database_pool_recycle_seconds: int = 300
    fx_base_url: str = "https://api.frankfurter.dev/v2"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash"
    groq_model: str = "openai/gpt-oss-120b"
    openrouter_model: str = "nvidia/nemotron-3.5-super-vl:free"
    mistral_model: str = "mistral-small-latest"
    mistral_inference_enabled: bool = False
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    mistral_api_key: SecretStr | None = None
    agent_provider: Literal["gemini", "groq", "openrouter", "mistral"] = "gemini"
    agent_temperature: float = 0
    agent_max_output_tokens: int = 300
    agent_timeout_seconds: int = 30
    agent_total_timeout_seconds: int = 60
    agent_max_retries: int = 0
    agent_mode: Literal["disabled", "synthetic_developer"] = "disabled"
    agent_max_steps: int = 8
    agent_history_messages: int = 12

    @field_validator("allow_dev_auth")
    @classmethod
    def dev_auth_is_never_hosted(cls, value: bool, info):
        if value and info.data.get("app_env") == "hosted":
            raise ValueError("ALLOW_DEV_AUTH cannot be enabled in hosted environments")
        return value

    @field_validator("agent_mode")
    @classmethod
    def synthetic_agent_is_local_only(cls, value: str, info):
        if value == "synthetic_developer" and info.data.get("app_env") == "hosted":
            raise ValueError("Synthetic developer agent cannot run in hosted environments")
        return value

    @model_validator(mode="after")
    def hosted_security_is_explicit(self):
        if self.app_env != "hosted":
            return self
        lowered_url = self.database_url.lower()
        secure_ssl_modes = ("sslmode=require", "sslmode=verify-ca", "sslmode=verify-full")
        if not lowered_url.startswith("postgresql+") or not any(mode in lowered_url for mode in secure_ssl_modes):
            raise ValueError("Hosted DATABASE_URL must use PostgreSQL with an enforced SSL mode")
        if not self.invited_email_set:
            raise ValueError("INVITED_USER_EMAILS must contain at least one address in hosted environments")
        if not self.supabase_jwks_url or not self.supabase_jwt_issuer:
            raise ValueError("Hosted Supabase JWT configuration is incomplete")
        if self.database_pool_size > 5 or self.database_max_overflow > 2:
            raise ValueError("Hosted database pool exceeds the five-user demo limit")
        return self

    @property
    def invited_email_set(self) -> frozenset[str]:
        return frozenset(value.strip().casefold() for value in self.invited_user_emails.split(",") if value.strip())

    @property
    def feedback_admin_email_set(self) -> frozenset[str]:
        return frozenset(value.strip().casefold() for value in self.feedback_admin_emails.split(",") if value.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
