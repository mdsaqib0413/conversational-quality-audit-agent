"""Find out which request setting your Gemini model rejects ("400 INVALID_ARGUMENT").

  python scripts/diagnose_llm.py                 # uses GEMINI_MODEL from .env
  python scripts/diagnose_llm.py --model gemini-2.5-flash
Uses about 8 tiny requests. Paste the output to your helper if the audit still fails.
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.audit.schemas import ConversationAnalysis, SegmentLabels  # noqa: E402


class Tiny(BaseModel):
    status: str


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.getenv("GEMINI_MODEL", ""))
    a = ap.parse_args()
    if not a.model or not os.getenv("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY and GEMINI_MODEL in .env first.")
        return 1
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    P = "Reply with the word ready."
    J = "Return JSON with status set to ready."
    cases = [
        ("1 plain text", P, {}),
        ("2 + temperature / max_output_tokens", P, dict(temperature=0.1, max_output_tokens=2000)),
        ("3 + system_instruction", P, dict(system_instruction="You are terse.", max_output_tokens=2000)),
        ("4 + thinking_budget=0", P, dict(max_output_tokens=2000, thinking_config=types.ThinkingConfig(thinking_budget=0))),
        ("5 + JSON mime type only", J, dict(response_mime_type="application/json", max_output_tokens=2000)),
        ("6 + tiny response_schema", J, dict(response_mime_type="application/json", response_schema=Tiny, max_output_tokens=2000)),
        ("7 + speaker-label schema (small)", "Label: [0] Thank you for calling. [1] My order is late. Return labels i=0,1.",
         dict(response_mime_type="application/json", response_schema=SegmentLabels, max_output_tokens=2000)),
        ("8 + big audit schema (ConversationAnalysis)", "Return an analysis of: agent greets, customer complains about a late order. Use empty lists where unsure.",
         dict(response_mime_type="application/json", response_schema=ConversationAnalysis, max_output_tokens=4000)),
    ]
    print(f"Model: {a.model}\n")
    fails = []
    for name, prompt, cfg in cases:
        try:
            r = client.models.generate_content(model=a.model, contents=prompt, config=types.GenerateContentConfig(**cfg))
            print(f"[ OK ] {name}: {(r.text or '')[:50]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: {str(e)[:220]}")
            fails.append(name)
        time.sleep(2)
    print()
    if not fails:
        print("Everything works. If the app still fails, send me the app's error text.")
    else:
        print("Rejected settings:", "; ".join(fails))
        print("The app already works around 4 (thinking) and 6/7/8 (schema) automatically; if 1-3 or 5 fail, the model name or key is the problem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
