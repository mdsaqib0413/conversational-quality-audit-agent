"""Qdrant vector store tests. Offline: a tiny hashing embedder replaces bge-small, so no model download."""

import re
import zlib

import numpy as np
import pytest

pytest.importorskip("qdrant_client")

from src.audit.rag import KnowledgeBase  # noqa: E402
from src.audit.vectorstore import PolicyVectorStore, point_id  # noqa: E402

DIM = 128


class HashEmbedder:
    """Bag-of-words hashed into DIM dims, L2-normalised. Deterministic and good enough to rank by word overlap."""

    def encode(self, texts, normalize_embeddings=True):
        out = np.zeros((len(texts), DIM), dtype="float32")
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                out[i, zlib.crc32(w.encode()) % DIM] += 1.0
        n = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(n == 0, 1, n)


@pytest.fixture()
def kb(tmp_path, monkeypatch):
    monkeypatch.setenv("QDRANT_PATH", str(tmp_path / "qdrant"))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("VECTOR_STORE", raising=False)
    k = KnowledgeBase(use_embeddings=True)
    k._embedder = HashEmbedder()
    k._emb_matrix = k._embedder.encode([c.text for c in k.policies])
    k._emb_tried = True
    k._attach_store()
    yield k
    if k._store is not None:
        k._store.close()


def test_policies_are_indexed_with_metadata(kb):
    assert kb._store is not None and kb.vector_backend.startswith("qdrant")
    assert kb._store.count() == len(kb.policies)
    rec = kb._store.client.retrieve(kb._store.collection, ids=[point_id("REF-1.1")], with_payload=True)[0]
    assert rec.payload["clause_id"] == "REF-1.1" and rec.payload["family"] == "REF" and rec.payload["kind"] == "policy"


def test_reopen_does_not_reindex_until_version_changes(kb, tmp_path):
    kb._store.close()
    store = PolicyVectorStore(kb.data_dir)  # same QDRANT_PATH
    assert store.sync(kb.policies, kb._emb_matrix, kb.version) is False  # persisted, same version
    assert store.sync(kb.policies, kb._emb_matrix, "another-version") is True  # policy text changed -> rebuild
    assert store.count() == len(kb.policies)
    store.close()
    kb._store = None


def test_qdrant_scores_match_numpy_matrix(kb):
    q = "refund will be credited within 24 hours to my wallet"
    qv = kb._embed_query(q)
    expected = dict(zip([c.id for c in kb.policies], (kb._emb_matrix @ qv).tolist()))
    got = kb._store.search(qv, limit=len(kb.policies))
    assert set(got) == set(expected)
    for cid, s in got.items():
        assert s == pytest.approx(expected[cid], abs=1e-4)


def test_retrieve_policies_same_with_and_without_qdrant(kb):
    q = "the return window for electronics is seven days refund to original payment"
    with_q = [c.id for c in kb.retrieve_policies(q, topic="refund", k=8)]
    store, kb._store = kb._store, None
    without_q = [c.id for c in kb.retrieve_policies(q, topic="refund", k=8)]
    kb._store = store
    assert with_q == without_q and with_q


def test_metadata_filter_by_family(kb):
    hits = kb.vector_search("courier delivery delay", k=5, families=["SHP"])
    assert hits and all(c.family == "SHP" for c, _ in hits)
    hits_all = kb.vector_search("courier delivery delay", k=5)
    assert len(hits_all) == 5


def test_falls_back_when_qdrant_breaks(kb):
    def boom(*a, **k):
        raise RuntimeError("server down")

    kb._store.search = boom
    got = kb.retrieve_policies("refund within seven days", topic="refund", k=5)
    assert got and kb._store is None and kb.vector_backend == "numpy matrix"


def test_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("QDRANT_PATH", str(tmp_path / "q"))
    monkeypatch.setenv("VECTOR_STORE", "numpy")
    k = KnowledgeBase(use_embeddings=True)
    k._embedder = HashEmbedder()
    k._emb_matrix = k._embedder.encode([c.text for c in k.policies])
    k._emb_tried = True
    k._attach_store()
    assert k._store is None and k.vector_backend == "numpy matrix"
