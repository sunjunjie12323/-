import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.blacktalk_engine import BlackTalkEngine
from app.core.llm import LLMService
from app.core.vector_store import VectorStore


@dataclass
class ZeroDayTerm:
    term: str
    normal_meaning: str
    criminal_meaning: str
    confidence: float
    context: str
    category: str
    is_truly_new: bool

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "normal_meaning": self.normal_meaning,
            "criminal_meaning": self.criminal_meaning,
            "confidence": self.confidence,
            "context": self.context,
            "category": self.category,
            "is_truly_new": self.is_truly_new,
        }


@dataclass
class SemanticDriftResult:
    term: str
    original_meaning: str
    current_meaning: str
    drift_timeline: List[Dict] = field(default_factory=list)
    drift_velocity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "original_meaning": self.original_meaning,
            "current_meaning": self.current_meaning,
            "drift_timeline": self.drift_timeline,
            "drift_velocity": self.drift_velocity,
        }


@dataclass
class MigrationResult:
    term: str
    origin_platform: str
    migration_path: List[Dict] = field(default_factory=list)
    current_platforms: List[str] = field(default_factory=list)
    spread_speed: float = 0.0

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "origin_platform": self.origin_platform,
            "migration_path": self.migration_path,
            "current_platforms": self.current_platforms,
            "spread_speed": self.spread_speed,
        }


class ZeroDayDetector:
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, llm: LLMService, vector_store: VectorStore, blacktalk_engine: BlackTalkEngine):
        self.llm = llm
        self.vector_store = vector_store
        self.blacktalk_engine = blacktalk_engine

    async def detect_zero_day_terms(self, text: str) -> List[ZeroDayTerm]:
        _, known_terms = await self.blacktalk_engine.decode(text)
        known_term_set = set(known_terms.keys())

        try:
            llm_results = await self._llm_detect_slang(text)
        except Exception as exc:
            logger.error(f"LLM zero-day detection failed: {exc}")
            llm_results = []

        zero_day_terms: List[ZeroDayTerm] = []
        for item in llm_results:
            term = item.get("term", "").strip()
            if not term:
                continue
            if term in known_term_set:
                continue
            if self._is_in_dictionary(term):
                continue

            confidence = float(item.get("confidence", 0.5))
            if confidence < self.CONFIDENCE_THRESHOLD:
                continue

            zdt = ZeroDayTerm(
                term=term,
                normal_meaning=item.get("normal_meaning", ""),
                criminal_meaning=item.get("criminal_meaning", ""),
                confidence=confidence,
                context=item.get("context", ""),
                category=item.get("category", "other"),
                is_truly_new=True,
            )
            zero_day_terms.append(zdt)

        zero_day_terms.sort(key=lambda t: t.confidence, reverse=True)
        logger.info(
            f"Zero-day detection: found {len(zero_day_terms)} new terms "
            f"(filtered from {len(llm_results)} LLM candidates, {len(known_term_set)} known)"
        )
        return zero_day_terms

    async def _llm_detect_slang(self, text: str) -> List[dict]:
        system_prompt = (
            "你是一个黑灰产暗语发现专家。你的任务是发现尚未被收录的黑话/暗语。\n"
            "分析以下黑灰产情报文本，找出其中可能是黑话/暗语但不在常见词典中的词汇。"
            "这些词在正常语境下有其他含义，但在黑灰产语境下有特殊含义。\n"
            "输出JSON格式数组：\n"
            '[{"term":"xxx","normal_meaning":"正常含义","criminal_meaning":"黑灰产含义",'
            '"confidence":0.8,"context":"原文片段","category":"fraud/money_laundering/hacking/gambling/drugs/other"}]\n'
            "confidence范围0-1，表示该词是黑话的确定程度。\n"
            "只返回JSON数组，不要其他内容。如果没有发现可疑词汇，返回空数组[]。"
        )
        prompt = f"分析以下文本中的未知黑话/暗语：\n\n{text}"

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                terms = result.get("terms", result.get("results", []))
                if isinstance(terms, list):
                    return terms
                return [result]
            return []
        except Exception as exc:
            logger.warning(f"LLM slang detection parse failed: {exc}")
            return []

    def _is_in_dictionary(self, term: str) -> bool:
        return term in self.blacktalk_engine._term_index

    async def track_semantic_drift(self, term: str) -> SemanticDriftResult:
        historical_uses = await self._find_historical_uses(term)

        if not historical_uses:
            return SemanticDriftResult(
                term=term,
                original_meaning="",
                current_meaning="",
                drift_timeline=[],
                drift_velocity=0.0,
            )

        try:
            drift_result = await self._llm_analyze_drift(term, historical_uses)
        except Exception as exc:
            logger.error(f"LLM semantic drift analysis failed for '{term}': {exc}")
            drift_result = self._heuristic_drift(term, historical_uses)

        return drift_result

    async def _find_historical_uses(self, term: str) -> List[Dict]:
        results = await self.vector_store.search_intelligence(term, n_results=20)
        uses: List[Dict] = []
        for result in results:
            doc = result.get("document", "")
            metadata = result.get("metadata", {})
            if not doc:
                continue
            timestamp = metadata.get("collected_at", metadata.get("timestamp", ""))
            source = metadata.get("source", "unknown")
            uses.append({
                "content": doc[:500],
                "timestamp": timestamp,
                "source": source,
                "id": result.get("id", ""),
            })
        uses.sort(key=lambda u: u.get("timestamp", "") or "")
        return uses

    async def _llm_analyze_drift(self, term: str, historical_uses: List[Dict]) -> SemanticDriftResult:
        uses_text = "\n".join(
            f"[{u.get('timestamp', '未知时间')}] (来源:{u.get('source', '未知')}): {u.get('content', '')[:200]}"
            for u in historical_uses
        )

        system_prompt = (
            f"你是一个语义演变分析专家。分析黑话术语「{term}」在不同时期的使用记录，"
            "判断其含义是否发生了变化（语义漂移）。\n"
            "输出JSON格式：\n"
            '{"original_meaning":"最初含义","current_meaning":"当前含义",'
            '"drift_timeline":[{"date":"日期","meaning":"该时期的含义","source":"来源"}],'
            '"drift_velocity":0.5}\n'
            "drift_velocity范围0-1，0表示没有变化，1表示含义完全改变。\n"
            "只返回JSON，不要其他内容。"
        )
        prompt = f"术语「{term}」的历史使用记录：\n\n{uses_text}"

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.2,
            )
            return SemanticDriftResult(
                term=term,
                original_meaning=result.get("original_meaning", ""),
                current_meaning=result.get("current_meaning", ""),
                drift_timeline=result.get("drift_timeline", []),
                drift_velocity=float(result.get("drift_velocity", 0.0)),
            )
        except Exception as exc:
            logger.warning(f"LLM drift analysis parse failed for '{term}': {exc}")
            return self._heuristic_drift(term, historical_uses)

    def _heuristic_drift(self, term: str, historical_uses: List[Dict]) -> SemanticDriftResult:
        if not historical_uses:
            return SemanticDriftResult(term=term, original_meaning="", current_meaning="")

        timeline = []
        for u in historical_uses:
            timeline.append({
                "date": u.get("timestamp", "未知"),
                "meaning": f"在上下文中使用: {u.get('content', '')[:50]}",
                "source": u.get("source", "未知"),
            })

        dict_meaning = ""
        if term in self.blacktalk_engine._term_index:
            term_id = self.blacktalk_engine._term_index[term]
            bt = self.blacktalk_engine._dictionary.get(term_id)
            if bt:
                dict_meaning = bt.meaning

        return SemanticDriftResult(
            term=term,
            original_meaning=dict_meaning or "未知",
            current_meaning=dict_meaning or "未知",
            drift_timeline=timeline,
            drift_velocity=0.0,
        )

    async def track_cross_platform_migration(self, term: str) -> MigrationResult:
        platform_uses = await self._find_platform_uses(term)

        if not platform_uses:
            return MigrationResult(
                term=term,
                origin_platform="unknown",
                migration_path=[],
                current_platforms=[],
                spread_speed=0.0,
            )

        try:
            migration_result = await self._llm_analyze_migration(term, platform_uses)
        except Exception as exc:
            logger.error(f"LLM migration analysis failed for '{term}': {exc}")
            migration_result = self._heuristic_migration(term, platform_uses)

        return migration_result

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

    async def _llm_analyze_migration(self, term: str, platform_uses: Dict[str, List[Dict]]) -> MigrationResult:
        platforms_summary = []
        for platform, uses in platform_uses.items():
            first_seen = uses[0].get("timestamp", "未知") if uses else "未知"
            platforms_summary.append(
                f"平台:{platform}, 首次出现:{first_seen}, 出现次数:{len(uses)}"
            )
        platforms_text = "\n".join(platforms_summary)

        system_prompt = (
            f"你是一个黑话传播路径分析专家。分析术语「{term}」在不同平台的传播情况。\n"
            "输出JSON格式：\n"
            '{"origin_platform":"最初出现的平台","migration_path":'
            '[{"platform":"平台名","first_seen":"首次出现时间","count":5}],'
            '"current_platforms":["当前活跃的平台列表"],'
            '"spread_speed":0.5}\n'
            "spread_speed范围0-1，0表示传播很慢，1表示快速跨平台传播。\n"
            "只返回JSON，不要其他内容。"
        )
        prompt = f"术语「{term}」的跨平台使用数据：\n\n{platforms_text}"

        result = await self.llm.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )

        return MigrationResult(
            term=term,
            origin_platform=result.get("origin_platform", "unknown"),
            migration_path=result.get("migration_path", []),
            current_platforms=result.get("current_platforms", []),
            spread_speed=float(result.get("spread_speed", 0.0)),
        )

    def _heuristic_migration(self, term: str, platform_uses: Dict[str, List[Dict]]) -> MigrationResult:
        if not platform_uses:
            return MigrationResult(term=term, origin_platform="unknown")

        earliest_platform = None
        earliest_time = None
        migration_path = []
        current_platforms = []

        for platform, uses in platform_uses.items():
            if uses:
                first_seen = uses[0].get("timestamp", "")
                migration_path.append({
                    "platform": platform,
                    "first_seen": first_seen,
                    "count": len(uses),
                })
                current_platforms.append(platform)
                if earliest_time is None or (first_seen and first_seen < earliest_time):
                    earliest_time = first_seen
                    earliest_platform = platform

        migration_path.sort(key=lambda p: p.get("first_seen", "") or "")

        total_uses = sum(len(uses) for uses in platform_uses.values())
        num_platforms = len(platform_uses)
        spread_speed = min(num_platforms / 5.0, 1.0) if total_uses > 0 else 0.0

        return MigrationResult(
            term=term,
            origin_platform=earliest_platform or "unknown",
            migration_path=migration_path,
            current_platforms=current_platforms,
            spread_speed=spread_speed,
        )
