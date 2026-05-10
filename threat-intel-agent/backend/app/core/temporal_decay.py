import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger
from scipy.optimize import minimize

from app.core.vector_store import VectorStore


DEFAULT_HALF_LIVES_HOURS = {
    "ip": 72,
    "phone": 168,
    "bank_card": 336,
    "domain": 720,
    "url": 720,
    "ttp": 2160,
    "organization": 4320,
    "blacktalk": 8760,
    "policy": 17520,
}

TYPE_KEYWORDS = {
    "ip": ["ip", "ip地址", "IP", "IP地址"],
    "phone": ["手机", "电话", "手机号", "电话号码", "phone"],
    "bank_card": ["银行卡", "卡号", "信用卡", "bank_card"],
    "domain": ["域名", "domain", "网址", "网站"],
    "url": ["url", "URL", "链接", "link"],
    "ttp": ["攻击手法", "TTP", "技术", "战术", "手法", "漏洞", "exploit"],
    "organization": ["组织", "团伙", "集团", "团队", "organization"],
    "blacktalk": ["黑话", "暗语", "术语", "黑话术语", "blacktalk"],
    "policy": ["法规", "政策", "法律", "条例", "policy"],
}

STATUS_THRESHOLDS = {
    "fresh": 0.8,
    "active": 0.5,
    "stale": 0.2,
}

MLE_MIN_OBSERVATIONS = 3
MLE_HALF_LIFE_BOUNDS = (1.0, 100000.0)


@dataclass
class DecayResult:
    intelligence_id: str
    intelligence_type: str
    original_confidence: float
    current_confidence: float
    half_life_hours: float
    elapsed_hours: float
    decay_percentage: float
    is_expired: bool
    status: str

    def to_dict(self) -> dict:
        return {
            "intelligence_id": self.intelligence_id,
            "intelligence_type": self.intelligence_type,
            "original_confidence": self.original_confidence,
            "current_confidence": self.current_confidence,
            "half_life_hours": self.half_life_hours,
            "elapsed_hours": self.elapsed_hours,
            "decay_percentage": self.decay_percentage,
            "is_expired": self.is_expired,
            "status": self.status,
        }


@dataclass
class DecayCurve:
    intelligence_id: str
    intelligence_type: str
    half_life_hours: float
    data_points: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intelligence_id": self.intelligence_id,
            "intelligence_type": self.intelligence_type,
            "half_life_hours": self.half_life_hours,
            "data_points": self.data_points,
        }


@dataclass
class BatchDecayResult:
    total: int
    fresh_count: int
    active_count: int
    stale_count: int
    expired_count: int
    items: List[DecayResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "fresh_count": self.fresh_count,
            "active_count": self.active_count,
            "stale_count": self.stale_count,
            "expired_count": self.expired_count,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class DecayBatch:
    items: List[DecayResult] = field(default_factory=list)
    total: int = 0
    fresh_count: int = 0
    active_count: int = 0
    stale_count: int = 0
    expired_count: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "fresh_count": self.fresh_count,
            "active_count": self.active_count,
            "stale_count": self.stale_count,
            "expired_count": self.expired_count,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class RefreshRecommendation:
    intelligence_id: str
    content_preview: str
    current_confidence: float
    original_confidence: float
    recommended_action: str
    urgency: str
    intelligence_type: str

    def to_dict(self) -> dict:
        return {
            "intelligence_id": self.intelligence_id,
            "content_preview": self.content_preview,
            "current_confidence": self.current_confidence,
            "original_confidence": self.original_confidence,
            "recommended_action": self.recommended_action,
            "urgency": self.urgency,
            "intelligence_type": self.intelligence_type,
        }


@dataclass
class DecayRecommendation:
    intelligence_id: str
    content_preview: str
    current_confidence: float
    original_confidence: float
    recommended_action: str
    urgency: str
    intelligence_type: str

    def to_dict(self) -> dict:
        return {
            "intelligence_id": self.intelligence_id,
            "content_preview": self.content_preview,
            "current_confidence": self.current_confidence,
            "original_confidence": self.original_confidence,
            "recommended_action": self.recommended_action,
            "urgency": self.urgency,
            "intelligence_type": self.intelligence_type,
        }


class TemporalDecay:
    DEFAULT_HALF_LIFE = 720
    EXPIRED_THRESHOLD = 0.2
    CURVE_POINTS = 20
    MODEL_PERSIST_DIR = Path("./model_data/temporal_decay")

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self._intelligence_registry: Dict[str, Dict] = {}
        self._observations: Dict[str, List[Dict]] = {}
        self._learned_half_lives: Dict[str, float] = {}
        self._half_lives: Dict[str, float] = dict(DEFAULT_HALF_LIVES_HOURS)

        self._load_learned_half_lives()

    def _load_learned_half_lives(self):
        if not self.MODEL_PERSIST_DIR.exists():
            return
        try:
            data_file = self.MODEL_PERSIST_DIR / "learned_half_lives.json"
            if not data_file.exists():
                return
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._learned_half_lives = {
                k: float(v) for k, v in data.get("half_lives", {}).items()
            }
            self._observations = data.get("observations", {})
            for itype, hl in self._learned_half_lives.items():
                self._half_lives[itype] = hl
            logger.info(
                f"Loaded {len(self._learned_half_lives)} learned half-lives from disk"
            )
        except Exception as exc:
            logger.warning(f"Failed to load learned half-lives: {exc}")

    def _save_learned_half_lives(self):
        try:
            self.MODEL_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "half_lives": self._learned_half_lives,
                "observations": self._observations,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            data_file = self.MODEL_PERSIST_DIR / "learned_half_lives.json"
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(
                f"Saved {len(self._learned_half_lives)} learned half-lives to disk"
            )
        except Exception as exc:
            logger.warning(f"Failed to save learned half-lives: {exc}")

    def register_intelligence(
        self,
        intelligence_id: str,
        intelligence_type: str,
        original_confidence: float,
        timestamp: str,
        content: str = "",
    ):
        self._intelligence_registry[intelligence_id] = {
            "type": intelligence_type,
            "original_confidence": original_confidence,
            "timestamp": timestamp,
            "content": content,
        }

    def record_observation(
        self,
        intelligence_id: str,
        intelligence_type: str,
        observed_confidence: float,
        observed_at: str,
        original_confidence: float,
        original_timestamp: str,
    ):
        if intelligence_type not in self._observations:
            self._observations[intelligence_type] = []

        self._observations[intelligence_type].append(
            {
                "intelligence_id": intelligence_id,
                "original_confidence": original_confidence,
                "observed_confidence": observed_confidence,
                "original_timestamp": original_timestamp,
                "observed_at": observed_at,
            }
        )

        obs_count = len(self._observations[intelligence_type])
        if obs_count >= MLE_MIN_OBSERVATIONS:
            self._estimate_half_life_mle(intelligence_type)

    def _estimate_half_life_mle(self, intelligence_type: str):
        observations = self._observations.get(intelligence_type, [])
        if len(observations) < MLE_MIN_OBSERVATIONS:
            return

        prior = DEFAULT_HALF_LIVES_HOURS.get(
            intelligence_type, self.DEFAULT_HALF_LIFE
        )

        try:
            elapsed_hours_list = []
            confidence_ratios = []
            for obs in observations:
                orig_ts = self._parse_timestamp(obs["original_timestamp"])
                obs_ts = self._parse_timestamp(obs["observed_at"])
                elapsed = (obs_ts - orig_ts).total_seconds() / 3600.0
                if elapsed <= 0:
                    continue
                orig_conf = max(float(obs["original_confidence"]), 0.001)
                ratio = float(obs["observed_confidence"]) / orig_conf
                ratio = np.clip(ratio, 1e-6, 1.0)
                elapsed_hours_list.append(elapsed)
                confidence_ratios.append(ratio)

            if len(elapsed_hours_list) < MLE_MIN_OBSERVATIONS:
                return

            elapsed_arr = np.array(elapsed_hours_list, dtype=np.float64)
            ratio_arr = np.array(confidence_ratios, dtype=np.float64)

            def neg_log_likelihood(log_hl: np.ndarray) -> float:
                hl = np.exp(log_hl[0])
                predicted = np.power(0.5, elapsed_arr / hl)
                residuals = ratio_arr - predicted
                sigma = np.std(residuals) + 1e-8
                nll = 0.5 * np.sum((residuals / sigma) ** 2) + len(
                    residuals
                ) * np.log(sigma + 1e-8)
                return float(nll)

            x0 = np.array([np.log(prior)])
            bounds = [
                (
                    np.log(MLE_HALF_LIFE_BOUNDS[0]),
                    np.log(MLE_HALF_LIFE_BOUNDS[1]),
                )
            ]

            result = minimize(
                neg_log_likelihood,
                x0,
                method="L-BFGS-B",
                bounds=bounds,
            )

            if result.success:
                estimated_hl = float(np.exp(result.x[0]))
                self._learned_half_lives[intelligence_type] = estimated_hl
                self._half_lives[intelligence_type] = estimated_hl
                logger.info(
                    f"MLE estimated half-life for '{intelligence_type}': "
                    f"{estimated_hl:.1f} hours (prior: {prior} hours, "
                    f"observations: {len(elapsed_hours_list)})"
                )
                self._save_learned_half_lives()
            else:
                logger.warning(
                    f"MLE optimization failed for '{intelligence_type}': "
                    f"{result.message}, keeping prior"
                )
        except Exception as exc:
            logger.warning(
                f"MLE half-life estimation failed for '{intelligence_type}': {exc}"
            )

    def _classify_type(self, content: str, metadata: Dict = None) -> str:
        if metadata:
            entity_type = metadata.get("entity_type", metadata.get("type", ""))
            if entity_type:
                type_lower = entity_type.lower()
                for known_type in DEFAULT_HALF_LIVES_HOURS:
                    if known_type in type_lower:
                        return known_type

        if content:
            content_lower = content.lower()
            best_type = "ttp"
            best_score = 0
            for itype, keywords in TYPE_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in content_lower)
                if score > best_score:
                    best_score = score
                    best_type = itype
            if best_score > 0:
                return best_type

        return "ttp"

    def _get_half_life(self, intelligence_type: str) -> float:
        return self._half_lives.get(intelligence_type, self.DEFAULT_HALF_LIFE)

    def _compute_decay(
        self,
        original_confidence: float,
        elapsed_hours: float,
        half_life_hours: float,
    ) -> float:
        if elapsed_hours <= 0:
            return original_confidence
        return float(
            original_confidence * np.power(0.5, elapsed_hours / half_life_hours)
        )

    def _get_status(self, current_confidence: float) -> str:
        if current_confidence >= STATUS_THRESHOLDS["fresh"]:
            return "fresh"
        if current_confidence >= STATUS_THRESHOLDS["active"]:
            return "active"
        if current_confidence >= STATUS_THRESHOLDS["stale"]:
            return "stale"
        return "expired"

    def _parse_timestamp(self, timestamp) -> datetime:
        if isinstance(timestamp, datetime):
            return timestamp
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            try:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return datetime.now(timezone.utc)

    async def _lookup_intelligence(self, intelligence_id: str) -> Optional[Dict]:
        try:
            results = await self.vector_store.search_intelligence(
                intelligence_id, n_results=5
            )
            for result in results:
                if result.get("id") == intelligence_id:
                    metadata = result.get("metadata", {})
                    return {
                        "type": metadata.get(
                            "entity_type", metadata.get("type", "unknown")
                        ),
                        "original_confidence": metadata.get("confidence", 0.5),
                        "timestamp": metadata.get(
                            "collected_at", metadata.get("timestamp", "")
                        ),
                        "content": result.get("document", ""),
                        "metadata": metadata,
                    }
        except Exception as exc:
            logger.warning(
                f"Intelligence lookup failed for '{intelligence_id}': {exc}"
            )

        return None

    async def compute_current_confidence(
        self, intelligence_id: str
    ) -> DecayResult:
        info = self._intelligence_registry.get(intelligence_id)

        if not info:
            info = await self._lookup_intelligence(intelligence_id)
            if not info:
                return DecayResult(
                    intelligence_id=intelligence_id,
                    intelligence_type="unknown",
                    original_confidence=0.0,
                    current_confidence=0.0,
                    half_life_hours=0.0,
                    elapsed_hours=0.0,
                    decay_percentage=100.0,
                    is_expired=True,
                    status="expired",
                )

        intelligence_type = info.get("type", "")
        if not intelligence_type or intelligence_type == "unknown":
            intelligence_type = self._classify_type(
                info.get("content", ""), info.get("metadata")
            )

        original_confidence = float(info.get("original_confidence", 0.5))
        timestamp = info.get("timestamp", "")
        created_at = self._parse_timestamp(timestamp)
        now = datetime.now(timezone.utc)

        elapsed = now - created_at
        elapsed_hours = max(elapsed.total_seconds() / 3600, 0)

        half_life = self._get_half_life(intelligence_type)
        current_confidence = self._compute_decay(
            original_confidence, elapsed_hours, half_life
        )

        decay_percentage = 0.0
        if original_confidence > 0:
            decay_percentage = (
                (1.0 - current_confidence / original_confidence) * 100
            )

        is_expired = current_confidence < self.EXPIRED_THRESHOLD * original_confidence
        status = self._get_status(
            current_confidence / max(original_confidence, 0.001)
        )

        return DecayResult(
            intelligence_id=intelligence_id,
            intelligence_type=intelligence_type,
            original_confidence=original_confidence,
            current_confidence=round(current_confidence, 6),
            half_life_hours=half_life,
            elapsed_hours=round(elapsed_hours, 2),
            decay_percentage=round(decay_percentage, 2),
            is_expired=is_expired,
            status=status,
        )

    async def compute_decay_curve(self, intelligence_id: str) -> DecayCurve:
        info = self._intelligence_registry.get(intelligence_id)
        if not info:
            info = await self._lookup_intelligence(intelligence_id)

        if not info:
            return DecayCurve(
                intelligence_id=intelligence_id,
                intelligence_type="unknown",
                half_life_hours=0,
            )

        intelligence_type = info.get("type", "")
        if not intelligence_type or intelligence_type == "unknown":
            intelligence_type = self._classify_type(
                info.get("content", ""), info.get("metadata")
            )

        original_confidence = float(info.get("original_confidence", 0.5))
        half_life = self._get_half_life(intelligence_type)

        total_hours = half_life * 5
        step = total_hours / self.CURVE_POINTS

        data_points: List[Dict] = []
        for i in range(self.CURVE_POINTS + 1):
            hours = i * step
            confidence = self._compute_decay(
                original_confidence, hours, half_life
            )
            ratio = confidence / max(original_confidence, 0.001)

            label = ""
            if i == 0:
                label = "初始"
            elif hours <= half_life * 0.5:
                label = "新鲜"
            elif hours <= half_life:
                label = "半衰期"
            elif hours <= half_life * 2:
                label = "衰减中"
            elif hours <= half_life * 3:
                label = "陈旧"
            else:
                label = "过期"

            data_points.append(
                {
                    "hours": round(hours, 1),
                    "confidence": round(confidence, 6),
                    "label": label,
                }
            )

        return DecayCurve(
            intelligence_id=intelligence_id,
            intelligence_type=intelligence_type,
            half_life_hours=half_life,
            data_points=data_points,
        )

    async def batch_decay(self) -> BatchDecayResult:
        all_ids = list(self._intelligence_registry.keys())

        if not all_ids:
            try:
                col = self.vector_store._collections.get("intelligence")
                if col:
                    all_ids = list(col.get(include=[])["ids"])
            except Exception:
                pass

        items: List[DecayResult] = []
        fresh_count = 0
        active_count = 0
        stale_count = 0
        expired_count = 0

        for intel_id in all_ids:
            try:
                result = await self.compute_current_confidence(intel_id)
                items.append(result)

                if result.status == "fresh":
                    fresh_count += 1
                elif result.status == "active":
                    active_count += 1
                elif result.status == "stale":
                    stale_count += 1
                else:
                    expired_count += 1
            except Exception as exc:
                logger.warning(
                    f"Batch decay analysis failed for '{intel_id}': {exc}"
                )
                expired_count += 1

        return BatchDecayResult(
            total=len(all_ids),
            fresh_count=fresh_count,
            active_count=active_count,
            stale_count=stale_count,
            expired_count=expired_count,
            items=items,
        )

    async def batch_decay_analysis(self) -> BatchDecayResult:
        return await self.batch_decay()

    async def recommendations(self) -> List[DecayRecommendation]:
        all_ids = list(self._intelligence_registry.keys())

        if not all_ids:
            try:
                col = self.vector_store._collections.get("intelligence")
                if col:
                    all_ids = list(col.get(include=[])["ids"])
            except Exception:
                pass

        recs: List[DecayRecommendation] = []

        for intel_id in all_ids:
            try:
                decay = await self.compute_current_confidence(intel_id)
            except Exception as exc:
                logger.warning(
                    f"Decay computation failed for '{intel_id}': {exc}"
                )
                continue

            if decay.status in ("fresh", "active"):
                continue

            info = self._intelligence_registry.get(intel_id, {})
            content_preview = info.get("content", "")[:100]

            urgency, action = self._determine_refresh_action(decay)

            recs.append(
                DecayRecommendation(
                    intelligence_id=intel_id,
                    content_preview=content_preview,
                    current_confidence=decay.current_confidence,
                    original_confidence=decay.original_confidence,
                    recommended_action=action,
                    urgency=urgency,
                    intelligence_type=decay.intelligence_type,
                )
            )

        recs.sort(
            key=lambda r: {"immediate": 0, "soon": 1, "routine": 2}.get(
                r.urgency, 2
            )
        )
        return recs

    async def recommend_refresh(self) -> List[RefreshRecommendation]:
        decay_recs = await self.recommendations()
        return [
            RefreshRecommendation(
                intelligence_id=r.intelligence_id,
                content_preview=r.content_preview,
                current_confidence=r.current_confidence,
                original_confidence=r.original_confidence,
                recommended_action=r.recommended_action,
                urgency=r.urgency,
                intelligence_type=r.intelligence_type,
            )
            for r in decay_recs
        ]

    def _determine_refresh_action(self, decay: DecayResult) -> Tuple[str, str]:
        if decay.status == "expired":
            if decay.current_confidence < 0.05:
                return (
                    "immediate",
                    "情报已严重过期，建议立即重新采集或标记为无效",
                )
            return "soon", "情报已过期，建议尽快重新验证或更新"

        if decay.status == "stale":
            if decay.current_confidence < 0.3:
                return "soon", "情报即将过期，建议在近期重新验证"
            return "routine", "情报正在衰减，建议定期检查更新"

        return "routine", "建议定期复查"

    def get_half_lives_info(self) -> Dict:
        result = {}
        for itype, default_hl in DEFAULT_HALF_LIVES_HOURS.items():
            learned = self._learned_half_lives.get(itype)
            obs_count = len(self._observations.get(itype, []))
            result[itype] = {
                "default_half_life": default_hl,
                "learned_half_life": learned,
                "active_half_life": self._half_lives.get(
                    itype, self.DEFAULT_HALF_LIFE
                ),
                "observation_count": obs_count,
                "mle_estimated": learned is not None,
            }
        return result
