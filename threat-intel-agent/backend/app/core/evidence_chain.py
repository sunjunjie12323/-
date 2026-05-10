import re
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.llm import LLMService
from app.core.vector_store import VectorStore


class Evidence:
    def __init__(
        self,
        id: str,
        source_id: str,
        source_type: str,
        content: str,
        confidence: float,
        timestamp: Optional[datetime] = None,
    ):
        self.id = id
        self.source_id = source_id
        self.source_type = source_type
        self.content = content
        self.confidence = confidence
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "content": self.content,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


class VerificationResult:
    def __init__(
        self,
        conclusion: str,
        confidence: float,
        evidence_count: int,
        source_count: int,
        cross_validated: bool,
        evidence_list: List[Evidence],
        verification_details: str,
    ):
        self.conclusion = conclusion
        self.confidence = confidence
        self.evidence_count = evidence_count
        self.source_count = source_count
        self.cross_validated = cross_validated
        self.evidence_list = evidence_list
        self.verification_details = verification_details

    def to_dict(self) -> dict:
        return {
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "source_count": self.source_count,
            "cross_validated": self.cross_validated,
            "evidence_list": [e.to_dict() for e in self.evidence_list],
            "verification_details": self.verification_details,
        }


class EvidenceChain:
    MIN_SOURCES_FOR_CROSS_VALIDATION = 2
    SOURCE_TYPE_WEIGHTS = {
        "intelligence": 1.0,
        "entity": 0.8,
        "external": 0.9,
    }
    CONSISTENCY_WEIGHT = 0.4
    SOURCE_COUNT_WEIGHT = 0.3
    DIVERSITY_WEIGHT = 0.2
    CROSS_VALIDATION_WEIGHT = 0.1

    def __init__(self, llm: LLMService, vector_store: VectorStore):
        self.llm = llm
        self.vector_store = vector_store

    async def verify(
        self, conclusion: str, sources: List[Evidence]
    ) -> VerificationResult:
        if not sources:
            return VerificationResult(
                conclusion=conclusion,
                confidence=0.0,
                evidence_count=0,
                source_count=0,
                cross_validated=False,
                evidence_list=[],
                verification_details="无证据来源，无法验证",
            )

        unique_sources = {e.source_id for e in sources}
        source_types = {e.source_type for e in sources}

        consistency_score = await self._assess_consistency(conclusion, sources)

        source_count_score = min(len(unique_sources) / 5.0, 1.0)

        diversity_score = min(len(source_types) / 3.0, 1.0)

        cross_validated = len(unique_sources) >= self.MIN_SOURCES_FOR_CROSS_VALIDATION
        cross_validation_score = 1.0 if cross_validated else 0.0

        avg_evidence_confidence = sum(e.confidence for e in sources) / len(sources)

        final_confidence = (
            consistency_score * self.CONSISTENCY_WEIGHT
            + source_count_score * self.SOURCE_COUNT_WEIGHT
            + diversity_score * self.DIVERSITY_WEIGHT
            + cross_validation_score * self.CROSS_VALIDATION_WEIGHT
        ) * avg_evidence_confidence

        final_confidence = max(0.0, min(1.0, final_confidence))

        details = self._build_verification_details(
            conclusion=conclusion,
            sources=sources,
            consistency_score=consistency_score,
            source_count_score=source_count_score,
            diversity_score=diversity_score,
            cross_validated=cross_validated,
            avg_evidence_confidence=avg_evidence_confidence,
            final_confidence=final_confidence,
        )

        return VerificationResult(
            conclusion=conclusion,
            confidence=final_confidence,
            evidence_count=len(sources),
            source_count=len(unique_sources),
            cross_validated=cross_validated,
            evidence_list=sources,
            verification_details=details,
        )

    async def _assess_consistency(
        self, conclusion: str, sources: List[Evidence]
    ) -> float:
        if len(sources) == 0:
            return 0.0
        if len(sources) == 1:
            return sources[0].confidence * 0.8

        evidence_text = "\n".join(
            f"[来源{i+1}] (类型: {e.source_type}, 置信度: {e.confidence:.2f}): {e.content[:300]}"
            for i, e in enumerate(sources)
        )

        system_prompt = (
            "你是一个情报分析验证专家。你需要评估以下结论是否被提供的证据所支持。\n"
            "请给出0到1之间的一致性分数：\n"
            "- 1.0: 所有证据完全支持结论\n"
            "- 0.7-0.9: 大部分证据支持结论\n"
            "- 0.4-0.6: 部分证据支持，部分矛盾\n"
            "- 0.1-0.3: 大部分证据与结论矛盾\n"
            "- 0.0: 证据完全不支持结论\n\n"
            "只返回一个0到1之间的数字，不要其他内容。"
        )
        prompt = f"结论：{conclusion}\n\n证据：\n{evidence_text}"

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=10,
            )
            score = float(response.strip())
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError) as exc:
            logger.warning(f"Failed to parse consistency score from LLM: {exc}")
            return 0.5
        except Exception as exc:
            logger.error(f"Consistency assessment failed: {exc}")
            return 0.5

    def _build_verification_details(
        self,
        conclusion: str,
        sources: List[Evidence],
        consistency_score: float,
        source_count_score: float,
        diversity_score: float,
        cross_validated: bool,
        avg_evidence_confidence: float,
        final_confidence: float,
    ) -> str:
        unique_sources = {e.source_id for e in sources}
        source_types = {e.source_type for e in sources}
        lines = [
            f"结论验证报告：{conclusion[:100]}",
            f"最终置信度：{final_confidence:.2f}",
            f"证据数量：{len(sources)}",
            f"独立来源数：{len(unique_sources)}",
            f"来源类型：{', '.join(source_types)}",
            f"是否交叉验证：{'是' if cross_validated else '否'}",
            f"一致性分数：{consistency_score:.2f}",
            f"来源数量分数：{source_count_score:.2f}",
            f"多样性分数：{diversity_score:.2f}",
            f"证据平均置信度：{avg_evidence_confidence:.2f}",
        ]
        if final_confidence >= 0.8:
            lines.append("验证结论：高度可信，结论被充分证据支持")
        elif final_confidence >= 0.6:
            lines.append("验证结论：较为可信，但建议补充更多来源验证")
        elif final_confidence >= 0.4:
            lines.append("验证结论：可信度一般，需要更多证据支持")
        else:
            lines.append("验证结论：可信度较低，结论可能不被证据支持")
        return "\n".join(lines)

    async def create_evidence_chain(
        self, conclusion: str, analysis_result: dict
    ) -> List[Evidence]:
        evidence_list: List[Evidence] = []

        raw_ids = analysis_result.get("raw_intelligence_ids", [])
        for raw_id in raw_ids:
            evidence = Evidence(
                id=uuid4().hex,
                source_id=raw_id,
                source_type="intelligence",
                content=analysis_result.get("analysis_summary", ""),
                confidence=analysis_result.get("confidence_score", 0.5),
            )
            evidence_list.append(evidence)

        entity_ids = analysis_result.get("entity_ids", [])
        for entity_id in entity_ids:
            evidence = Evidence(
                id=uuid4().hex,
                source_id=entity_id,
                source_type="entity",
                content=f"关联实体: {entity_id}",
                confidence=0.6,
            )
            evidence_list.append(evidence)

        external_refs = analysis_result.get("external_references", [])
        for ref in external_refs:
            if isinstance(ref, dict):
                evidence = Evidence(
                    id=uuid4().hex,
                    source_id=ref.get("id", uuid4().hex),
                    source_type="external",
                    content=ref.get("content", ""),
                    confidence=ref.get("confidence", 0.5),
                )
            else:
                evidence = Evidence(
                    id=uuid4().hex,
                    source_id=str(ref),
                    source_type="external",
                    content=str(ref),
                    confidence=0.5,
                )
            evidence_list.append(evidence)

        logger.info(
            f"Created evidence chain for conclusion '{conclusion[:50]}...': "
            f"{len(evidence_list)} evidence items"
        )
        return evidence_list

    async def detect_hallucination(self, claim: str, context: str) -> float:
        if not context.strip():
            return 0.8

        hallucination_score = 0.0

        try:
            system_prompt = (
                "你是一个AI幻觉检测专家。判断以下声明是否被上下文所支持。\n"
                "返回一个0到1之间的幻觉概率：\n"
                "- 0.0: 声明完全被上下文支持，没有幻觉\n"
                "- 0.3: 声明大部分被支持，有少量推断\n"
                "- 0.5: 声明部分被支持，有较多推断\n"
                "- 0.7: 声明大部分不被支持，可能是幻觉\n"
                "- 1.0: 声明完全不被支持，确定是幻觉\n\n"
                "只返回一个0到1之间的数字，不要其他内容。"
            )
            prompt = f"声明：{claim}\n\n上下文：{context[:2000]}"
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=10,
            )
            llm_score = float(response.strip())
            hallucination_score = llm_score * 0.7
        except (ValueError, TypeError) as exc:
            logger.warning(f"Failed to parse hallucination score: {exc}")
            hallucination_score = 0.3
        except Exception as exc:
            logger.error(f"Hallucination LLM check failed: {exc}")
            hallucination_score = 0.3

        claim_chars = set(claim)
        context_chars = set(context)
        overlap = claim_chars & context_chars
        if claim_chars:
            char_overlap_ratio = len(overlap) / len(claim_chars)
        else:
            char_overlap_ratio = 0.0

        claim_words = set(re.findall(r"[\u4e00-\u9fff]+|\w+", claim))
        context_words = set(re.findall(r"[\u4e00-\u9fff]+|\w+", context))
        word_overlap = claim_words & context_words
        if claim_words:
            word_overlap_ratio = len(word_overlap) / len(claim_words)
        else:
            word_overlap_ratio = 0.0

        entity_overlap_score = 1.0 - word_overlap_ratio
        hallucination_score += entity_overlap_score * 0.3

        hallucination_score = max(0.0, min(1.0, hallucination_score))

        logger.debug(
            f"Hallucination detection: claim='{claim[:50]}...', "
            f"score={hallucination_score:.2f}"
        )
        return hallucination_score
