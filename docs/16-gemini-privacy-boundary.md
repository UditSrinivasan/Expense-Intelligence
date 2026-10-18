# Gemini integration boundary

## Current state

`GEMINI_API_KEY` is backend-only and loaded by Pydantic settings from the ignored root `.env`. The key is never included in API schemas, browser environment variables, logs or telemetry. `AGENT_MODE=disabled` remains the default.

The model-connected LangGraph registry contains only immutable synthetic fixtures. Real-ledger adapters exist in `agent/private_tools.py` and enforce ownership through a session closed over the authenticated user, but they are deliberately not imported by `runtime.py`. This structural separation prevents a configuration typo from sending real records to Gemini.

## Provider decision

As reviewed on 18 October 2026, an API key does not prove that its Cloud project has active billing. Google distinguishes paid and unpaid Gemini API processing in its [Additional Terms](https://ai.google.dev/gemini-api/terms). UK-facing API clients must use Paid Services, and private-data processing also requires product/legal approval appropriate to the application's users. Google's [billing guide](https://ai.google.dev/gemini-api/docs/billing) explains how to verify the plan, while its [zero-data-retention guide](https://ai.google.dev/gemini-api/docs/zdr) documents additional retention constraints. Therefore real financial data remains local and deterministic.

Before enabling real-ledger model access, an operator must verify all of the following outside the application:

1. The API key belongs to the intended Cloud project.
2. That project visibly has the required paid plan and active billing.
3. The applicable Gemini terms, Data Processing Addendum, retention configuration and regional requirements have been reviewed and accepted.
4. The product owner explicitly approves sending the enumerated financial fields.
5. A separate reviewed runtime mode registers the private tools; changing `.env` alone must not be enough.

No live Gemini request is part of this milestone validation.
