import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from uuid import uuid4

from loguru import logger

from app.core.knowledge_graph import KnowledgeGraph
from app.core.llm import LLMService
from app.core.vector_store import VectorStore


@dataclass
class BehavioralFingerprint:
    entity_id: str
    platform: str
    linguistic_features: Dict = field(default_factory=dict)
    active_hours: Dict = field(default_factory=dict)
    operation_types: List[str] = field(default_factory=list)
    price_patterns: Dict = field(default_factory=dict)
    social_connections: List[str] = field(default_factory=list)
    fingerprint_vector: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "platform": self.platform,
            "linguistic_features": self.linguistic_features,
            "active_hours": self.active_hours,
            "operation_types": self.operation_types,
            "price_patterns": self.price_patterns,
            "social_connections": self.social_connections,
            "fingerprint_vector": self.fingerprint_vector,
        }


@dataclass
class AttributionMatch:
    source_entity_id: str
    source_platform: str
    target_entity_id: str
    target_platform: str
    overall_similarity: float
    linguistic_similarity: float = 0.0
    temporal_similarity: float = 0.0
    behavioral_similarity: float = 0.0
    network_similarity: float = 0.0
    evidence: List[str] = field(default_factory=list)
    confidence: str = "low"

    def to_dict(self) -> dict:
        return {
            "source_entity_id": self.source_entity_id,
            "source_platform": self.source_platform,
            "target_entity_id": self.target_entity_id,
            "target_platform": self.target_platform,
            "overall_similarity": self.overall_similarity,
            "linguistic_similarity": self.linguistic_similarity,
            "temporal_similarity": self.temporal_similarity,
            "behavioral_similarity": self.behavioral_similarity,
            "network_similarity": self.network_similarity,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


@dataclass
class AttributionReport:
    entity_id: str
    primary_platform: str
    aliases: List[AttributionMatch] = field(default_factory=list)
    total_platforms: int = 1
    risk_assessment: str = ""
    evidence_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "primary_platform": self.primary_platform,
            "aliases": [a.to_dict() for a in self.aliases],
            "total_platforms": self.total_platforms,
            "risk_assessment": self.risk_assessment,
            "evidence_summary": self.evidence_summary,
        }


class EntityAttribution:
    WEIGHTS = {
        "linguistic": 0.3,
        "temporal": 0.2,
        "behavioral": 0.3,
        "network": 0.2,
    }
    VECTOR_DIM = 64

    def __init__(self, llm: LLMService, vector_store: VectorStore, knowledge_graph: KnowledgeGraph):
        self.llm = llm
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self._fingerprint_cache: Dict[str, BehavioralFingerprint] = {}

    async def compute_behavioral_fingerprint(self, entity_id: str) -> BehavioralFingerprint:
        if entity_id in self._fingerprint_cache:
            return self._fingerprint_cache[entity_id]

        entity = await self.knowledge_graph.get_entity(entity_id)
        if not entity:
            return BehavioralFingerprint(entity_id=entity_id, platform="unknown")

        platform = entity.metadata.get("source", entity.metadata.get("platform", "unknown"))

        intelligence_texts = await self._gather_entity_intelligence(entity_id)
        relations = await self.knowledge_graph.get_entity_relations(entity_id)

        linguistic_features = await self._extract_linguistic_features(
            entity_id, intelligence_texts
        )
        active_hours = self._extract_active_hours(intelligence_texts)
        operation_types = await self._extract_operation_types(
            entity_id, intelligence_texts
        )
        price_patterns = self._extract_price_patterns(intelligence_texts)
        social_connections = self._extract_social_connections(entity_id, relations)

        fingerprint_vector = self._build_fingerprint_vector(
            linguistic_features, active_hours, operation_types, price_patterns, social_connections
        )

        fingerprint = BehavioralFingerprint(
            entity_id=entity_id,
            platform=platform,
            linguistic_features=linguistic_features,
            active_hours=active_hours,
            operation_types=operation_types,
            price_patterns=price_patterns,
            social_connections=social_connections,
            fingerprint_vector=fingerprint_vector,
        )

        self._fingerprint_cache[entity_id] = fingerprint
        return fingerprint

    async def _gather_entity_intelligence(self, entity_id: str) -> List[Dict]:
        results = await self.vector_store.search_intelligence(entity_id, n_results=20)
        texts: List[Dict] = []
        for result in results:
            doc = result.get("document", "")
            metadata = result.get("metadata", {})
            if doc:
                texts.append({
                    "content": doc,
                    "timestamp": metadata.get("collected_at", metadata.get("timestamp", "")),
                    "source": metadata.get("source", "unknown"),
                })
        return texts

    async def _extract_linguistic_features(
        self, entity_id: str, intelligence_texts: List[Dict]
    ) -> Dict:
        if not intelligence_texts:
            return {}

        combined_text = "\n".join(t.get("content", "")[:300] for t in intelligence_texts[:10])

        try:
            system_prompt = (
                "你是一个文本风格分析专家。分析以下文本的写作风格特征。\n"
                "输出JSON格式：\n"
                '{"avg_sentence_length":20.5,"emoji_frequency":0.1,'
                '"punctuation_style":"heavy","formality_level":0.3,'
                '"dialect_markers":["标记1"],"common_phrases":["短语1"],'
                '"sentence_pattern":"short_imperative"}\n'
                "只返回JSON，不要其他内容。"
            )
            prompt = f"分析以下文本的写作风格：\n\n{combined_text[:2000]}"

            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.2,
            )
            return result
        except Exception as exc:
            logger.warning(f"LLM linguistic feature extraction failed for '{entity_id}': {exc}")
            return self._heuristic_linguistic_features(combined_text)

    def _heuristic_linguistic_features(self, text: str) -> Dict:
        sentences = text.split("。")
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

        emoji_count = sum(1 for c in text if ord(c) > 0x1F000)
        emoji_freq = emoji_count / max(len(text), 1)

        return {
            "avg_sentence_length": avg_len,
            "emoji_frequency": round(emoji_freq, 4),
            "punctuation_style": "normal",
            "formality_level": 0.5,
            "dialect_markers": [],
            "common_phrases": [],
            "sentence_pattern": "unknown",
        }

    def _extract_active_hours(self, intelligence_texts: List[Dict]) -> Dict:
        hours: Counter = Counter()
        for item in intelligence_texts:
            timestamp = item.get("timestamp", "")
            if not timestamp:
                continue
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    hours[dt.hour] += 1
            except (ValueError, TypeError):
                continue

        total = sum(hours.values())
        if total == 0:
            return {str(h): 0 for h in range(24)}

        return {str(h): hours.get(h, 0) / total for h in range(24)}

    async def _extract_operation_types(
        self, entity_id: str, intelligence_texts: List[Dict]
    ) -> List[str]:
        relations = await self.knowledge_graph.get_entity_relations(entity_id)
        operation_types: Set[str] = set()

        for rel in relations:
            rel_type = rel.type.value if hasattr(rel.type, "value") else str(rel.type)
            operation_types.add(rel_type)

        if intelligence_texts and len(operation_types) < 2:
            combined = " ".join(t.get("content", "")[:200] for t in intelligence_texts[:5])
            try:
                system_prompt = (
                    "你是一个黑灰产行为分析专家。从以下文本中提取该实体的行为类型。\n"
                    "输出JSON数组，如：[\"selling\",\"recruiting\",\"advertising\"]\n"
                    "可选值：selling/buying/recruiting/advertising/laundering/"
                    "hacking/phishing/spamming/other\n"
                    "只返回JSON数组，不要其他内容。"
                )
                prompt = f"分析以下文本中实体的行为类型：\n\n{combined[:1500]}"

                result = await self.llm.generate_json(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.2,
                )
                if isinstance(result, list):
                    operation_types.update(result)
                elif isinstance(result, dict):
                    ops = result.get("operations", result.get("types", []))
                    if isinstance(ops, list):
                        operation_types.update(ops)
            except Exception as exc:
                logger.warning(f"LLM operation extraction failed for '{entity_id}': {exc}")

        return list(operation_types)

    def _extract_price_patterns(self, intelligence_texts: List[Dict]) -> Dict:
        import re

        prices: List[float] = []
        for item in intelligence_texts:
            content = item.get("content", "")
            price_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:元|块|万|¥|￥|CNY|RMB)", content)
            for p in price_matches:
                try:
                    prices.append(float(p))
                except ValueError:
                    continue

        if not prices:
            return {"has_pricing": False, "avg_price": 0.0, "price_range": "", "round_preference": 0.0}

        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        round_count = sum(1 for p in prices if p == int(p))
        round_preference = round_count / len(prices)

        return {
            "has_pricing": True,
            "avg_price": round(avg_price, 2),
            "price_range": f"{min_price}-{max_price}",
            "round_preference": round(round_preference, 2),
            "price_count": len(prices),
        }

    def _extract_social_connections(
        self, entity_id: str, relations: list
    ) -> List[str]:
        connections: List[str] = []
        for rel in relations:
            if rel.source_entity_id == entity_id:
                connections.append(rel.target_entity_id)
            else:
                connections.append(rel.source_entity_id)
        return connections[:50]

    def _build_fingerprint_vector(
        self,
        linguistic: Dict,
        active_hours: Dict,
        operations: List[str],
        prices: Dict,
        connections: List[str],
    ) -> List[float]:
        vector: List[float] = []

        avg_sent_len = float(linguistic.get("avg_sentence_length", 0)) / 100.0
        vector.append(min(avg_sent_len, 1.0))

        emoji_freq = float(linguistic.get("emoji_frequency", 0))
        vector.append(min(emoji_freq, 1.0))

        formality = float(linguistic.get("formality_level", 0.5))
        vector.append(formality)

        dialect_count = len(linguistic.get("dialect_markers", []))
        vector.append(min(dialect_count / 5.0, 1.0))

        phrase_count = len(linguistic.get("common_phrases", []))
        vector.append(min(phrase_count / 10.0, 1.0))

        for h in range(24):
            vector.append(float(active_hours.get(str(h), 0)))

        operation_categories = [
            "selling", "buying", "recruiting", "advertising",
            "laundering", "hacking", "phishing", "spamming", "other",
        ]
        for op in operation_categories:
            vector.append(1.0 if op in operations else 0.0)

        vector.append(1.0 if prices.get("has_pricing", False) else 0.0)
        vector.append(min(float(prices.get("avg_price", 0)) / 10000.0, 1.0))
        vector.append(float(prices.get("round_preference", 0)))

        vector.append(min(len(connections) / 20.0, 1.0))

        while len(vector) < self.VECTOR_DIM:
            vector.append(0.0)

        return vector[:self.VECTOR_DIM]

    async def find_same_entity(
        self, entity_id: str, threshold: float = 0.7
    ) -> List[AttributionMatch]:
        source_fp = await self.compute_behavioral_fingerprint(entity_id)

        all_entities = []
        for eid in self.knowledge_graph._entities:
            if eid != entity_id:
                all_entities.append(eid)

        matches: List[AttributionMatch] = []

        for target_id in all_entities:
            try:
                target_fp = await self.compute_behavioral_fingerprint(target_id)

                if source_fp.platform == target_fp.platform:
                    continue

                ling_sim = self._cosine_similarity_dict(
                    source_fp.linguistic_features, target_fp.linguistic_features
                )
                temp_sim = self._cosine_similarity_hours(
                    source_fp.active_hours, target_fp.active_hours
                )
                behav_sim = self._jaccard_similarity(
                    set(source_fp.operation_types), set(target_fp.operation_types)
                )
                net_sim = self._jaccard_similarity(
                    set(source_fp.social_connections), set(target_fp.social_connections)
                )

                overall = (
                    self.WEIGHTS["linguistic"] * ling_sim
                    + self.WEIGHTS["temporal"] * temp_sim
                    + self.WEIGHTS["behavioral"] * behav_sim
                    + self.WEIGHTS["network"] * net_sim
                )

                if overall >= threshold:
                    evidence = self._build_evidence(
                        ling_sim, temp_sim, behav_sim, net_sim, source_fp, target_fp
                    )
                    confidence = "high" if overall >= 0.85 else ("medium" if overall >= 0.75 else "low")

                    matches.append(AttributionMatch(
                        source_entity_id=entity_id,
                        source_platform=source_fp.platform,
                        target_entity_id=target_id,
                        target_platform=target_fp.platform,
                        overall_similarity=round(overall, 4),
                        linguistic_similarity=round(ling_sim, 4),
                        temporal_similarity=round(temp_sim, 4),
                        behavioral_similarity=round(behav_sim, 4),
                        network_similarity=round(net_sim, 4),
                        evidence=evidence,
                        confidence=confidence,
                    ))
            except Exception as exc:
                logger.warning(f"Attribution comparison failed for '{entity_id}' vs '{target_id}': {exc}")
                continue

        matches.sort(key=lambda m: m.overall_similarity, reverse=True)
        return matches

    async def generate_attribution_report(self, entity_id: str) -> AttributionReport:
        source_fp = await self.compute_behavioral_fingerprint(entity_id)
        entity = await self.knowledge_graph.get_entity(entity_id)

        primary_platform = source_fp.platform

        try:
            matches = await self.find_same_entity(entity_id, threshold=0.5)
        except Exception as exc:
            logger.error(f"Attribution search failed for '{entity_id}': {exc}")
            matches = []

        all_platforms = {primary_platform}
        for match in matches:
            all_platforms.add(match.target_platform)

        risk_assessment = self._assess_attribution_risk(matches)
        evidence_summary = self._build_evidence_summary(entity_id, matches)

        return AttributionReport(
            entity_id=entity_id,
            primary_platform=primary_platform,
            aliases=matches,
            total_platforms=len(all_platforms),
            risk_assessment=risk_assessment,
            evidence_summary=evidence_summary,
        )

    def _assess_attribution_risk(self, matches: List[AttributionMatch]) -> str:
        if not matches:
            return "未发现跨平台关联，威胁范围有限"

        high_conf_matches = [m for m in matches if m.confidence == "high"]
        medium_conf_matches = [m for m in matches if m.confidence == "medium"]

        platforms = set()
        for m in matches:
            platforms.add(m.target_platform)

        if high_conf_matches:
            return (
                f"高风险：发现{len(high_conf_matches)}个高置信度跨平台关联，"
                f"涉及{len(platforms)}个平台，该实体可能运营大规模跨平台犯罪网络"
            )
        if medium_conf_matches:
            return (
                f"中风险：发现{len(medium_conf_matches)}个中等置信度跨平台关联，"
                f"涉及{len(platforms)}个平台，建议持续监控"
            )
        return (
            f"低风险：发现{len(matches)}个低置信度跨平台关联，"
            f"需要更多证据确认"
        )

    def _build_evidence_summary(
        self, entity_id: str, matches: List[AttributionMatch]
    ) -> str:
        if not matches:
            return f"实体{entity_id[:8]}未发现跨平台关联证据"

        parts = [f"实体{entity_id[:8]}的跨平台归因分析："]
        for i, match in enumerate(matches[:5]):
            parts.append(
                f"{i+1}. 与{match.target_platform}平台实体{match.target_entity_id[:8]}的"
                f"综合相似度为{match.overall_similarity:.2f}（{match.confidence}置信度）"
            )
            if match.evidence:
                parts.append(f"   关键证据: {'; '.join(match.evidence[:3])}")

        return "\n".join(parts)

    def _build_evidence(
        self,
        ling_sim: float,
        temp_sim: float,
        behav_sim: float,
        net_sim: float,
        source_fp: BehavioralFingerprint,
        target_fp: BehavioralFingerprint,
    ) -> List[str]:
        evidence: List[str] = []

        if ling_sim > 0.6:
            evidence.append(f"写作风格相似度{ling_sim:.2f}")
        if temp_sim > 0.6:
            evidence.append(f"活跃时间模式相似度{temp_sim:.2f}")
        if behav_sim > 0.5:
            common_ops = set(source_fp.operation_types) & set(target_fp.operation_types)
            if common_ops:
                evidence.append(f"共同行为类型: {', '.join(common_ops)}")
        if net_sim > 0.3:
            common_connections = set(source_fp.social_connections) & set(target_fp.social_connections)
            if common_connections:
                evidence.append(f"共同社交连接: {len(common_connections)}个")

        return evidence

    @staticmethod
    def _cosine_similarity_hours(hours_a: Dict, hours_b: Dict) -> float:
        vec_a = [float(hours_a.get(str(h), 0)) for h in range(24)]
        vec_b = [float(hours_b.get(str(h), 0)) for h in range(24)]

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))

        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    @staticmethod
    def _cosine_similarity_dict(dict_a: Dict, dict_b: Dict) -> float:
        all_keys = set(dict_a.keys()) | set(dict_b.keys())
        if not all_keys:
            return 0.0

        vec_a = []
        vec_b = []
        for key in all_keys:
            val_a = dict_a.get(key, 0)
            val_b = dict_b.get(key, 0)
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                vec_a.append(float(val_a))
                vec_b.append(float(val_b))

        if not vec_a:
            return 0.0

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))

        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)
