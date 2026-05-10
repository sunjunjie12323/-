import hashlib
import json
import os
import pickle
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from app.core.blacktalk_engine import BlackTalkEngine
from app.core.vector_store import VectorStore


@np.errstate(divide="ignore", invalid="ignore")
def _safe_kl(p: np.ndarray, q: np.ndarray) -> float:
    p = np.clip(p, 1e-10, None)
    q = np.clip(q, 1e-10, None)
    return float(np.sum(p * np.log(p / q)))


class SkipGramModel:
    def __init__(self, vocab_size: int, embed_dim: int = 64):
        self.vocab_size = vocab_size
        self.embed_dim = embed_dim
        scale = 0.5 / embed_dim
        self.W_in = np.random.uniform(-scale, scale, (vocab_size, embed_dim))
        self.W_out = np.random.uniform(-scale, scale, (vocab_size, embed_dim))

    def get_embedding(self, word_idx: int) -> np.ndarray:
        return self.W_in[word_idx]

    def save(self, path: str):
        np.savez(path, W_in=self.W_in, W_out=self.W_out)

    @classmethod
    def load(cls, path: str) -> "SkipGramModel":
        data = np.load(path)
        model = cls(vocab_size=data["W_in"].shape[0], embed_dim=data["W_in"].shape[1])
        model.W_in = data["W_in"]
        model.W_out = data["W_out"]
        return model


class ZeroDayDetector:
    CONFIDENCE_THRESHOLD = 0.5
    DRIFT_THRESHOLD = 0.3
    EMBED_DIM = 64
    WINDOW_SIZE = 3
    NEGATIVE_SAMPLES = 5
    LEARNING_RATE = 0.025
    MIN_COUNT = 1

    def __init__(self, vector_store: VectorStore, blacktalk_engine: BlackTalkEngine):
        self.vector_store = vector_store
        self.blacktalk_engine = blacktalk_engine
        self._word2idx: Dict[str, int] = {}
        self._idx2word: Dict[int, str] = {}
        self._word_freq: Counter = Counter()
        self._model: Optional[SkipGramModel] = None
        self._reference_dist: Optional[np.ndarray] = None
        self._term_vectors: Dict[str, np.ndarray] = {}
        self._trained = False
        self._persist_dir = "./model_data/zero_day"
        os.makedirs(self._persist_dir, exist_ok=True)

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"[\u4e00-\u9fff]{1,4}|[a-zA-Z]{2,}|[0-9]+", text.lower())
        return tokens

    def _build_vocab(self, corpus: List[str]):
        self._word_freq = Counter()
        for text in corpus:
            tokens = self._tokenize(text)
            self._word_freq.update(tokens)

        self._word2idx = {}
        self._idx2word = {}
        idx = 0
        for word, freq in self._word_freq.items():
            if freq >= self.MIN_COUNT:
                self._word2idx[word] = idx
                self._idx2word[idx] = word
                idx += 1

        logger.info(f"Vocabulary built: {len(self._word2idx)} words from {len(corpus)} documents")

    def _generate_training_pairs(self, corpus: List[str]) -> List[Tuple[int, int]]:
        pairs = []
        for text in corpus:
            tokens = self._tokenize(text)
            indices = [self._word2idx[t] for t in tokens if t in self._word2idx]
            for i, center in enumerate(indices):
                for j in range(max(0, i - self.WINDOW_SIZE), min(len(indices), i + self.WINDOW_SIZE + 1)):
                    if i != j:
                        pairs.append((center, indices[j]))
        return pairs

    def _negative_sampling(self, num_neg: int) -> np.ndarray:
        freq = np.array([self._word_freq.get(self._idx2word.get(i, ""), 1) for i in range(len(self._idx2word))])
        freq = np.power(freq, 0.75)
        freq = freq / freq.sum()
        return np.random.choice(len(freq), size=num_neg, p=freq)

    def train(self, corpus: List[str], epochs: int = 10):
        if not corpus:
            logger.warning("Empty corpus, skipping training")
            return

        self._build_vocab(corpus)
        if len(self._word2idx) < 2:
            logger.warning("Vocabulary too small for training")
            return

        self._model = SkipGramModel(len(self._word2idx), self.EMBED_DIM)
        pairs = self._generate_training_pairs(corpus)
        if not pairs:
            logger.warning("No training pairs generated")
            return

        logger.info(f"Training Skip-gram: {len(pairs)} pairs, {epochs} epochs")

        for epoch in range(epochs):
            np.random.shuffle(pairs)
            total_loss = 0.0
            lr = self.LEARNING_RATE * (1.0 - epoch / epochs)
            lr = max(lr, 0.001)

            for center, context in pairs:
                v_c = self._model.W_in[center]
                v_o = self._model.W_out[context]
                score = np.dot(v_c, v_o)
                score = np.clip(score, -10, 10)
                sig = 1.0 / (1.0 + np.exp(-score))
                grad_out = (sig - 1.0) * v_c
                grad_in = (sig - 1.0) * v_o
                self._model.W_out[context] -= lr * grad_out
                self._model.W_in[center] -= lr * grad_in
                total_loss += -np.log(sig + 1e-10)

                neg_indices = self._negative_sampling(self.NEGATIVE_SAMPLES)
                for neg in neg_indices:
                    v_n = self._model.W_out[neg]
                    score_neg = np.dot(v_c, v_n)
                    score_neg = np.clip(score_neg, -10, 10)
                    sig_neg = 1.0 / (1.0 + np.exp(score_neg))
                    grad_neg_out = (sig_neg - 0.0) * v_c
                    grad_neg_in = (sig_neg - 0.0) * v_n
                    self._model.W_out[neg] -= lr * grad_neg_out
                    self._model.W_in[center] -= lr * grad_neg_in

            if (epoch + 1) % 5 == 0 or epoch == 0:
                logger.info(f"Epoch {epoch + 1}/{epochs}, loss: {total_loss / len(pairs):.4f}")

        self._compute_reference_distribution(corpus)
        self._extract_term_vectors()
        self._trained = True
        self._save_model()
        logger.info("Skip-gram training complete")

    def _compute_reference_distribution(self, corpus: List[str]):
        all_embeddings = []
        for text in corpus:
            tokens = self._tokenize(text)
            for t in tokens:
                if t in self._word2idx:
                    all_embeddings.append(self._model.get_embedding(self._word2idx[t]))

        if not all_embeddings:
            return

        all_emb = np.array(all_embeddings)
        centroid = all_emb.mean(axis=0)
        dists = np.linalg.norm(all_emb - centroid, axis=1)
        n_bins = 20
        hist, _ = np.histogram(dists, bins=n_bins, density=True)
        self._reference_dist = hist / hist.sum()

    def _extract_term_vectors(self):
        for term in self.blacktalk_engine._term_index:
            tokens = self._tokenize(term)
            vectors = []
            for t in tokens:
                if t in self._word2idx:
                    vectors.append(self._model.get_embedding(self._word2idx[t]))
            if vectors:
                self._term_vectors[term] = np.mean(vectors, axis=0)

    def _compute_kl_drift(self, text: str) -> float:
        if not self._trained or self._reference_dist is None:
            return 0.0

        tokens = self._tokenize(text)
        vectors = []
        for t in tokens:
            if t in self._word2idx:
                vectors.append(self._model.get_embedding(self._word2idx[t]))

        if len(vectors) < 2:
            return 0.0

        emb = np.array(vectors)
        centroid = emb.mean(axis=0)
        dists = np.linalg.norm(emb - centroid, axis=1)
        n_bins = len(self._reference_dist)
        hist, _ = np.histogram(dists, bins=n_bins, density=True)
        current_dist = hist / hist.sum()

        kl_div = _safe_kl(current_dist, self._reference_dist)
        return min(kl_div, 2.0)

    def _compute_context_anomaly(self, term: str, context: str) -> float:
        if not self._trained or term not in self._term_vectors:
            return 0.5

        term_vec = self._term_vectors[term]
        context_tokens = self._tokenize(context)
        context_vecs = []
        for t in context_tokens:
            if t in self._word2idx:
                context_vecs.append(self._model.get_embedding(self._word2idx[t]))

        if not context_vecs:
            return 0.5

        context_mean = np.mean(context_vecs, axis=0)
        norm_term = np.linalg.norm(term_vec)
        norm_context = np.linalg.norm(context_mean)

        if norm_term < 1e-8 or norm_context < 1e-8:
            return 0.5

        similarity = float(np.dot(term_vec, context_mean) / (norm_term * norm_context))
        anomaly = 1.0 - max(0.0, min(1.0, (similarity + 1) / 2))
        return anomaly

    def _detect_unknown_terms(self, text: str) -> List[Dict]:
        tokens = self._tokenize(text)
        known_terms = set(self.blacktalk_engine._term_index.keys())
        candidates = []

        for i in range(len(tokens)):
            for length in range(2, min(5, len(tokens) - i + 1)):
                ngram = "".join(tokens[i:i + length])
                if ngram in known_terms:
                    continue
                if len(ngram) < 2:
                    continue
                if ngram.isascii() and len(ngram) < 3:
                    continue

                context_anomaly = self._compute_context_anomaly(ngram, text)
                kl_drift = self._compute_kl_drift(text)

                confidence = 0.0
                if context_anomaly > 0.4:
                    confidence += 0.3
                if kl_drift > self.DRIFT_THRESHOLD:
                    confidence += 0.3
                if any(kw in text for kw in ["出售", "价格", "佣金", "套现", "跑分", "通道", "接码", "养号", "出", "求购", "招募"]):
                    confidence += 0.2
                if context_anomaly > 0.6:
                    confidence += 0.2

                confidence = min(confidence, 1.0)

                if confidence >= self.CONFIDENCE_THRESHOLD:
                    candidates.append({
                        "term": ngram,
                        "confidence": confidence,
                        "context_anomaly": context_anomaly,
                        "kl_drift": kl_drift,
                        "context": text[max(0, text.find(ngram) - 20):text.find(ngram) + len(ngram) + 20],
                    })

        seen = set()
        unique = []
        for c in sorted(candidates, key=lambda x: x["confidence"], reverse=True):
            if c["term"] not in seen:
                seen.add(c["term"])
                unique.append(c)

        return unique

    async def detect_zero_day_terms(self, text: str) -> List:
        from app.core.zero_day_detector import ZeroDayTerm

        if not self._trained:
            self._try_load_model()

        known_terms = set(self.blacktalk_engine._term_index.keys())
        candidates = self._detect_unknown_terms(text)

        results = []
        for c in candidates:
            term = c["term"]
            if term in known_terms:
                continue
            if self._is_in_dictionary(term):
                continue

            category = self._infer_category_from_context(c["context"])
            results.append(ZeroDayTerm(
                term=term,
                normal_meaning=self._guess_normal_meaning(term),
                criminal_meaning=self._guess_criminal_meaning(c["context"], term),
                confidence=c["confidence"],
                context=c["context"],
                category=category,
                is_truly_new=True,
            ))

        results.sort(key=lambda t: t.confidence, reverse=True)
        logger.info(f"Zero-day detection: {len(results)} new terms found (KL drift + context anomaly)")
        return results

    def _is_in_dictionary(self, term: str) -> bool:
        return term in self.blacktalk_engine._term_index

    def _infer_category_from_context(self, context: str) -> str:
        category_keywords = {
            "money_laundering": ["跑分", "水房", "套现", "通道", "四件套", "走账", "洗白", "码商"],
            "fraud": ["诈骗", "杀猪", "套路", "话术", "引流", "薅羊毛", "接码", "养号"],
            "gambling": ["菠菜", "盘口", "菜农", "代理", "返水"],
            "hacking": ["木马", "挂马", "漏洞", "入侵", "脱库", "撞库", "肉鸡", "DDoS"],
            "drug": ["毒品", "大麻", "冰毒"],
        }
        for cat, kws in category_keywords.items():
            for kw in kws:
                if kw in context:
                    return cat
        return "other"

    def _guess_normal_meaning(self, term: str) -> str:
        if term.isascii():
            return f"英文术语"
        if len(term) <= 2:
            return f"常见缩写"
        return f"常规含义待确认"

    def _guess_criminal_meaning(self, context: str, term: str) -> str:
        meaning_hints = {
            "出售": "可能与非法交易相关",
            "价格": "可能与黑产定价相关",
            "佣金": "可能与黑产分赃相关",
            "通道": "可能与资金通道相关",
            "跑分": "可能与洗钱相关",
            "接码": "可能与验证码服务相关",
            "养号": "可能与账号培育相关",
        }
        for hint, meaning in meaning_hints.items():
            if hint in context:
                return meaning
        return "黑灰产含义待确认"

    async def track_semantic_drift(self, term: str) -> "SemanticDriftResult":
        from app.core.zero_day_detector import SemanticDriftResult

        if not self._trained:
            self._try_load_model()

        historical_uses = await self._find_historical_uses(term)

        if not historical_uses:
            return SemanticDriftResult(
                term=term, original_meaning="", current_meaning="",
                drift_timeline=[], drift_velocity=0.0,
            )

        dict_meaning = ""
        if term in self.blacktalk_engine._term_index:
            term_id = self.blacktalk_engine._term_index[term]
            bt = self.blacktalk_engine._dictionary.get(term_id)
            if bt:
                dict_meaning = bt.meaning

        timeline = []
        drift_scores = []
        for u in historical_uses:
            content = u.get("content", "")
            kl = self._compute_kl_drift(content)
            anomaly = self._compute_context_anomaly(term, content)
            drift_score = (kl + anomaly) / 2.0
            drift_scores.append(drift_score)
            timeline.append({
                "date": u.get("timestamp", "未知"),
                "meaning": f"上下文异常度: {anomaly:.2f}, KL散度: {kl:.2f}",
                "source": u.get("source", "未知"),
                "drift_score": drift_score,
            })

        drift_velocity = float(np.mean(drift_scores)) if drift_scores else 0.0

        current_meaning = dict_meaning
        if drift_velocity > self.DRIFT_THRESHOLD and len(historical_uses) > 1:
            latest = historical_uses[-1].get("content", "")
            current_meaning = f"[语义漂移检测] 原始: {dict_meaning}, 当前上下文暗示含义可能已变化 (漂移速度: {drift_velocity:.2f})"

        return SemanticDriftResult(
            term=term,
            original_meaning=dict_meaning or "未知",
            current_meaning=current_meaning,
            drift_timeline=timeline,
            drift_velocity=drift_velocity,
        )

    async def _find_historical_uses(self, term: str) -> List[Dict]:
        results = await self.vector_store.search_intelligence(term, n_results=20)
        uses = []
        for result in results:
            doc = result.get("document", "")
            metadata = result.get("metadata", {})
            if not doc:
                continue
            uses.append({
                "content": doc[:500],
                "timestamp": metadata.get("collected_at", metadata.get("timestamp", "")),
                "source": metadata.get("source", "unknown"),
                "id": result.get("id", ""),
            })
        uses.sort(key=lambda u: u.get("timestamp", "") or "")
        return uses

    async def track_cross_platform_migration(self, term: str) -> "MigrationResult":
        from app.core.zero_day_detector import MigrationResult

        platform_uses = await self._find_platform_uses(term)

        if not platform_uses:
            return MigrationResult(
                term=term, origin_platform="unknown",
                migration_path=[], current_platforms=[], spread_speed=0.0,
            )

        earliest_platform = None
        earliest_time = None
        migration_path = []
        current_platforms = []

        for platform, uses in platform_uses.items():
            if uses:
                first_seen = uses[0].get("timestamp", "")
                count = len(uses)
                migration_path.append({
                    "platform": platform,
                    "first_seen": first_seen,
                    "count": count,
                })
                current_platforms.append(platform)
                if earliest_time is None or (first_seen and first_seen < earliest_time):
                    earliest_time = first_seen
                    earliest_platform = platform

        migration_path.sort(key=lambda p: p.get("first_seen", "") or "")

        num_platforms = len(platform_uses)
        total_uses = sum(len(uses) for uses in platform_uses.values())
        spread_speed = min(num_platforms / 5.0, 1.0) * min(total_uses / 10.0, 1.0)

        return MigrationResult(
            term=term,
            origin_platform=earliest_platform or "unknown",
            migration_path=migration_path,
            current_platforms=current_platforms,
            spread_speed=spread_speed,
        )

    async def _find_platform_uses(self, term: str) -> Dict[str, List[Dict]]:
        results = await self.vector_store.search_intelligence(term, n_results=30)
        platform_uses: Dict[str, List[Dict]] = {}
        for result in results:
            metadata = result.get("metadata", {})
            source = metadata.get("source", "unknown")
            if source not in platform_uses:
                platform_uses[source] = []
            platform_uses[source].append({
                "content": result.get("document", "")[:300],
                "timestamp": metadata.get("collected_at", metadata.get("timestamp", "")),
                "id": result.get("id", ""),
            })
        for platform in platform_uses:
            platform_uses[platform].sort(key=lambda u: u.get("timestamp", "") or "")
        return platform_uses

    def _save_model(self):
        if self._model is None:
            return
        model_path = os.path.join(self._persist_dir, "skipgram.npz")
        self._model.save(model_path)
        meta = {
            "word2idx": self._word2idx,
            "trained": self._trained,
        }
        meta_path = os.path.join(self._persist_dir, "metadata.pkl")
        with open(meta_path, "wb") as f:
            pickle.dump(meta, f)
        if self._reference_dist is not None:
            ref_path = os.path.join(self._persist_dir, "reference_dist.npy")
            np.save(ref_path, self._reference_dist)
        logger.info(f"Zero-day model saved to {self._persist_dir}")

    def _try_load_model(self) -> bool:
        model_path = os.path.join(self._persist_dir, "skipgram.npz")
        meta_path = os.path.join(self._persist_dir, "metadata.pkl")
        ref_path = os.path.join(self._persist_dir, "reference_dist.npy")

        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            return False

        try:
            self._model = SkipGramModel.load(model_path)
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)
            self._word2idx = meta.get("word2idx", {})
            self._idx2word = {v: k for k, v in self._word2idx.items()}
            self._trained = meta.get("trained", False)
            if os.path.exists(ref_path):
                self._reference_dist = np.load(ref_path)
            self._extract_term_vectors()
            logger.info(f"Zero-day model loaded: vocab={len(self._word2idx)}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to load zero-day model: {exc}")
            return False
