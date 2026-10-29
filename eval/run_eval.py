"""Evaluate the audit agent against the labelled transcripts.

Examples
  python eval/run_eval.py --no-llm                    # free: topic, step coverage, timing gaps (0 API requests)
  python eval/run_eval.py --max-requests 12           # full audit eval, stops before spending more than 12 API requests
  python eval/run_eval.py --split test --limit 6
Audits are cached, so re-running costs nothing for calls already audited.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.evaluation import evaluate_no_llm, evaluate_reports, summary_markdown, write_csv  # noqa: E402
from src.audit.llm import LLMError, QuotaExhaustedError, gemini_gateway  # noqa: E402
from src.audit.pipeline import AuditPipeline  # noqa: E402
from src.audit.rag import get_kb  # noqa: E402
from src.audit.transcript_io import find_transcripts, load_transcript_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=str(ROOT / "data" / "transcripts"))
    ap.add_argument("--split", choices=["all", "train", "test"], default="all")
    ap.add_argument("--include-unverified", action="store_true", help="also use transcripts whose verification failed")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--max-requests", type=int, default=16, help="stop before exceeding this many API requests")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    files = find_transcripts(args.folder, only_verified=not args.include_unverified)
    if args.split != "all":
        files = [p for p in files if json.loads(p.read_text(encoding="utf-8")).get("split") == args.split]
    if args.limit:
        files = files[: args.limit]
    if not files:
        print("No transcripts found (are they verified? use --include-unverified).")
        return 1
    kb = get_kb()
    out_dir = ROOT / "eval"
    stamp = time.strftime("%Y%m%d_%H%M%S")

    if args.no_llm:
        res = evaluate_no_llm(files, kb)
        md = summary_markdown(res, "Evaluation (no API requests)")
        write_csv(out_dir / f"results_nollm_{stamp}.csv", res["rows"])
        (out_dir / "summary_nollm.md").write_text(md, encoding="utf-8")
        print(md)
        return 0

    pipe = AuditPipeline(kb=kb)
    pairs, start = [], gemini_gateway.request_count
    for i, p in enumerate(files, 1):
        if gemini_gateway.request_count - start + 2 > args.max_requests:
            cached_possible = pipe._audit_cache_path(load_transcript_json(p)[0]).exists()
            if not cached_possible:
                print(f"Stopping: --max-requests {args.max_requests} reached after {len(pairs)} audits. Re-run later to continue (finished audits are cached).")
                break
        call, raw = load_transcript_json(p)
        try:
            rep = pipe.audit_call(call, use_cache=not args.no_cache)
        except QuotaExhaustedError as e:
            print(f"Daily quota exhausted after {len(pairs)} audits: {str(e)[:200]}")
            break
        except LLMError as e:
            print(f"[{call.call_id}] failed: {str(e)[:200]}")
            continue
        pairs.append((rep, raw))
        print(f"[{i}/{len(files)}] {call.call_id} {raw['quality']:<15} score {rep.scores.overall:>5} grade {rep.scores.grade} "
              f"viol {sum(1 for x in rep.policy_results if x.verdict == 'violation')}/{len(raw['ground_truth']['policy_violations'])} "
              f"requests {rep.meta.llm_requests}{' (cache)' if rep.meta.cache_hit else ''}")
    if not pairs:
        return 1
    res = evaluate_reports(pairs)
    md = summary_markdown(res)
    write_csv(out_dir / f"results_calls_{stamp}.csv", res["per_call"])
    write_csv(out_dir / f"results_steps_{stamp}.csv", res["per_step"])
    (out_dir / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Saved to eval/summary.md and eval/results_*_{stamp}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
