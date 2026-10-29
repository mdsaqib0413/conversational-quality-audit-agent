"""Knowledge base + retrieval (the RAG layer).

* Parses data/policies/*.md and data/sops/*.md into clause-level / step-level chunks with
  stable IDs (REF-1.1, GEN-03, REF-S2 ...) and metadata.
* Reads data/rubric.yaml for weights / critical flags.
* Retrieval is hybrid: BM25 (always available) + sentence-embedding cosine similarity
  (BAAI/bge-small-en-v1.5 via sentence-transformers, used when installed). Embeddings are cached
  on disk, so the model is only needed the first time. If embeddings cannot load, BM25 alone is
  used and a warning is logged, so the app never fails because of the vector part.
* `retrieve_for_topic` / `retrieve_window` are standalone and work on partial conversations, which
  is what the Phase-2 live assistant needs.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Dict, Iterable, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = DATA_DIR / "index_cache"

HEADER_RE = re.compile(r"^###\s*\[([A-Z]+-S?\d+(?:\.\d+)?)\]\s*(.*)$", re.MULTILINE)

# policy id prefix -> human name
POLICY_PREFIX_NAMES = {
    "REF": "Refund and Returns Policy",
    "SHP": "Shipping and Delivery Policy",
    "WAR": "Warranty and Replacement Policy",
    "BIL": "Billing and Payments Policy",
    "ESC": "Escalation Policy",
    "PRV": "Privacy and Identity Verification Policy",
}

# which policy families matter for which topic (first = primary)
TOPIC_POLICY_PREFIXES = {
    "refund": ["REF", "BIL", "PRV", "ESC"],
    "billing": ["BIL", "REF", "PRV", "ESC"],
    "shipping": ["SHP", "ESC", "PRV", "REF"],
    "warranty": ["WAR", "REF", "PRV", "ESC"],
    "complaint": ["ESC", "REF", "SHP", "PRV"],
    "general": ["PRV", "ESC", "REF", "SHP"],
}

STOPWORDS = set(
    "a an the and or of to in on for with is are was were be been it this that you your i my we our they their at by as from "
    "have has had do does did not no yes can will would should could may might please thank thanks sir madam ma am hello hi ok okay "
    "just so if then than there here what which who whom when where how also any all some more most".split()
)


def tokenize(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS and len(w) > 1]


@dataclass
class Chunk:
    id: str
    kind: str                 # "policy" | "sop"
    title: str
    text: str
    file: str
    family: str               # policy prefix (REF, SHP, ...) or SOP family (GEN, REF-S, ANG, HLD)
    category: str = ""
    weight: int = 1
    critical: bool = False
    mandatory: bool = True
    what_good: str = ""
    example: str = ""
    description: str = ""

    def body(self, limit: int = 600) -> str:
        """The clause text without its leading 'ID Title' line and without markdown noise."""
        lines = self.text.split("\n", 1)
        t = lines[1] if len(lines) > 1 else self.text
        t = re.sub(r"\s+", " ", t.replace("**", "")).strip()
        return t if len(t) <= limit else t[: limit - 3] + "..."

    def short(self, limit: int = 600) -> str:
        t = re.sub(r"\s+", " ", self.text.replace("**", "")).strip()
        return t if len(t) <= limit else t[: limit - 3] + "..."


def _split_front_matter(raw: str):
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                meta = {}
            return meta, parts[2]
    return {}, raw


def _field(block: str, label: str) -> str:
    m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+?)(?=\n- \*\*|\n---|\Z)", block, re.DOTALL)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _first_example(block: str) -> str:
    m = re.search(r"\*\"(.+?)\"\*", block, re.DOTALL)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _family(chunk_id: str) -> str:
    m = re.match(r"([A-Z]+-S?)\d", chunk_id)
    prefix = m.group(1) if m else chunk_id
    return prefix[:-1] if prefix.endswith("-") else prefix  # "REF-1.1" -> "REF", "REF-S1" -> "REF-S"


def parse_markdown_file(path: Path) -> List[Chunk]:
    raw = path.read_text(encoding="utf-8")
    meta, body = _split_front_matter(raw)
    kind = str(meta.get("type", "sop" if "sops" in path.parts else "policy"))
    category = str(meta.get("category", ""))
    heads = list(HEADER_RE.finditer(body))
    chunks: List[Chunk] = []
    for idx, m in enumerate(heads):
        end = heads[idx + 1].start() if idx + 1 < len(heads) else len(body)
        block = body[m.end():end]
        block = re.split(r"\n---\s*\n", block)[0]
        cid, title = m.group(1), m.group(2).strip()
        chunks.append(
            Chunk(
                id=cid, kind=kind, title=title, text=f"{cid} {title}\n{block.strip()}", file=path.name,
                family=_family(cid), category=category,
                mandatory=_field(block, "Mandatory").lower().startswith("y") if kind == "sop" else True,
                critical=_field(block, "Critical").lower().startswith("y") if kind == "sop" else False,
                what_good=_field(block, "What Good Looks Like"),
                example=_first_example(block),
                description=_field(block, "Description"),
            )
        )
    return chunks


def load_rubric(path: Optional[Path] = None) -> dict:
    path = path or DATA_DIR / "rubric.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class BM25:
    def __init__(self, docs: Sequence[List[str]], k1: float = 1.4, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(1, self.N)
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.tf = [Counter(d) for d in docs]

    def scores(self, query: List[str]) -> List[float]:
        out = []
        for i, d in enumerate(self.docs):
            s = 0.0
            dl = len(d) or 1
            for t in set(query):
                f = self.tf[i].get(t, 0)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


def _normalize(scores: List[float]) -> List[float]:
    if not scores:
        return scores
    hi, lo = max(scores), min(scores)
    if hi - lo < 1e-9:
        return [0.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


class KnowledgeBase:
    def __init__(self, data_dir: Path = DATA_DIR, use_embeddings: Optional[bool] = None):
        self.data_dir = data_dir
        self.policies: List[Chunk] = []
        self.sops: List[Chunk] = []
        self.rubric: dict = {}
        self._embedder = None
        self._emb_matrix = None
        self._emb_tried = False
        if use_embeddings is None:
            use_embeddings = os.getenv("USE_EMBEDDINGS", "1") not in ("0", "false", "False")
        self.use_embeddings = use_embeddings
        self.load()

    # ---- loading ---------------------------------------------------------------------
    def load(self) -> None:
        self.policies, self.sops = [], []
        for p in sorted((self.data_dir / "policies").glob("*.md")):
            self.policies += parse_markdown_file(p)
        for p in sorted((self.data_dir / "sops").glob("*.md")):
            self.sops += parse_markdown_file(p)
        self.rubric = load_rubric(self.data_dir / "rubric.yaml")
        rub = {s["step_id"]: s for s in self.rubric.get("sop_steps", [])}
        for s in self.sops:
            r = rub.get(s.id)
            if r:
                s.weight = int(r.get("weight", 1))
                s.critical = bool(r.get("critical", s.critical))
                s.mandatory = bool(r.get("mandatory", s.mandatory))
        self.by_id: Dict[str, Chunk] = {c.id: c for c in self.policies + self.sops}
        self._bm25 = BM25([tokenize(c.text) for c in self.policies])
        self._emb_matrix, self._emb_tried = None, False

    @property
    def version(self) -> str:
        h = hashlib.sha256()
        for c in self.policies + self.sops:
            h.update(c.text.encode("utf-8"))
        h.update(repr(sorted((s["step_id"], s.get("weight"), s.get("critical")) for s in self.rubric.get("sop_steps", []))).encode())
        return h.hexdigest()[:12]

    # ---- embeddings (optional) -------------------------------------------------------
    def _load_embeddings(self) -> bool:
        if self._emb_matrix is not None:
            return True
        if self._emb_tried or not self.use_embeddings:
            return False
        self._emb_tried = True
        try:
            import numpy as np

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache = CACHE_DIR / f"policy_emb_{self.version}.npy"
            if cache.exists():
                self._emb_matrix = np.load(cache)
                return True
            from sentence_transformers import SentenceTransformer

            name = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
            self._embedder = get_embedder(name)
            mat = self._embedder.encode([c.text for c in self.policies], normalize_embeddings=True)
            np.save(cache, mat)
            self._emb_matrix = mat
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embeddings unavailable (%s). Falling back to BM25-only retrieval.", exc)
            self._emb_matrix = None
            return False

    def _embed_query(self, query: str):
        import numpy as np

        if self._embedder is None:
            self._embedder = get_embedder(os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5"))
        prefix = "Represent this sentence for searching relevant passages: "
        return np.asarray(self._embedder.encode([prefix + query], normalize_embeddings=True))[0]


    # ---- retrieval -------------------------------------------------------------------
    def retrieve_policies(self, query: str, topic: Optional[str] = None, k: int = 12,
                          always_include: Iterable[str] = (), use_embeddings: Optional[bool] = None) -> List[Chunk]:
        """Top-k policy clauses for `query`, boosted by topic, always including `always_include` ids."""
        if not self.policies:
            return []
        lex = _normalize(self._bm25.scores(tokenize(query)))
        scores = lex
        should_embed = self.use_embeddings if use_embeddings is None else use_embeddings
        if should_embed and self._load_embeddings():
            try:
                import numpy as np

                sims = (self._emb_matrix @ self._embed_query(query)).tolist()
                scores = [0.5 * a + 0.5 * b for a, b in zip(lex, _normalize(sims))]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Embedding query failed (%s); using BM25 only.", exc)
        prefixes = TOPIC_POLICY_PREFIXES.get(topic or "general", [])
        boosted = []
        for c, s in zip(self.policies, scores):
            if c.family in prefixes:
                s += 0.35 if c.family == prefixes[0] else 0.15
            boosted.append((s, c))
        boosted.sort(key=lambda x: -x[0])
        picked: List[Chunk] = []
        for _, c in boosted:
            if len(picked) >= k:
                break
            picked.append(c)
        for cid in always_include:
            ch = self.by_id.get(cid)
            if ch and ch not in picked and ch.kind == "policy":
                picked.append(ch)
        return picked

    def policies_for_topic(self, topic: str, limit: Optional[int] = None) -> List[Chunk]:
        """All clauses of the topic's primary policy family (Phase 2: 'show me all refund policies')."""
        prefixes = TOPIC_POLICY_PREFIXES.get(topic, [])
        primary = prefixes[0] if prefixes else None
        out = [c for c in self.policies if c.family == primary]
        return out[:limit] if limit else out

    # ---- SOP access ------------------------------------------------------------------
    def sop_steps(self, families: Iterable[str]) -> List[Chunk]:
        fams = set(families)
        return [s for s in self.sops if s.family in fams]

    def policy_title(self, clause_id: str) -> str:
        c = self.by_id.get(clause_id)
        if not c:
            return ""
        return f"{POLICY_PREFIX_NAMES.get(c.family, c.family)}: {c.title}"


_kb: Optional[KnowledgeBase] = None
_kb_lock = threading.Lock()


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        with _kb_lock:
            if _kb is None:
                _kb = KnowledgeBase()
    return _kb


_embedder_cache: dict = {}
_embedder_lock = threading.Lock()


def get_embedder(name: str = "BAAI/bge-small-en-v1.5"):
    if name not in _embedder_cache:
        with _embedder_lock:
            if name not in _embedder_cache:
                from sentence_transformers import SentenceTransformer
                _embedder_cache[name] = SentenceTransformer(name)
    return _embedder_cache[name]

