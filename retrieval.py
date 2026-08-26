"""
Stage 4 — Evidence Retrieval.

WHY hybrid (dense + BM25) instead of dense-only:
Dense embeddings (BGE) are great at semantic/paraphrase matching ("cures
diabetes" ~ "reduces blood glucose") but weak on exact terminology matches
that matter a lot in medicine — drug names, dosages, ICD codes, gene names.
BM25 (lexical, term-frequency based) nails those exact-term cases dense
retrieval sometimes misses. Fusing both is standard in modern RAG systems
(this is what "hybrid search" in Weaviate/Pinecone/Elastic docs means) and
consistently outperforms either alone on out-of-domain, jargon-heavy text.
Without hybrid: you will retrieve semantically-similar-but-wrong evidence,
which the NLI stage will then confidently "verify" against — garbage in,
confidently-wrong verdict out.

WHY ChromaDB over Pinecone/Weaviate here:
Runs embedded (no server, no network dependency), persists to disk, free,
and is more than fast enough at the corpus sizes an undergrad capstone will
actually index (thousands-tens of thousands of documents). Swap to Qdrant/
Pinecone later only if you scale past ~1M vectors.
"""
import bm25s
import chromadb
from sentence_transformers import SentenceTransformer

from config import (
    EMBED_MODEL, CHROMA_DIR, COLLECTION_NAME, DEVICE,
    DENSE_WEIGHT, BM25_WEIGHT, TOP_K_RETRIEVE,
)

_embedder = SentenceTransformer(EMBED_MODEL, device=DEVICE)
_chroma = chromadb.PersistentClient(path=CHROMA_DIR)
_collection = _chroma.get_or_create_collection(COLLECTION_NAME)

# BM25 index is built once (or rebuilt) over the same corpus you push into Chroma.
_bm25_index = None
_bm25_corpus_ids = []


def index_documents(docs: list[dict]):
    """docs: [{"id": str, "text": str, "source": str, "url": str}, ...]"""
    global _bm25_index, _bm25_corpus_ids

    embeddings = _embedder.encode(
        [d["text"] for d in docs],
        normalize_embeddings=True,   # required for cosine similarity via dot product
        show_progress_bar=True,
    )
    _collection.upsert(
        ids=[d["id"] for d in docs],
        embeddings=embeddings.tolist(),
        documents=[d["text"] for d in docs],
        metadatas=[{"source": d["source"], "url": d.get("url", "")} for d in docs],
    )

    # bm25s: tokenizes + builds a sparse index far faster than rank_bm25 (Rust-backed under the hood)
    corpus_tokens = bm25s.tokenize([d["text"] for d in docs], stopwords="en")
    _bm25_index = bm25s.BM25()
    _bm25_index.index(corpus_tokens)
    _bm25_corpus_ids = [d["id"] for d in docs]


def retrieve(query: str, top_k: int = TOP_K_RETRIEVE) -> list[dict]:
    # --- dense leg ---
    q_emb = _embedder.encode([query], normalize_embeddings=True).tolist()
    dense_res = _collection.query(query_embeddings=q_emb, n_results=top_k)
    dense_scores = {
        doc_id: 1 - dist  # chroma returns cosine distance -> similarity
        for doc_id, dist in zip(dense_res["ids"][0], dense_res["distances"][0])
    }

    # --- sparse leg ---
    bm25_scores = {}
    if _bm25_index is not None:
        q_tokens = bm25s.tokenize([query], stopwords="en")
        results, scores = _bm25_index.retrieve(q_tokens, k=min(top_k, len(_bm25_corpus_ids)))
        for idx, score in zip(results[0], scores[0]):
            bm25_scores[_bm25_corpus_ids[idx]] = float(score)

    # --- normalize + fuse ---
    def _minmax(d: dict) -> dict:
        if not d:
            return {}
        lo, hi = min(d.values()), max(d.values())
        span = (hi - lo) or 1.0
        return {k: (v - lo) / span for k, v in d.items()}

    dense_n, bm25_n = _minmax(dense_scores), _minmax(bm25_scores)
    all_ids = set(dense_n) | set(bm25_n)
    fused = {
        doc_id: DENSE_WEIGHT * dense_n.get(doc_id, 0) + BM25_WEIGHT * bm25_n.get(doc_id, 0)
        for doc_id in all_ids
    }
    ranked_ids = sorted(fused, key=fused.get, reverse=True)[:top_k]

    fetched = _collection.get(ids=ranked_ids, include=["documents", "metadatas"])
    return [
        {"id": doc_id, "text": text, "score": fused[doc_id], **meta}
        for doc_id, text, meta in zip(fetched["ids"], fetched["documents"], fetched["metadatas"])
    ]
