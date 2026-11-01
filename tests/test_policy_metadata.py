"""Tests for policy clause metadata parsing and payload indexing."""

from __future__ import annotations

import pytest

from src.audit.rag import KnowledgeBase
from src.audit.vectorstore import PolicyVectorStore, point_id


ALLOWED_TOPICS = {"refund", "billing", "shipping", "warranty", "complaint", "general"}
ALLOWED_SEVERITIES = {"minor", "major", "critical"}
ALLOWED_KINDS = {"must_say", "must_not_do", "informational"}


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(use_embeddings=False)


def test_every_policy_clause_has_valid_metadata(kb):
    """Verify all 42 policy clauses have valid topics, situations, numeric_limit, severity, and kind."""
    assert len(kb.policies) == 42, f"Expected 42 policy clauses, found {len(kb.policies)}"

    for c in kb.policies:
        # 1. Topics: non-empty list from allowed topics
        assert isinstance(c.topics, list), f"{c.id}: topics is not a list"
        assert len(c.topics) > 0, f"{c.id}: topics list is empty"
        assert all(t in ALLOWED_TOPICS for t in c.topics), f"{c.id}: invalid topics {c.topics}"

        # 2. Situations: list of strings
        assert isinstance(c.situations, list), f"{c.id}: situations is not a list"
        for s in c.situations:
            assert isinstance(s, str) and len(s) > 0, f"{c.id}: empty situation in {c.situations}"

        # 3. Numeric limit: None or non-empty string
        assert c.numeric_limit is None or (isinstance(c.numeric_limit, str) and len(c.numeric_limit) > 0)

        # 4. Default severity: minor | major | critical
        assert c.default_severity in ALLOWED_SEVERITIES, f"{c.id}: invalid severity {c.default_severity}"

        # 5. Clause kind: must_say | must_not_do | informational
        assert c.clause_kind in ALLOWED_KINDS, f"{c.id}: invalid clause_kind {c.clause_kind}"
        assert c.policy_kind == c.clause_kind


def test_policy_metadata_stored_in_qdrant_payload(kb, tmp_path):
    """Verify policy metadata fields are preserved in the vectorstore payload."""
    import numpy as np

    fake_matrix = np.ones((len(kb.policies), 8), dtype=float)
    store = PolicyVectorStore(tmp_path / "qd_test", collection="test_meta")
    store.sync(kb.policies, fake_matrix, "v_meta_test")

    # Inspect a clause with rich metadata (BIL-2.2 or PRV-1.1)
    ref_point = store.client.retrieve(store.collection, ids=[point_id("BIL-2.2")], with_payload=True)[0]
    payload = ref_point.payload

    assert payload["clause_id"] == "BIL-2.2"
    assert payload["topics"] == ["billing", "refund", "complaint"]
    assert "high_value_refund" in payload["situations"]
    assert payload["numeric_limit"] == "Rs 5,000"
    assert payload["default_severity"] == "critical"
    assert payload["clause_kind"] == "must_not_do"

    store.close()
