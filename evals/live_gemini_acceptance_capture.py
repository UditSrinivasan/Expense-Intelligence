import json
import time
from pathlib import Path

from expense_intelligence.agent.runtime import run_agent
from expense_intelligence.config import Settings


def main():
    settings = Settings(agent_max_steps=2)
    prompts = [
        ("tool_question", "What was total synthetic spending in October 2026? Use the ledger tool and show the exact INR amount."),
        ("multi_tool", "Compare synthetic spending in September and October 2026, then identify the largest October category. Use the necessary tools and explain the increase."),
    ]
    results = []
    output = Path("evals/gemini-3.5-flash-live-capture-2026-10-18.json")
    prior_prompt = prior_response = None
    for name, prompt in prompts:
        result = run_agent(settings, prompt, [])
        results.append({"case": name, "response": result.content, "tools": result.tools_used, "model_calls": result.model_calls, "input_tokens": result.input_tokens, "output_tokens": result.output_tokens, "latency_ms": result.latency_ms})
        output.write_text(json.dumps({"model": settings.gemini_model, "results": results}, indent=2), encoding="utf-8")
        print(f"captured {name}: calls={result.model_calls}, latency_ms={result.latency_ms}", flush=True)
        prior_prompt, prior_response = prompt, result.content
        time.sleep(40)
    follow = run_agent(settings, "Which category was largest in October?", [("user", prior_prompt), ("assistant", prior_response)])
    results.append({"case": "follow_up", "response": follow.content, "tools": follow.tools_used, "model_calls": follow.model_calls, "input_tokens": follow.input_tokens, "output_tokens": follow.output_tokens, "latency_ms": follow.latency_ms})
    output.write_text(json.dumps({"model": settings.gemini_model, "results": results}, indent=2), encoding="utf-8")
    print(f"captured follow_up: calls={follow.model_calls}, latency_ms={follow.latency_ms}", flush=True)


if __name__ == "__main__":
    main()
