import os
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("governance_api.retrieval")

MODEL_NAME = "all-MiniLM-L6-v2"
INDEX_DIR = "data"

# Load model once at import / startup
logger.info(f"Loading retrieval model '{MODEL_NAME}'...")
try:
    _model = SentenceTransformer(MODEL_NAME)
except Exception as e:
    logger.error(f"Failed to load sentence-transformers model: {e}")
    _model = None

# In-memory index cache: { index_name: {"vecs": np.ndarray, "chunks": list, "meta": list} }
INDEXES: Dict[str, Dict[str, Any]] = {}


def load_indexes():
    """Loads all available .npz files into memory once at startup."""
    global INDEXES
    INDEXES.clear()
    
    if not os.path.exists(INDEX_DIR):
        logger.warning(f"Index directory '{INDEX_DIR}' does not exist.")
        return

    for filename in os.listdir(INDEX_DIR):
        if filename.endswith(".npz"):
            index_name = filename[:-4]
            path = os.path.join(INDEX_DIR, filename)
            try:
                data = np.load(path, allow_pickle=True)
                vecs = data["vecs"].astype(np.float32)
                chunks = data["chunks"].tolist()
                raw_meta = data["meta"].tolist()
                
                meta = []
                for m in raw_meta:
                    if isinstance(m, str):
                        meta.append(json.loads(m))
                    else:
                        meta.append(dict(m))
                
                INDEXES[index_name] = {
                    "vecs": vecs,
                    "chunks": chunks,
                    "meta": meta
                }
                logger.info(f"Loaded index '{index_name}' ({len(chunks)} chunks).")
            except Exception as e:
                logger.error(f"Failed to load index '{filename}': {e}")


# Initialize indexes on module load
load_indexes()


def search(index_name: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Synchronous vector dot-product search.
    Returns list of dicts: [{"text": str, "score": float, "meta": dict}]
    If index_name is not found, logs warning and returns [].
    """
    if _model is None:
        logger.warning("Retrieval model is not initialized.")
        return []

    if index_name not in INDEXES:
        logger.warning(f"Index '{index_name}' not found in loaded indexes {list(INDEXES.keys())}.")
        return []

    index = INDEXES[index_name]
    vecs = index["vecs"]
    chunks = index["chunks"]
    meta = index["meta"]

    if len(chunks) == 0:
        return []

    # Encode query and normalize
    q_vec = _model.encode(query, convert_to_numpy=True)
    norm = np.linalg.norm(q_vec)
    if norm > 0:
        q_vec = q_vec / norm

    # Compute dot product similarities
    scores = vecs @ q_vec
    top_indices = np.argsort(scores)[::-1][:k]

    results = []
    for idx in top_indices:
        results.append({
            "text": str(chunks[idx]),
            "score": float(scores[idx]),
            "meta": meta[idx]
        })

    return results
