import pytest

from expense_intelligence.secret_safety import redact_secrets


@pytest.mark.parametrize("value", [
    "Mistral: mstrl_abcdefghijklmnopqrstuvwxyz123456",
    "Authorization: Bearer sk-or-v1-abcdefghijklmnopqrstuvwxyz",
    "GROQ_API_KEY=gsk_abcdefghijklmnopqrstuvwxyz",
    "X-goog-api-key: AIzaabcdefghijklmnopqrstuvwxyz",
    "OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnopqrstuvwxyz",
    "api_key=sk-abcdefghijklmnopqrstuvwxyz",
])
def test_supported_secret_formats_are_redacted(value):
    result = redact_secrets(value)
    assert "[REDACTED]" in result
    assert "abcdefghijklmnopqrstuvwxyz" not in result
