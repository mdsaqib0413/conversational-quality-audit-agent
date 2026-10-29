"""Ingest real call MP3s from data/audio/real_calls/ and run the audit pipeline on each.

Usage:
    python scripts/ingest_real_calls.py [--force]
"""
from __future__ import annotations

import os
import warnings

os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["GLOG_minloglevel"] = "2"
os.environ["TORCH_CPP_LOG_LEVEL"] = "ERROR"
warnings.filterwarnings("ignore")

import argparse
import logging
import sys
import time
from pathlib import Path

logging.getLogger("torch").setLevel(logging.ERROR)
logging.getLogger("faster_whisper").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.pipeline import AuditPipeline

REAL_CALLS_DIR = ROOT / "data" / "audio" / "real_calls"
CACHE_DIR = ROOT / "data" / "cache" / "audits"


def _cached_report_exists(mp3: Path) -> bool:
    stem = mp3.stem
    if not CACHE_DIR.exists():
        return False
    return any(f.name.startswith(stem + "_") for f in CACHE_DIR.glob("*.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest real call MP3s and run the audit pipeline.")
    parser.add_argument("--force", action="store_true", help="Re-run even if a cached report exists.")
    args = parser.parse_args()

    if not REAL_CALLS_DIR.exists():
        print(f"ERROR: {REAL_CALLS_DIR} does not exist.", file=sys.stderr)
        sys.exit(1)

    mp3s = sorted(REAL_CALLS_DIR.glob("*.mp3"))
    if not mp3s:
        print(f"No .mp3 files found in {REAL_CALLS_DIR}", file=sys.stderr)
        sys.exit(1)

    pipe = AuditPipeline()

    for mp3 in mp3s:
        call_id = mp3.stem
        if not args.force and _cached_report_exists(mp3):
            print(f"{call_id}  SKIPPED (cached -- pass --force to re-run)")
            continue
        t0 = time.time()
        try:
            report = pipe.audit_audio(str(mp3), call_id=call_id, use_cache=not args.force, source_set="real", policy_applicable=False)
            elapsed = time.time() - t0
            dur = report.transcript.duration_seconds
            score = report.scores.overall
            grade = report.scores.grade
            diar = report.meta.diarization_method
            print(f"{call_id}  duration={dur:.0f}s  score={score:.1f}/100  grade={grade}  diarization={diar}  time={elapsed:.1f}s")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.time() - t0
            print(f"{call_id}  ERROR after {elapsed:.1f}s: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
