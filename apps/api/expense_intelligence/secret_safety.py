import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s'\"]+"),
    re.compile(r"(?i)((?:x-goog-api-key|(?:gemini|groq|openrouter|mistral)?_?api_?key)\s*[:=]\s*)[^\s'\"]+"),
    re.compile(r"\b(?:AIza|gsk_|sk-or-v1-|mstrl_|sk-)[A-Za-z0-9_.-]{12,}\b"),
)


def redact_secrets(value: str) -> str:
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", result)
    return result
