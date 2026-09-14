"""本地中文句向量语义匹配。

首次运行会从 Hugging Face 下载模型；之后使用本地缓存离线运行。
"""
from functools import lru_cache
from typing import List

import numpy as np


@lru_cache(maxsize=1)
def get_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("缺少 sentence-transformers，请执行 pip install sentence-transformers torch") from exc
    return SentenceTransformer("BAAI/bge-small-zh-v1.5")


def encode_texts(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def semantic_similarity(text_a: str, text_b: str) -> float:
    vectors = encode_texts([text_a or "", text_b or ""])
    if vectors.shape[0] < 2:
        return 0.0
    return float(np.clip(np.dot(vectors[0], vectors[1]), -1.0, 1.0))
