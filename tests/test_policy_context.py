"""Offline unit tests for POLICY_CONTEXT configuration (Variants A vs G) and audit cache versioning."""

from __future__ import annotations

import os
from typing import List

import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.policy_check import (
    ALWAYS_INCLUDE,
    check_policies,
    get_policy_context_clauses,
    get_policy_context_mode,
)
from src.audit.rag import KnowledgeBase
from src.audit.schemas import CallTranscript, DialogueTurn, PolicyAnalysis
from tests.fakes import FakeGateway


@pytest.fixture
def sample_call() -> CallTranscript:
    turns = [
        DialogueTurn(turn_id=1, speaker="customer", text="I want to check my warranty coverage for Boat headphones."),
        DialogueTurn(turn_id=2, speaker="agent", text="Certainly! I can assist you with your Boat warranty claim."),
        DialogueTurn(turn_id=3, speaker="customer", text="Here is my order ORD-9912 and last four digits 4412."),
        DialogueTurn(turn_id=4, speaker="agent", text="Thank you, I see your order. Replacement takes 2 business days."),
    ]
    return CallTranscript(call_id="call_mock_context", turns=turns, audio_file="")


@pytest.fixture
def kb() -> KnowledgeBase:
    return KnowledgeBase(use_embeddings=False)


def test_default_policy_context_is_g(sample_call, kb, monkeypatch):
    """When POLICY_CONTEXT is not set, default to G (universal PRV and ESC inclusion)."""
    monkeypatch.delenv("POLICY_CONTEXT", raising=False)
    assert get_policy_context_mode() == "G"

    clauses = get_policy_context_clauses(sample_call, "warranty", kb)
    clause_ids = {c.id for c in clauses}

    # All PRV and ESC clauses must be present in G
    prv_and_esc = [p.id for p in kb.policies if p.family in ("PRV", "ESC")]
    for cid in prv_and_esc:
        assert cid in clause_ids, f"Expected {cid} in Variant G context"


def test_policy_context_a_setting(sample_call, kb, monkeypatch):
    """When POLICY_CONTEXT=A, only ALWAYS_INCLUDE, topic family, and top-k are in context."""
    monkeypatch.setenv("POLICY_CONTEXT", "A")
    assert get_policy_context_mode() == "A"

    clauses_a = get_policy_context_clauses(sample_call, "warranty", kb)
    clause_ids_a = {c.id for c in clauses_a}

    # Core always-included clauses must still be present
    for cid in ALWAYS_INCLUDE:
        assert cid in clause_ids_a

    # Non-core PRV clause PRV-2.1 should NOT be automatically included in warranty call
    assert "PRV-2.1" not in clause_ids_a

    # Case insensitivity check
    monkeypatch.setenv("POLICY_CONTEXT", "a")
    assert get_policy_context_mode() == "A"


def test_policy_context_g_explicit_setting(sample_call, kb, monkeypatch):
    """When POLICY_CONTEXT=G explicitly, universal safety families are included."""
    monkeypatch.setenv("POLICY_CONTEXT", "G")
    assert get_policy_context_mode() == "G"

    clauses_g = get_policy_context_clauses(sample_call, "warranty", kb)
    clause_ids_g = {c.id for c in clauses_g}

    assert "PRV-2.1" in clause_ids_g
    assert "ESC-3.1" in clause_ids_g

    # Case insensitivity check
    monkeypatch.setenv("POLICY_CONTEXT", "g")
    assert get_policy_context_mode() == "G"


def test_policy_context_clauses_count_comparison(sample_call, kb, monkeypatch):
    """Variant G must include strictly more clauses than Variant A for the same topic."""
    clauses_g = get_policy_context_clauses(sample_call, "shipping", kb, mode="G")
    clauses_a = get_policy_context_clauses(sample_call, "shipping", kb, mode="A")

    assert len(clauses_g) > len(clauses_a)
    assert len(clauses_g) >= 20  # PRV (5) + ESC (5) + Shipping (7) + top-k


def test_check_policies_respects_env_switch(sample_call, kb, monkeypatch):
    """check_policies uses get_policy_context_clauses and passes correct clauses to prompt."""
    fake_gateway = FakeGateway(policy=PolicyAnalysis(claims=[]))

    # Test Mode A
    monkeypatch.setenv("POLICY_CONTEXT", "A")
    results_a, warnings_a, clauses_a = check_policies(sample_call, "warranty", kb, fake_gateway)
    ids_a = {c.id for c in clauses_a}
    assert "PRV-2.1" not in ids_a

    # Test Mode G
    monkeypatch.setenv("POLICY_CONTEXT", "G")
    results_g, warnings_g, clauses_g = check_policies(sample_call, "warranty", kb, fake_gateway)
    ids_g = {c.id for c in clauses_g}
    assert "PRV-2.1" in ids_g


def test_audit_cache_version_and_context_key_bump(sample_call, kb, tmp_path, monkeypatch):
    """Audit cache keys reflect the v9 cache bump and differ between modes A and G."""
    fake_gateway = FakeGateway(policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=fake_gateway, cache_dir=tmp_path)

    monkeypatch.setenv("POLICY_CONTEXT", "A")
    key_a = pipe._audit_key(sample_call)

    monkeypatch.setenv("POLICY_CONTEXT", "G")
    key_g = pipe._audit_key(sample_call)

    # Different policy context modes must generate different cache keys
    assert key_a != key_g

    # Keys must be non-empty hex strings
    assert len(key_a) == 16
    assert len(key_g) == 16
