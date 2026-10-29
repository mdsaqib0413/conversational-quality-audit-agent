"""Audit one file from the command line.

  python scripts/audit_cli.py data/audio/call_001_stereo.mp3 --pdf
  python scripts/audit_cli.py data/transcripts/call_017.json --json
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.llm import LLMError  # noqa: E402
from src.audit.pipeline import run_audit  # noqa: E402
from src.audit.report import render_html, render_pdf  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    def progress(stage, frac, msg):
        print(f"[{frac:>4.0%}] {msg}")

    try:
        rep = run_audit(a.source, use_cache=not a.no_cache, progress=progress)
    except LLMError as e:
        print(f"\nAI step failed: {e}")
        return 2
    s = rep.scores
    print(f"\n{rep.call_id}: {s.overall}/100 grade {s.grade}  (SOP {s.sop_score}/40, policy {s.policy_score}/30, empathy {s.empathy_score}/15, communication {s.communication_score}/15)")
    for r in s.cap_reasons:
        print("  !", r)
    for r in rep.sop_results:
        if r.status in ("missed", "partial"):
            print(f"  - {r.step_id} {r.status}: {r.title}")
    for p in rep.policy_results:
        if p.verdict == "violation":
            print(f"  - {p.clause_id} {p.severity} (turn {p.turn}): {p.explanation[:140]}")
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    if a.json:
        (out / f"{rep.call_id}.json").write_text(rep.model_dump_json(indent=1), encoding="utf-8")
    if a.html:
        (out / f"{rep.call_id}.html").write_text(render_html(rep), encoding="utf-8")
    if a.pdf:
        (out / f"{rep.call_id}.pdf").write_bytes(render_pdf(rep))
    if a.json or a.html or a.pdf:
        print(f"Saved to {out}")
    print(f"API requests used: {rep.meta.llm_requests}{' (cached)' if rep.meta.cache_hit else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
