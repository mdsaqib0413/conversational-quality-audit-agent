"""Write data/expected/expected_results.json from the hand-written ground truth in data/transcripts.

  python scripts/build_expectations.py           # (re)generate
  python scripts/build_expectations.py --check   # exit 1 if the stored file is out of date
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.expectations import EXPECTED_PATH, build_all, load_expected, save_expected  # noqa: E402
from src.audit.rag import get_kb  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    new = build_all(ROOT / "data" / "transcripts", get_kb())
    if a.check:
        old = load_expected()
        if old != json.loads(json.dumps(new)):
            print("expected_results.json is out of date. Run: python scripts/build_expectations.py")
            return 1
        print(f"OK: expected_results.json is up to date ({len(new)} calls)")
        return 0
    save_expected(new)
    print(f"Wrote {EXPECTED_PATH.relative_to(ROOT)} for {len(new)} calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
