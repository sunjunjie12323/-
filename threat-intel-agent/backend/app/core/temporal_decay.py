import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.knowledge_graph import KnowledgeGraph
from app.core.llm import LLMService
from app.core.vector_store import VectorStore


HALF_LIVES_HOURS = {
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


class TemporalDecay:
    DEFAULT_HALF_LIFE = 720
    EXPIRED_THRESHOLD = 0.2
    CURVE_POINTS = 20

    def __init__(self, llm: LLMService, vector_store: VectorStore, knowledge_graph: KnowledgeGraph):
        self.llm = llm
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self._intelligence_registry: Dict[str, Dict] = {}

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

    def _classify_type(self, content: str, metadata: Dict = None) -> str:
        if metadata:
            entity_type = metadata.get("entity_type", metadata.get("type", ""))
            if entity_type:
                type_lower = entity_type.lower()
                for known_type in HALF_LIVES_HOURS:
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
        return HALF_LIVES_HOURS.get(intelligence_type, self.DEFAULT_HALF_LIFE)

    def _compute_decay(
        self, original_confidence: float, elapsed_hours: float, half_life_hours: float
    ) -> float:
        if elapsed_hours <= 0:
            return original_confidence
        return original_confidence * (0.5 ** (elapsed_hours / half_life_hours))

    def _get_status(self, current_confidence: float) -> str:
        if current_confidence >= STATUS_THRESHOLDS["fresh"]:
            return "fresh"
        if current_confidence >= STATUS_THRESHOLDS["active"]:
            return "active"
        if current_confidence >= STATUS_THRESHOLDS["stale"]:
            return "stale"
        return "expired"

    def _parse_timestamp(self, timestamp: str) -> datetime:
        if isinstance(timestamp, datetime):
            return timestamp
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            try:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return datetime.utcnow()

    async def compute_current_confidence(self, intelligence_id: str) -> DecayResult:
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
        now = datetime.utcnow()

        if created_at.tzinfo is not None:
            from datetime import timezone
            now = datetime.now(timezone.utc)

        elapsed = now - created_at
        elapsed_hours = max(elapsed.total_seconds() / 3600, 0)

        half_life = self._get_half_life(intelligence_type)
        current_confidence = self._compute_decay(original_confidence, elapsed_hours, half_life)

        decay_percentage = 0.0
        if original_confidence > 0:
            decay_percentage = (1.0 - current_confidence / original_confidence) * 100

        is_expired = current_confidence < self.EXPIRED_THRESHOLD * original_confidence
        status = self._get_status(current_confidence / max(original_confidence, 0.001))

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

    async def _lookup_intelligence(self, intelligence_id: str) -> Optional[Dict]:
        entity = await self.knowledge_graph.get_entity(intelligence_id)
        if entity:
            return {
                "type": entity.type.value,
                "original_confidence": entity.confidence,
                "timestamp": entity.first_seen.isoformat() if entity.first_seen else "",
                "content": entity.context or entity.value,
                "metadata": entity.metadata,
            }

        try:
            results = await self.vector_store.search_intelligence(intelligence_id, n_results=1)
            for result in results:
                if result.get("id") == intelligence_id:
                    metadata = result.get("metadata", {})
                    return {
                        "type": metadata.get("entity_type", metadata.get("type", "unknown")),
                        "original_confidence": metadata.get("confidence", 0.5),
                        "timestamp": metadata.get("collected_at", metadata.get("timestamp", "")),
                        "content": result.get("document", ""),
                        "metadata": metadata,
                    }
        except Exception as exc:
            logger.warning(f"Intelligence lookup failed for '{intelligence_id}': {exc}")

        return None

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
            confidence = self._compute_decay(original_confidence, hours, half_life)
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

            data_points.append({
                "hours": round(hours, 1),
                "confidence": round(confidence, 6),
                "label": label,
            })

        return DecayCurve(
            intelligence_id=intelligence_id,
            intelligence_type=intelligence_type,
            half_life_hours=half_life,
            data_points=data_points,
        )

    async def batch_decay_analysis(self) -> BatchDecayResult:
        all_ids = list(self._intelligence_registry.keys())

        if not all_ids:
            graph_entities = self.knowledge_graph._entities
            for eid in graph_entities:
                all_ids.append(eid)

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
                logger.warning(f"Batch decay analysis failed for '{intel_id}': {exc}")
                expired_count += 1

        return BatchDecayResult(
            total=len(all_ids),
            fresh_count=fresh_count,
            active_count=active_count,
            stale_count=stale_count,
            expired_count=expired_count,
            items=items,
        )

    async def recommend_refresh(self) -> List[RefreshRecommendation]:
        all_ids = list(self._intelligence_registry.keys())

        if not all_ids:
            graph_entities = self.knowledge_graph._entities
            for eid in graph_entities:
                all_ids.append(eid)

        recommendations: List[RefreshRecommendation] = []

        for intel_id in all_ids:
            try:
                decay = await self.compute_current_confidence(intel_id)
            except Exception as exc:
                logger.warning(f"Decay computation failed for '{intel_id}': {exc}")
                continue

            if decay.status in ("fresh", "active"):
                continue

            info = self._intelligence_registry.get(intel_id, {})
            content_preview = info.get("content", "")[:100]

            if not content_preview:
                entity = await self.knowledge_graph.get_entity(intel_id)
                if entity:
                    content_preview = f"{entity.type.value}: {entity.value}"

            urgency, action = self._determine_refresh_action(decay)

            recommendations.append(RefreshRecommendation(
                intelligence_id=intel_id,
                content_preview=content_preview,
                current_confidence=decay.current_confidence,
                original_confidence=decay.original_confidence,
                recommended_action=action,
                urgency=urgency,
                intelligence_type=decay.intelligence_type,
            ))

        recommendations.sort(
            key=lambda r: {"immediate": 0, "soon": 1, "routine": 2}.get(r.urgency, 2)
        )
        return recommendations

    def _determine_refresh_action(self, decay: DecayResult) -> tuple:
        if decay.status == "expired":
            if decay.current_confidence < 0.05:
                return "immediate", "情报已严重过期，建议立即重新采集或标记为无效"
            return "soon", "情报已过期，建议尽快重新验证或更新"

        if decay.status == "stale":
            if decay.current_confidence < 0.3:
                return "soon", "情报即将过期，建议在近期重新验证"
            return "routine", "情报正在衰减，建议定期检查更新"

        return "routine", "建议定期复查"
