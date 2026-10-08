"""Embeds user questions with the SAME model that produced your stored embeddings."""
from __future__ import annotations

import numpy as np


class QueryEmbedder:
    def __init__(self, model_name: str, backend: str = "fastembed", prefix: str = ""):
        self.model_name = model_name
        self.backend = backend
        self.prefix = prefix or ""
        if backend == "sentence_transformers":
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
        else:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=model_name)

    def embed(self, text: str) -> np.ndarray:
        text = self.prefix + text
        if self.backend == "sentence_transformers":
            vec = self._model.encode(text, normalize_embeddings=True)
        else:
            vec = next(iter(self._model.embed([text])))
        vec = np.asarray(vec, dtype=np.float32)
        n = np.linalg.norm(vec)
        return vec / n if n else vec
