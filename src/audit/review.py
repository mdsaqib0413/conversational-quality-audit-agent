"""Human review persistence and management for audit findings.

Stores review decisions (accepted / overturned) in data/reviews/<call_id>.json.
Overturned findings are marked, never deleted, allowing side-by-side comparison.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .schemas import AuditFinding, AuditReport

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REVIEWS_DIR = REPO_ROOT / "data" / "reviews"


class ReviewDecision(BaseModel):
    finding_id: str
    decision: str  # "accepted" | "overturned"
    reviewer_note: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CallReviewFile(BaseModel):
    call_id: str
    reviews: Dict[str, ReviewDecision] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def get_review_file_path(call_id: str, base_dir: Path | None = None) -> Path:
    d = base_dir or REVIEWS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{call_id}.json"


def load_reviews_for_call(call_id: str, base_dir: Path | None = None) -> Dict[str, ReviewDecision]:
    path = get_review_file_path(call_id, base_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        res = {}
        for fid, raw in data.get("reviews", {}).items():
            res[fid] = ReviewDecision.model_validate(raw)
        return res
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error reading review file %s: %s", path, exc)
        return {}


def save_review_decision(
    call_id: str,
    finding_id: str,
    decision: str,
    reviewer_note: str = "",
    base_dir: Path | None = None,
) -> ReviewDecision:
    """Save an acceptance or overturn decision for a finding."""
    path = get_review_file_path(call_id, base_dir)
    current = load_reviews_for_call(call_id, base_dir)
    item = ReviewDecision(
        finding_id=finding_id,
        decision=decision,
        reviewer_note=reviewer_note,
    )
    current[finding_id] = item

    doc = {
        "call_id": call_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "reviews": {fid: r.model_dump() for fid, r in current.items()},
    }
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return item


def apply_reviews_to_report(report: AuditReport, base_dir: Path | None = None) -> AuditReport:
    """Annotate report findings with reviewer decisions."""
    reviews = load_reviews_for_call(report.call_id, base_dir)
    if not reviews:
        return report

    for f in report.findings:
        if f.finding_id in reviews:
            rev = reviews[f.finding_id]
            f.reviewer_status = "overturned" if rev.decision == "overturned" else "accepted"
            f.reviewer_note = rev.reviewer_note
    return report

