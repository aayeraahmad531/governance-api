import os
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

logger = logging.getLogger("governance_api.retrieval")

INDEX_DIR = "data"
ONNX_MODEL_PATH = os.path.join(INDEX_DIR, "model.onnx")
TOKENIZER_DIR = os.path.join(INDEX_DIR, "tokenizer")

_session: Optional[ort.InferenceSession] = None
_tokenizer: Optional[Tokenizer] = None
INDEXES: Dict[str, Dict[str, Any]] = {}


def init_onnx_embedder():
    global _session, _tokenizer
    tokenizer_json = os.path.join(TOKENIZER_DIR, "tokenizer.json")
    if os.path.exists(ONNX_MODEL_PATH) and os.path.exists(tokenizer_json):
        try:
            logger.info("Initializing ONNX Runtime inference session...")
            _session = ort.InferenceSession(ONNX_MODEL_PATH)
            _tokenizer = Tokenizer.from_file(tokenizer_json)
            _tokenizer.enable_truncation(max_length=512)
            _tokenizer.enable_padding(length=512)
            logger.info("ONNX Runtime query embedder ready.")
        except Exception as e:
            logger.error(f"Failed to initialize ONNX embedder: {e}")
            _session = None
            _tokenizer = None
    else:
        logger.warning(f"ONNX model or tokenizer not found at '{ONNX_MODEL_PATH}' / '{TOKENIZER_DIR}'.")


def load_indexes():
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


# Initialize ONNX embedder and load indexes at module load
init_onnx_embedder()
load_indexes()


def encode_query_onnx(query: str) -> np.ndarray:
    if _session is None or _tokenizer is None:
        raise RuntimeError("ONNX embedder is not initialized.")

    encoding = _tokenizer.encode(query)
    input_ids = np.array([encoding.ids], dtype=np.int64)
    attention_mask = np.array([encoding.attention_mask], dtype=np.int64)
    token_type_ids = np.array([encoding.type_ids], dtype=np.int64)

    ort_inputs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids
    }
    
    outputs = _session.run(None, ort_inputs)
    last_hidden_state = outputs[0]

    mask_expanded = np.expand_dims(attention_mask, -1).astype(float)
    sum_embeddings = np.sum(last_hidden_state * mask_expanded, axis=1)
    sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
    mean_pooled = sum_embeddings / sum_mask

    norm = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    return (mean_pooled / norm)[0].astype(np.float32)


def search(index_name: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Synchronous vector search using ONNX query embeddings.
    Returns list of dicts: [{"text": str, "score": float, "meta": dict}]
    If index_name is missing, logs warning and returns [].
    """
    if _session is None or _tokenizer is None:
        logger.warning("ONNX embedder is not ready.")
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

    # Fast ONNX query embedding
    q_vec = encode_query_onnx(query)

    # Dot-product similarities
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
