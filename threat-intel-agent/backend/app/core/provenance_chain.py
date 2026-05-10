import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.llm import LLMService
from app.core.vector_store import VectorStore


@dataclass
class ProvenanceRecord:
    id: str
    intelligence_id: str
    stage: str
    timestamp: str
    input_hash: str
    output_hash: str
    previous_record_id: Optional[str] = None
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    operator: str = "automated"
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "intelligence_id": self.intelligence_id,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "previous_record_id": self.previous_record_id,
            "llm_prompt": self.llm_prompt,
            "llm_response": self.llm_response,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "operator": self.operator,
            "metadata": self.metadata,
        }


@dataclass
class VerificationResult:
    intelligence_id: str
    is_valid: bool
    chain_length: int
    llm_contributions: int
    human_contributions: int
    automated_contributions: int
    tampered_steps: List[str] = field(default_factory=list)
    completeness: float = 0.0

    def to_dict(self) -> dict:
        return {
            "intelligence_id": self.intelligence_id,
            "is_valid": self.is_valid,
            "chain_length": self.chain_length,
            "llm_contributions": self.llm_contributions,
            "human_contributions": self.human_contributions,
            "automated_contributions": self.automated_contributions,
            "tampered_steps": self.tampered_steps,
            "completeness": self.completeness,
        }


@dataclass
class ConfidencePoint:
    stage: str
    confidence: float
    delta: float
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "confidence": self.confidence,
            "delta": self.delta,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class HallucinationReport:
    intelligence_id: str
    hallucination_score: float = 0.0
    flagged_claims: List[Dict] = field(default_factory=list)
    unsupported_assertions: List[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "intelligence_id": self.intelligence_id,
            "hallucination_score": self.hallucination_score,
            "flagged_claims": self.flagged_claims,
            "unsupported_assertions": self.unsupported_assertions,
            "recommendation": self.recommendation,
        }


class ProvenanceChain:
    EXPECTED_STAGES = ["collected", "cleaned", "analyzed", "report_generated"]

    def __init__(self, llm: LLMService, vector_store: VectorStore):
        self.llm = llm
        self.vector_store = vector_store
        self._chains: Dict[str, List[ProvenanceRecord]] = {}
        self._records_by_id: Dict[str, ProvenanceRecord] = {}

    @staticmethod
    def _compute_hash(data: dict) -> str:
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def record_provenance(
        self,
        intelligence_id: str,
        stage: str,
        input_data: dict,
        output_data: dict,
        llm_prompt: str = None,
        llm_response: str = None,
        confidence_before: float = None,
        confidence_after: float = None,
    ) -> ProvenanceRecord:
        input_hash = self._compute_hash(input_data)
        output_hash = self._compute_hash(output_data)

        previous_record_id = None
        if intelligence_id in self._chains and self._chains[intelligence_id]:
            previous_record_id = self._chains[intelligence_id][-1].id

        operator = "automated"
        if llm_prompt is not None or llm_response is not None:
            operator = "llm"
        elif stage == "collected":
            operator = "human"

        record = ProvenanceRecord(
            id=uuid4().hex,
            intelligence_id=intelligence_id,
            stage=stage,
            timestamp=datetime.utcnow().isoformat(),
            input_hash=input_hash,
            output_hash=output_hash,
            previous_record_id=previous_record_id,
            llm_prompt=llm_prompt,
            llm_response=llm_response,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            operator=operator,
            metadata={
                "input_data": input_data,
                "output_data": output_data,
            },
        )

        if intelligence_id not in self._chains:
            self._chains[intelligence_id] = []
        self._chains[intelligence_id].append(record)
        self._records_by_id[record.id] = record

        logger.info(
            f"Recorded provenance: {intelligence_id} stage={stage} "
            f"operator={operator} record_id={record.id[:8]}"
        )
        return record

    async def verify_provenance(self, intelligence_id: str) -> VerificationResult:
        chain = self._chains.get(intelligence_id, [])

        if not chain:
            return VerificationResult(
                intelligence_id=intelligence_id,
                is_valid=False,
                chain_length=0,
                llm_contributions=0,
                human_contributions=0,
                automated_contributions=0,
                tampered_steps=[],
                completeness=0.0,
            )

        tampered_steps: List[str] = []
        llm_count = 0
        human_count = 0
        automated_count = 0

        for i, record in enumerate(chain):
            if record.operator == "llm":
                llm_count += 1
            elif record.operator == "human":
                human_count += 1
            else:
                automated_count += 1

            stored_input_hash = record.input_hash
            stored_output_hash = record.output_hash
            recomputed_input_hash = self._compute_hash(record.metadata.get("input_data", {}))
            recomputed_output_hash = self._compute_hash(record.metadata.get("output_data", {}))

            if stored_input_hash != recomputed_input_hash:
                tampered_steps.append(
                    f"stage={record.stage} record={record.id[:8]}: input_hash mismatch"
                )
            if stored_output_hash != recomputed_output_hash:
                tampered_steps.append(
                    f"stage={record.stage} record={record.id[:8]}: output_hash mismatch"
                )

            if i > 0 and record.previous_record_id != chain[i - 1].id:
                tampered_steps.append(
                    f"stage={record.stage} record={record.id[:8]}: chain link broken"
                )

        stages_present = {r.stage for r in chain}
        expected_present = stages_present & set(self.EXPECTED_STAGES)
        completeness = len(expected_present) / len(self.EXPECTED_STAGES) if self.EXPECTED_STAGES else 0.0

        is_valid = len(tampered_steps) == 0

        return VerificationResult(
            intelligence_id=intelligence_id,
            is_valid=is_valid,
            chain_length=len(chain),
            llm_contributions=llm_count,
            human_contributions=human_count,
            automated_contributions=automated_count,
            tampered_steps=tampered_steps,
            completeness=completeness,
        )

    async def get_confidence_evolution(
        self, intelligence_id: str
    ) -> List[ConfidencePoint]:
        chain = self._chains.get(intelligence_id, [])

        if not chain:
            return []

        evolution: List[ConfidencePoint] = []
        prev_confidence = None

        for record in chain:
            confidence = record.confidence_after
            if confidence is None:
                confidence = record.confidence_before

            delta = 0.0
            if prev_confidence is not None and confidence is not None:
                delta = confidence - prev_confidence

            reason = self._infer_confidence_reason(record, delta)

            evolution.append(ConfidencePoint(
                stage=record.stage,
                confidence=confidence if confidence is not None else 0.0,
                delta=delta,
                reason=reason,
                timestamp=record.timestamp,
            ))

            if confidence is not None:
                prev_confidence = confidence

        return evolution

    def _infer_confidence_reason(self, record: ProvenanceRecord, delta: float) -> str:
        if record.stage == "collected":
            return "初始采集，设定基线置信度"
        if record.stage == "cleaned":
            if delta > 0:
                return "数据清洗后质量提升"
            elif delta < 0:
                return "数据清洗发现噪声，降低置信度"
            return "数据清洗完成，置信度不变"
        if record.stage == "analyzed":
            if delta > 0:
                return "分析发现更多支持证据"
            elif delta < 0:
                return "分析发现矛盾信息"
            return "分析完成，置信度不变"
        if record.stage == "report_generated":
            if delta > 0:
                return "报告生成时交叉验证通过"
            elif delta < 0:
                return "报告生成时发现不确定性"
            return "报告生成完成"
        if delta > 0:
            return f"{record.stage}阶段置信度提升"
        elif delta < 0:
            return f"{record.stage}阶段置信度下降"
        return f"{record.stage}阶段置信度不变"

    async def detect_hallucination(self, intelligence_id: str) -> HallucinationReport:
        chain = self._chains.get(intelligence_id, [])

        if not chain:
            return HallucinationReport(
                intelligence_id=intelligence_id,
                hallucination_score=0.0,
                recommendation="无溯源记录，无法检测幻觉",
            )

        flagged_claims: List[Dict] = []
        unsupported_assertions: List[str] = []
        total_llm_steps = 0
        hallucinated_steps = 0

        for record in chain:
            if record.operator != "llm":
                continue

            total_llm_steps += 1

            if not record.llm_response:
                continue

            input_data = record.metadata.get("input_data", {})
            input_text = json.dumps(input_data, ensure_ascii=False, default=str)[:2000]
            output_data = record.metadata.get("output_data", {})
            output_text = json.dumps(output_data, ensure_ascii=False, default=str)[:2000]

            try:
                claim_check = await self._llm_verify_claim(
                    record.llm_response, input_text
                )
            except Exception as exc:
                logger.warning(
                    f"LLM hallucination check failed for record {record.id[:8]}: {exc}"
                )
                claim_check = self._heuristic_verify_claim(
                    record.llm_response, input_text
                )

            if claim_check.get("is_hallucinated", False):
                hallucinated_steps += 1
                flagged_claims.append({
                    "claim": record.llm_response[:300],
                    "evidence_for": claim_check.get("evidence_for", ""),
                    "evidence_against": claim_check.get("evidence_against", ""),
                    "verdict": "likely_hallucinated",
                    "stage": record.stage,
                    "record_id": record.id[:8],
                })
                unsupported_assertions.append(record.llm_response[:200])

        hallucination_score = 0.0
        if total_llm_steps > 0:
            hallucination_score = hallucinated_steps / total_llm_steps

        recommendation = self._generate_hallucination_recommendation(
            hallucination_score, len(flagged_claims)
        )

        return HallucinationReport(
            intelligence_id=intelligence_id,
            hallucination_score=hallucination_score,
            flagged_claims=flagged_claims,
            unsupported_assertions=unsupported_assertions,
            recommendation=recommendation,
        )

    async def _llm_verify_claim(self, claim: str, source_data: str) -> dict:
        system_prompt = (
            "你是一个AI幻觉检测专家。判断以下LLM生成的内容是否被源数据所支持。\n"
            "输出JSON格式：\n"
            '{"is_hallucinated":false,"evidence_for":"支持的证据",'
            '"evidence_against":"反对的证据"}\n'
            "is_hallucinated为true表示该内容可能是幻觉（不被源数据支持）。\n"
            "只返回JSON，不要其他内容。"
        )
        prompt = (
            f"源数据：\n{source_data[:1500]}\n\n"
            f"LLM生成内容：\n{claim[:500]}\n\n"
            "判断LLM生成内容是否被源数据支持。"
        )

        result = await self.llm.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
        )

        return {
            "is_hallucinated": bool(result.get("is_hallucinated", False)),
            "evidence_for": result.get("evidence_for", ""),
            "evidence_against": result.get("evidence_against", ""),
        }

    def _heuristic_verify_claim(self, claim: str, source_data: str) -> dict:
        claim_words = set(claim.split())
        source_words = set(source_data.split())
        overlap = claim_words & source_words

        if not claim_words:
            return {"is_hallucinated": False, "evidence_for": "", "evidence_against": ""}

        overlap_ratio = len(overlap) / len(claim_words)
        is_hallucinated = overlap_ratio < 0.15

        return {
            "is_hallucinated": is_hallucinated,
            "evidence_for": f"词汇重叠率: {overlap_ratio:.2f}" if overlap_ratio >= 0.15 else "",
            "evidence_against": f"词汇重叠率过低: {overlap_ratio:.2f}" if is_hallucinated else "",
        }

    def _generate_hallucination_recommendation(
        self, score: float, flagged_count: int
    ) -> str:
        if score == 0.0:
            return "未检测到幻觉，所有LLM生成内容均有源数据支持"
        if score < 0.3:
            return f"低风险：少量内容可能存在幻觉（{flagged_count}处），建议人工复核"
        if score < 0.6:
            return f"中等风险：部分内容可能存在幻觉（{flagged_count}处），建议重新分析并补充证据"
        return f"高风险：大量内容可能存在幻觉（{flagged_count}处），强烈建议重新进行完整分析"

    def get_chain(self, intelligence_id: str) -> List[ProvenanceRecord]:
        return self._chains.get(intelligence_id, [])

    def get_record(self, record_id: str) -> Optional[ProvenanceRecord]:
        return self._records_by_id.get(record_id)
