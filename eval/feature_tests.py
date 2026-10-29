"""Run the feature tests: expected result versus actual result for every feature and every call.

  python eval/feature_tests.py                  # free: everything that needs no AI (topic, signals, timing, score arithmetic, reports)
  python eval/feature_tests.py --ai             # also the AI features, using audits you already have saved (0 AI requests)
  python eval/feature_tests.py --ai --run-missing --max-requests 12   # audit calls that have no saved audit yet
  python eval/feature_tests.py --ai --calls call_106,call_105

Writes eval/feature_report.json and eval/feature_report.md (the Test lab page shows the same data).
Exit code 1 if any HARD check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.expectations import load_expected, load_spec  # noqa: E402
from src.audit.featuretests import run_all, to_markdown  # noqa: E402
from src.audit.llm import LLMError, gemini_gateway  # noqa: E402
from src.audit.pipeline import AuditPipeline  # noqa: E402
from src.audit.rag import get_kb  # noqa: E402
from src.audit.schemas import AuditReport  # noqa: E402
from src.audit.transcript_io import find_transcripts, load_transcript_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", action="store_true", help="include the AI features (uses saved audits)")
    ap.add_argument("--run-missing", action="store_true", help="audit calls without a saved audit (uses AI requests)")
    ap.add_argument("--max-requests", type=int, default=12)
    ap.add_argument("--calls", default="", help="comma separated call ids")
    a = ap.parse_args()

    kb = get_kb()
    expected = load_expected()
    if not expected:
        print("No expected results found. Run: python scripts/build_expectations.py")
        return 2
    spec = load_spec()
    files = [p for p in find_transcripts(ROOT / "data" / "transcripts", only_verified=True) if p.stem in expected]
    if a.calls:
        want = {c.strip() for c in a.calls.split(",")}
        files = [p for p in files if p.stem in want]

    reports = {}
    if a.ai:
        pipe = AuditPipeline(kb=kb)
        start = gemini_gateway.request_count
        for p in files:
            call, _ = load_transcript_json(p)
            cache = pipe._audit_cache_path(call)
            if cache.exists():
                reports[p.stem] = AuditReport.model_validate_json(cache.read_text(encoding="utf-8"))
            elif a.run_missing:
                if gemini_gateway.request_count - start + 2 > a.max_requests:
                    print(f"Stopping new audits: --max-requests {a.max_requests} reached.")
                    break
                try:
                    reports[p.stem] = pipe.audit_call(call)
                except LLMError as e:
                    print(f"[{p.stem}] audit failed: {str(e)[:160]}")
                    break
        missing = [p.stem for p in files if p.stem not in reports]
        if missing:
            print(f"Note: {len(missing)} call(s) have no saved audit and were skipped: {', '.join(missing)}\n")

    result = run_all(files, kb, expected, spec, reports)
    out = ROOT / "eval"
    (out / "feature_report.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    (out / "feature_report.md").write_text(to_markdown(result), encoding="utf-8")

    mark = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "skip"}
    print(f"FEATURE TESTS: {len(result['calls'])} calls, {len(result['audited_calls'])} with AI audits\n")
    for f in result["features"]:
        print(f"[{mark[f['status']]}] {f['title']}")
        for c in f["checks"]:
            print(f"        {mark[c['status']]:<5} {c['label']:<52} expected {c['expected']:>8}   actual {c['actual']}")
    diffs = [(cid, r) for cid, rows in result["rows"].items() for r in rows if not r["ok"]]
    if diffs:
        print(f"\nWHERE ACTUAL DIFFERS FROM EXPECTED ({len(diffs)}):")
        for cid, r in diffs:
            print(f"  {cid:<9} {r['feature']:<16} {r['item'][:46]:<46} expected: {r['expected'][:34]:<34} actual: {r['actual'][:40]}  [{r['level']}]")
    s = result["summary"]
    print(f"\nSUMMARY: {s.get('PASS', 0)} pass, {s.get('WARN', 0)} warn, {s.get('FAIL', 0)} fail, {s.get('SKIP', 0)} skipped. Saved to eval/feature_report.json and .md")
    return 1 if s.get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
