"""RAG knowledge base indexer and retrieval module using ChromaDB and sentence-transformers."""

import os
import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from .schemas import DialogueTurn

logger = logging.getLogger(__name__)

class PolicyKnowledgeBase:
    """Manages policy indexing and semantic retrieval."""

    def __init__(
        self,
        persist_dir: str = "data/chroma_db",
        collection_name: str = "shopease_policies",
        embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self._collection = None
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.embedding_model_name)
        return self._embedder

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = client.get_or_create_collection(name=self.collection_name)
        return self._collection

    def index_policies(self, policies_dir: str = "data/policies"):
        """Parses markdown policy documents by stable clause IDs and indexes into ChromaDB."""
        p_dir = Path(policies_dir)
        if not p_dir.exists():
            logger.warning(f"Policies directory not found at {policies_dir}")
            return

        documents = []
        metadatas = []
        ids = []

        # Regex to locate stable clause IDs (e.g., REF-1.1, SHP-2.3, etc.)
        clause_pattern = re.compile(r"(###?\s*\[?([A-Z]{3}-\d+\.\d+)\]?[\s\S]*?)(?=(?:###?\s*\[?[A-Z]{3}-\d+\.\d+\]?|\Z))")

        for file_path in p_dir.glob("*.md"):
            content = file_path.read_text(encoding="utf-8")
            policy_name = file_path.stem
            matches = clause_pattern.findall(content)

            for raw_chunk, clause_id in matches:
                clean_chunk = raw_chunk.strip()
                documents.append(clean_chunk)
                ids.append(f"{policy_name}_{clause_id}")
                metadatas.append({
                    "clause_id": clause_id,
                    "policy_name": policy_name,
                    "source_file": file_path.name
                })

        if documents:
            embedder = self._get_embedder()
            embeddings = embedder.encode(documents).tolist()
            collection = self._get_collection()
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Successfully indexed {len(documents)} clauses into ChromaDB.")

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Semantic retrieval of clauses matching the query."""
        try:
            embedder = self._get_embedder()
            query_emb = embedder.encode([query]).tolist()
            collection = self._get_collection()
            results = collection.query(query_embeddings=query_emb, n_results=top_k)

            formatted = []
            if results and results.get("documents") and results["documents"][0]:
                for doc, meta, cid in zip(results["documents"][0], results["metadatas"][0], results["ids"][0]):
                    formatted.append({
                        "clause_id": meta.get("clause_id"),
                        "policy_name": meta.get("policy_name"),
                        "text": doc,
                        "id": cid
                    })
            return formatted
        except Exception as e:
            logger.warning(f"RAG retrieval fallback: {e}")
            return []

# Singleton
kb = PolicyKnowledgeBase()

# Standalone functions for Phase 2 Live Call Analysis
def retrieve_relevant_clauses(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Standalone retrieval function for live turn or query."""
    return kb.retrieve(query, top_k=top_k)

def retrieve_policies_rolling_window(turns: List[DialogueTurn], window_size: int = 4, top_k: int = 3) -> List[Dict[str, Any]]:
    """Standalone function retrieving policies against a rolling window of recent turns."""
    recent = turns[-window_size:] if len(turns) >= window_size else turns
    query_text = " ".join([t.text for t in recent])
    return retrieve_relevant_clauses(query_text, top_k=top_k)
