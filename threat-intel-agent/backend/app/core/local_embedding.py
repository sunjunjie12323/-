import math
import os
import pickle
import re
from collections import Counter
from typing import List, Optional

import numpy as np
from loguru import logger


class LocalEmbeddingEngine:
    PERSIST_DIR = "./model_data/local_embedding"

    def __init__(self, dim: int = 256):
        self.dim = dim
        self._idf: dict = {}
        self._vocab: dict = {}
        self._svd_components: Optional[np.ndarray] = None
        self._trained = False
        self._try_load()

    def _tokenize(self, text: str) -> List[str]:
        tokens = []
        en_tokens = re.findall(r'[a-zA-Z][a-zA-Z0-9_]{1,}', text.lower())
        tokens.extend(en_tokens)

        cn_tokens = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        for t in cn_tokens:
            for i in range(len(t) - 1):
                tokens.append(t[i:i + 2])

        special = re.findall(
            r'(?:\d{1,3}\.){3}\d{1,3}|'
            r'[a-fA-F0-9]{32,}|'
            r'https?://[^\s]+|'
            r'CVE-\d{4}-\d{4,}|'
            r'[\w.+-]+@[\w-]+\.[\w.-]+',
            text,
        )
        tokens.extend(special)
        return tokens

    def train(self, documents: List[str]):
        logger.info(f"LocalEmbeddingEngine: training on {len(documents)} documents...")
        doc_freq = Counter()
        all_tokens_per_doc = []

        for doc in documents:
            tokens = self._tokenize(doc)
            all_tokens_per_doc.append(tokens)
            unique_tokens = set(tokens)
            for t in unique_tokens:
                doc_freq[t] += 1

        min_df = max(1, len(documents) // 1000)
        max_df_ratio = 0.95
        n_docs = len(documents)

        self._vocab = {}
        idx = 0
        for token, df in doc_freq.items():
            if df >= min_df and df / n_docs <= max_df_ratio:
                self._vocab[token] = idx
                idx += 1

        for token, df in doc_freq.items():
            if token in self._vocab:
                self._idf[token] = math.log((n_docs + 1) / (df + 1)) + 1.0

        vocab_size = len(self._vocab)
        logger.info(f"LocalEmbeddingEngine: vocab size = {vocab_size}")

        if vocab_size == 0:
            self._trained = True
            return

        tfidf_matrix = np.zeros((n_docs, vocab_size), dtype=np.float32)
        for i, tokens in enumerate(all_tokens_per_doc):
            tf = Counter(tokens)
            for token, count in tf.items():
                if token in self._vocab:
                    j = self._vocab[token]
                    tfidf_matrix[i, j] = (1 + math.log(count)) * self._idf.get(token, 1.0)

        norms = np.linalg.norm(tfidf_matrix, axis=1, keepdims=True)
        norms[norms < 1e-10] = 1.0
        tfidf_matrix = tfidf_matrix / norms

        target_dim = min(self.dim, vocab_size, tfidf_matrix.shape[0])
        if target_dim < vocab_size and target_dim > 0:
            try:
                U, S, Vt = np.linalg.svd(tfidf_matrix, full_matrices=False)
                self._svd_components = Vt[:target_dim]
                logger.info(f"LocalEmbeddingEngine: SVD reduced {vocab_size} → {target_dim} dims")
            except Exception as exc:
                logger.warning(f"SVD failed: {exc}, using random projection")
                rng = np.random.RandomState(42)
                self._svd_components = rng.randn(target_dim, vocab_size).astype(np.float32)
                self._svd_components /= np.linalg.norm(self._svd_components, axis=1, keepdims=True)
        else:
            self._svd_components = None

        self._trained = True
        self._save()
        logger.info(f"LocalEmbeddingEngine: training complete, dim={target_dim}")

    def embed(self, text: str) -> List[float]:
        if not self._trained or not self._vocab:
            return self._fallback_embed(text)

        tokens = self._tokenize(text)
        if not tokens:
            return self._fallback_embed(text)

        tf = Counter(tokens)
        vocab_size = len(self._vocab)
        vec = np.zeros(vocab_size, dtype=np.float32)
        for token, count in tf.items():
            if token in self._vocab:
                j = self._vocab[token]
                vec[j] = (1 + math.log(count)) * self._idf.get(token, 1.0)

        norm = np.linalg.norm(vec)
        if norm < 1e-10:
            return self._fallback_embed(text)
        vec = vec / norm

        if self._svd_components is not None:
            vec = self._svd_components @ vec
            norm = np.linalg.norm(vec)
            if norm > 1e-10:
                vec = vec / norm

        return vec.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]

    def _fallback_embed(self, text: str) -> List[float]:
        import hashlib as _hashlib
        h = _hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:4], "big")
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm < 1e-10:
            return [0.0] * self.dim
        vec = vec / norm
        return vec.tolist()

    def _save(self):
        os.makedirs(self.PERSIST_DIR, exist_ok=True)
        data = {
            "vocab": self._vocab,
            "idf": self._idf,
            "svd_components": self._svd_components,
            "dim": self.dim,
            "trained": self._trained,
        }
        with open(os.path.join(self.PERSIST_DIR, "model.pkl"), "wb") as f:
            pickle.dump(data, f)

    def _try_load(self):
        path = os.path.join(self.PERSIST_DIR, "model.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                self._vocab = data["vocab"]
                self._idf = data["idf"]
                self._svd_components = data["svd_components"]
                self.dim = data.get("dim", self.dim)
                self._trained = data.get("trained", False)
                logger.info(f"LocalEmbeddingEngine: loaded model, vocab={len(self._vocab)}, trained={self._trained}")
            except Exception as exc:
                logger.warning(f"LocalEmbeddingEngine: failed to load model: {exc}")
