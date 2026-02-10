# src/retrieval/embedding_index.py

import numpy as np
from typing import List


class EmbeddingIndex:
    def __init__(self, texts: List[str], vectors: np.ndarray):
        self.texts = texts
        self.vecs = vectors  # already normalized

    # -------------------------------------------------

    def search(self, query_vec: np.ndarray, top_k: int = 7):
        """
        cosine search
        """
        sims = self.vecs @ query_vec
        idx = np.argsort(-sims)[:top_k]

        return [self.texts[i] for i in idx]
