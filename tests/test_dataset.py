"""Consistency checks for the labelled transcripts. Run after every generation: `python -m pytest tests/test_dataset.py -q`."""
import json
from pathlib import Path

import pytest

from src.audit.rag import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / "data" / "transcripts").glob("call_*.json"))
KB = KnowledgeBase(use_embeddings=False)


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_labels_are_consistent_with_dialogue(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    turns = {t["i"]: t for t in d["turns"]}
    assert [t["i"] for t in d["turns"]] == list(range(1, len(d["turns"]) + 1))
    gt = d["ground_truth"]
    for sid, status in gt["sop_steps"].items():
        assert sid in KB.by_id and status in ("followed", "partial", "missed")
    for v in gt["policy_violations"]:
        assert v["clause_id"] in KB.by_id, v
        t = turns[v["turn"]]
        assert t["speaker"] == "agent", f"violation points at a {t['speaker']} turn"
        assert v["said"] == t["text"], "`said` must be the text of the cited turn"
    if d["quality"] == "good":
        assert not gt["policy_violations"]
        assert all(s == "followed" for s in gt["sop_steps"].values())
    if "dead_air" in gt.get("gaps", []):
        assert any(t.get("pause_before_sec", 0) >= 4 for t in d["turns"])
    if "interruption" in gt.get("gaps", []):
        assert any(t.get("interrupts_previous") for t in d["turns"])


def test_violation_turn_is_the_turn_that_states_the_claim():
    """Regression for call_017: the mistake is in turn 9 (one delivery attempt), not turn 11."""
    p = ROOT / "data" / "transcripts" / "call_017.json"
    if not p.exists():
        pytest.skip("call_017 not present")
    d = json.loads(p.read_text(encoding="utf-8"))
    v = d["ground_truth"]["policy_violations"][0]
    assert v["turn"] == 9 and "one single delivery attempt" in v["said"]
