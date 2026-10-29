"""Smoke test: every module imports and the knowledge base loads."""


def test_imports_and_kb():
    import importlib

    for m in ("llm", "schemas", "rag", "topic", "emotion", "evidence", "scoring", "sop_check", "policy_check", "diarize",
              "transcribe", "pipeline", "report", "evaluation", "labels", "transcript_io"):
        importlib.import_module(f"src.audit.{m}")
    from src.audit.rag import KnowledgeBase

    kb = KnowledgeBase(use_embeddings=False)
    assert kb.policies and kb.sops
