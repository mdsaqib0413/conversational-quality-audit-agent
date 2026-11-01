"""Vector store for policy clauses (Qdrant).

Why it exists: today the knowledge base is small (a few dozen clauses), but policies will grow. A real vector
database gives us persistence, payload metadata filtering (family / topic / severity ...) and an approximate
index that scales, without changing the callers: `KnowledgeBase.retrieve_policies` is the only entry point.

Modes (env):
* VECTOR_STORE=qdrant (default)  -> Qdrant. `QDRANT_URL` set -> remote/cloud server (QDRANT_API_KEY optional);
                                   otherwise embedded local mode persisted in data/qdrant_db (no server to run).
* VECTOR_STORE=numpy             -> disable Qdrant, use the in-memory matrix (previous behaviour).

Any Qdrant failure (not installed, folder locked by another process, server down) is logged and the caller falls
back to the in-memory matrix, then to BM25, so the app never fails because of the vector part.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

COLLECTION = "shopease_policies"
_NAMESPACE = uuid.UUID("6f1c2f0e-6a0e-4b8e-9f0e-0a5d1c9b7e11")


def point_id(chunk_id: str) -> str:
    """Stable UUID per clause id (Qdrant ids must be ints or UUIDs)."""
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


def vector_store_enabled() -> bool:
    return os.getenv("VECTOR_STORE", "qdrant").strip().lower() not in ("numpy", "none", "off", "0", "false")


class PolicyVectorStore:
    def __init__(self, data_dir: Path, collection: str = COLLECTION, client=None):
        from qdrant_client import QdrantClient

        self.collection = collection
        self.mode = "memory"
        if client is not None:
            self.client = client
        elif os.getenv("QDRANT_URL"):
            self.client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.getenv("QDRANT_API_KEY") or None)
            self.mode = "server"
        else:
            path = Path(os.getenv("QDRANT_PATH", str(Path(data_dir) / "qdrant_db")))
            path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(path))
            self.mode = f"local:{path}"

    # ---- indexing --------------------------------------------------------------------
    def _stored_version(self) -> Optional[str]:
        try:
            info = self.client.get_collection(self.collection)
        except Exception:  # noqa: BLE001 - collection missing
            return None
        meta = getattr(getattr(info, "config", None), "metadata", None) or {}
        return meta.get("kb_version")

    def sync(self, chunks: Sequence, vectors, version: str) -> bool:
        """Make the collection match `chunks`/`vectors`. Re-indexes only when the knowledge base version changed.

        Returns True when a (re)index happened."""
        from qdrant_client import models

        n = len(chunks)
        if n == 0:
            return False
        if self._stored_version() == version:
            try:
                if self.client.count(self.collection, exact=True).count == n:
                    return False
            except Exception:  # noqa: BLE001
                pass
        dim = int(len(vectors[0]))
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            self.collection,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            metadata={"kb_version": version},
        )
        points = [
            models.PointStruct(
                id=point_id(c.id),
                vector=[float(x) for x in v],
                payload={
                    "clause_id": c.id, "family": c.family, "kind": c.kind, "title": c.title,
                    "category": c.category, "file": c.file,
                    "topics": getattr(c, "topics", []),
                    "situations": getattr(c, "situations", []),
                    "numeric_limit": getattr(c, "numeric_limit", None),
                    "default_severity": getattr(c, "default_severity", "minor"),
                    "clause_kind": getattr(c, "clause_kind", "informational"),
                },
            )
            for c, v in zip(chunks, vectors)
        ]
        self.client.upsert(self.collection, points=points, wait=True)
        # payload indexes only matter on a real server (embedded local mode ignores them and warns)
        if self.mode != "server":
            logger.info("Indexed %d clauses into Qdrant (%s)", n, self.mode)
            return True
        try:
            self.client.create_payload_index(self.collection, "family", models.PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(self.collection, "kind", models.PayloadSchemaType.KEYWORD)
        except Exception:  # noqa: BLE001 - not supported in every mode; filters still work
            pass
        logger.info("Indexed %d clauses into Qdrant (%s)", n, self.mode)
        return True

    # ---- search ----------------------------------------------------------------------
    def search(self, query_vec, limit: int, families: Optional[Iterable[str]] = None) -> Dict[str, float]:
        """Cosine similarity per clause id for the top `limit` hits, optionally restricted to policy families."""
        from qdrant_client import models

        flt = None
        fams = list(families or [])
        if fams:
            flt = models.Filter(must=[models.FieldCondition(key="family", match=models.MatchAny(any=fams))])
        res = self.client.query_points(
            self.collection, query=[float(x) for x in query_vec], limit=int(limit), query_filter=flt,
            with_payload=["clause_id"],
        )
        return {p.payload["clause_id"]: float(p.score) for p in res.points}

    def count(self) -> int:
        return int(self.client.count(self.collection, exact=True).count)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:  # noqa: BLE001
            pass
