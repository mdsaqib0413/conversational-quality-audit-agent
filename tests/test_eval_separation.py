"""Tests for evaluation set separation and leakage prevention.

Ensures that no call id belonging to the 'heldout' split ever appears in:
1. Agent prompt instruction files (agents/ and prompts/)
2. Few-shot example citations
3. Threshold or heuristic configurations (scorecard/quality_config.yaml, data/rubric.yaml)
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def eval_split():
    split_path = ROOT / "eval_data" / "split.json"
    assert split_path.exists(), "eval_data/split.json must exist"
    data = json.loads(split_path.read_text(encoding="utf-8"))
    assert "dev" in data and "heldout" in data
    assert "rule" in data
    return data


def test_no_overlap_between_dev_and_heldout(eval_split):
    dev = set(eval_split["dev"])
    heldout = set(eval_split["heldout"])
    overlap = dev.intersection(heldout)
    assert not overlap, f"Dev and heldout splits must be strictly disjoint, found overlap: {overlap}"


def test_heldout_calls_never_appear_in_prompts_or_configs(eval_split):
    heldout_ids = eval_split["heldout"]
    search_dirs = [
        ROOT / "agents",
        ROOT / "prompts",
        ROOT / "scorecard" / "quality_config.yaml",
        ROOT / "data" / "rubric.yaml",
    ]

    leakages = []
    for target in search_dirs:
        if target.is_dir():
            files = list(target.glob("*.md")) + list(target.glob("*.yaml"))
        elif target.exists():
            files = [target]
        else:
            continue

        for f in files:
            content = f.read_text(encoding="utf-8")
            for cid in heldout_ids:
                if cid in content:
                    leakages.append(f"Heldout call '{cid}' leaked into '{f.relative_to(ROOT)}'")

    assert not leakages, "Leakage detected! Heldout calls must never appear in prompts or configs:\n" + "\n".join(leakages)

