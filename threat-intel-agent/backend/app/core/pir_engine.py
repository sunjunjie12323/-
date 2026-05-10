from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.evidence_chain import EvidenceChain, Evidence
from app.core.llm import LLMService
from app.core.vector_store import VectorStore
from app.models.intelligence import IntelligenceReport, IntelligenceSource
from app.models.pir import PIR, PIRPriority, PIRStatus, PIRTask, PIRTaskStatus


class PIREngine:
    def __init__(self, llm: LLMService, vector_store: VectorStore):
        self.llm = llm
        self.vector_store = vector_store
        self.evidence_chain = EvidenceChain(llm, vector_store)
        self._pirs: Dict[str, PIR] = {}
        self._tasks: Dict[str, PIRTask] = {}

    async def create_pir(
        self,
        title: str,
        description: str,
        priority: str,
        keywords: List[str],
        target_sources: List[str],
    ) -> PIR:
        try:
            priority_enum = PIRPriority(priority)
        except ValueError:
            priority_enum = PIRPriority.MEDIUM
            logger.warning(f"Invalid priority '{priority}', defaulting to MEDIUM")

        source_enums: List[IntelligenceSource] = []
        for src in target_sources:
            try:
                source_enums.append(IntelligenceSource(src))
            except ValueError:
                logger.warning(f"Invalid source type '{src}', skipping")

        pir = PIR(
            title=title,
            description=description,
            priority=priority_enum,
            keywords=keywords,
            target_sources=source_enums,
        )
        self._pirs[pir.id] = pir
        logger.info(f"Created PIR: {pir.id} - {title} (priority={priority})")
        return pir

    async def decompose_pir(self, pir: PIR) -> List[PIRTask]:
        system_prompt = (
            "你是一个黑灰产情报分析任务分解专家。根据给定的优先情报需求(PIR)，"
            "将其分解为具体的Agent任务。\n\n"
            "可用的Agent类型：\n"
            "- collector: 情报采集Agent，负责从各渠道搜索和收集情报\n"
            "- cleaner: 情报清洗Agent，负责解码黑话、提取实体、标准化数据\n"
            "- analyst: 情报分析Agent，负责识别威胁模式、评估威胁等级、分析攻击链\n"
            "- graph_builder: 图谱构建Agent，负责更新知识图谱、发现关联关系\n\n"
            "返回JSON数组，每个元素包含：\n"
            "- agent_type: agent类型（collector/cleaner/analyst/graph_builder之一）\n"
            "- task_description: 具体任务描述\n\n"
            "只返回JSON数组，不要其他内容。"
        )
        source_list = ", ".join(s.value for s in pir.target_sources) if pir.target_sources else "所有来源"
        keyword_list = ", ".join(pir.keywords) if pir.keywords else "无特定关键词"
        prompt = (
            f"PIR标题：{pir.title}\n"
            f"PIR描述：{pir.description}\n"
            f"优先级：{pir.priority.value}\n"
            f"关键词：{keyword_list}\n"
            f"目标来源：{source_list}\n\n"
            f"请将此PIR分解为具体的Agent任务。"
        )

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error(f"LLM decomposition failed for PIR {pir.id}: {exc}")
            result = self._fallback_decompose(pir)

        if not isinstance(result, list):
            if isinstance(result, dict):
                result = [result]
            else:
                result = self._fallback_decompose(pir)

        tasks: List[PIRTask] = []
        for item in result:
            agent_type = item.get("agent_type", "collector")
            task_desc = item.get("task_description", "")
            if not task_desc:
                continue
            valid_agents = {"collector", "cleaner", "analyst", "graph_builder"}
            if agent_type not in valid_agents:
                agent_type = "collector"
            task = PIRTask(
                pir_id=pir.id,
                agent_type=agent_type,
                task_description=task_desc,
            )
            self._tasks[task.id] = task
            tasks.append(task)

        if not tasks:
            tasks = self._create_default_tasks(pir)

        logger.info(f"Decomposed PIR {pir.id} into {len(tasks)} tasks")
        return tasks

    def _fallback_decompose(self, pir: PIR) -> List[dict]:
        return [
            {
                "agent_type": "collector",
                "task_description": f"搜索与「{pir.title}」相关的情报，关键词：{', '.join(pir.keywords[:5])}",
            },
            {
                "agent_type": "cleaner",
                "task_description": f"清洗采集到的情报，解码黑话，提取实体信息",
            },
            {
                "agent_type": "analyst",
                "task_description": f"分析清洗后的情报，识别威胁模式和攻击链",
            },
            {
                "agent_type": "graph_builder",
                "task_description": f"将分析结果更新到知识图谱，建立实体关联关系",
            },
        ]

    def _create_default_tasks(self, pir: PIR) -> List[PIRTask]:
        fallback = self._fallback_decompose(pir)
        tasks: List[PIRTask] = []
        for item in fallback:
            task = PIRTask(
                pir_id=pir.id,
                agent_type=item["agent_type"],
                task_description=item["task_description"],
            )
            self._tasks[task.id] = task
            tasks.append(task)
        return tasks

    async def evaluate_pir(self, pir_id: str) -> Dict:
        pir = self._pirs.get(pir_id)
        if not pir:
            logger.warning(f"PIR {pir_id} not found")
            return {"error": f"PIR {pir_id} not found"}

        pir_tasks = [
            t for t in self._tasks.values() if t.pir_id == pir_id
        ]
        if not pir_tasks:
            return {
                "pir_id": pir_id,
                "title": pir.title,
                "status": pir.status.value,
                "fulfillment_percentage": 0.0,
                "total_tasks": 0,
                "completed_tasks": 0,
                "running_tasks": 0,
                "pending_tasks": 0,
                "failed_tasks": 0,
                "summary": "尚未分解任务",
            }

        total = len(pir_tasks)
        completed = sum(1 for t in pir_tasks if t.status == PIRTaskStatus.COMPLETED)
        running = sum(1 for t in pir_tasks if t.status == PIRTaskStatus.RUNNING)
        pending = sum(1 for t in pir_tasks if t.status == PIRTaskStatus.PENDING)
        failed = sum(1 for t in pir_tasks if t.status == PIRTaskStatus.FAILED)

        fulfillment_percentage = (completed / total * 100) if total > 0 else 0.0

        is_fulfilled = False
        summary = ""
        if fulfillment_percentage >= 80.0 and failed == 0:
            is_fulfilled = True
            summary = "PIR已基本完成，所有关键任务均已执行"
        elif fulfillment_percentage >= 50.0:
            summary = f"PIR执行中，已完成{completed}/{total}个任务"
        elif failed > completed:
            summary = f"PIR执行困难，{failed}个任务失败，仅{completed}个完成"
        else:
            summary = f"PIR执行初期，{pending}个任务待执行"

        if is_fulfilled and pir.status == PIRStatus.ACTIVE:
            pir.status = PIRStatus.FULFILLED
            pir.fulfilled_at = datetime.utcnow()
            pir.updated_at = datetime.utcnow()
            pir.results_summary = summary

        return {
            "pir_id": pir_id,
            "title": pir.title,
            "status": pir.status.value,
            "fulfillment_percentage": round(fulfillment_percentage, 1),
            "total_tasks": total,
            "completed_tasks": completed,
            "running_tasks": running,
            "pending_tasks": pending,
            "failed_tasks": failed,
            "summary": summary,
        }

    async def generate_pir_report(self, pir_id: str) -> IntelligenceReport:
        pir = self._pirs.get(pir_id)
        if not pir:
            raise ValueError(f"PIR {pir_id} not found")

        pir_tasks = [
            t for t in self._tasks.values() if t.pir_id == pir_id
        ]

        task_results: List[Dict[str, Any]] = []
        for task in pir_tasks:
            if task.result:
                task_results.append(task.result)

        related_intel: List[dict] = []
        for keyword in pir.keywords:
            try:
                results = await self.vector_store.search_intelligence(
                    keyword, n_results=5
                )
                related_intel.extend(results)
            except Exception as exc:
                logger.warning(f"Failed to search intel for keyword '{keyword}': {exc}")

        context_parts: List[str] = []
        for i, result in enumerate(task_results[:10]):
            context_parts.append(f"任务结果{i+1}: {str(result)[:500]}")
        for i, intel in enumerate(related_intel[:5]):
            doc = intel.get("document", "")
            if doc:
                context_parts.append(f"相关情报{i+1}: {doc[:500]}")
        context = "\n\n".join(context_parts) if context_parts else "暂无相关情报数据"

        system_prompt = (
            "你是一个黑灰产情报分析报告撰写专家。根据提供的PIR信息和任务结果，"
            "生成一份结构化的情报分析报告。\n\n"
            "返回JSON格式，包含以下字段：\n"
            "- summary: 报告摘要（200字以内）\n"
            "- key_findings: 关键发现列表（字符串数组）\n"
            "- threat_actors: 威胁行为者列表\n"
            "- iocs: 失陷指标(IoC)列表\n"
            "- recommendations: 建议措施列表\n"
            "- confidence_score: 总体置信度（0-1）\n\n"
            "只返回JSON，不要其他内容。"
        )
        prompt = (
            f"PIR标题：{pir.title}\n"
            f"PIR描述：{pir.description}\n"
            f"优先级：{pir.priority.value}\n"
            f"关键词：{', '.join(pir.keywords)}\n\n"
            f"相关数据：\n{context}"
        )

        try:
            report_data = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error(f"LLM report generation failed for PIR {pir_id}: {exc}")
            report_data = {
                "summary": f"关于「{pir.title}」的情报分析报告（自动生成摘要）",
                "key_findings": [f"PIR: {pir.title}", f"描述: {pir.description}"],
                "threat_actors": [],
                "iocs": [],
                "recommendations": ["建议持续监控相关情报"],
                "confidence_score": 0.3,
            }

        evidence_list: List[Evidence] = []
        for intel in related_intel:
            metadata = intel.get("metadata", {})
            evidence = Evidence(
                id=uuid4().hex,
                source_id=intel.get("id", uuid4().hex),
                source_type="intelligence",
                content=intel.get("document", ""),
                confidence=1.0 - (intel.get("distance", 0.5)),
            )
            evidence_list.append(evidence)

        verification = await self.evidence_chain.verify(
            conclusion=report_data.get("summary", pir.title),
            sources=evidence_list,
        )

        confidence = report_data.get("confidence_score", 0.5)
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence * verification.confidence))

        report = IntelligenceReport(
            pir_id=pir_id,
            title=f"情报报告: {pir.title}",
            summary=report_data.get("summary", ""),
            key_findings=report_data.get("key_findings", []),
            threat_actors=report_data.get("threat_actors", []),
            iocs=report_data.get("iocs", []),
            recommendations=report_data.get("recommendations", []),
            confidence_score=confidence,
            evidence_chain=[e.id for e in evidence_list],
        )

        logger.info(
            f"Generated report for PIR {pir_id}: {report.id} "
            f"(confidence={confidence:.2f})"
        )
        return report

    async def get_pir(self, pir_id: str) -> Optional[PIR]:
        return self._pirs.get(pir_id)

    async def get_all_pirs(
        self, status: Optional[str] = None
    ) -> List[PIR]:
        pirs = list(self._pirs.values())
        if status:
            try:
                status_enum = PIRStatus(status)
                pirs = [p for p in pirs if p.status == status_enum]
            except ValueError:
                logger.warning(f"Invalid status filter: {status}")
        return sorted(pirs, key=lambda p: p.created_at, reverse=True)

    async def get_pir_tasks(self, pir_id: str) -> List[PIRTask]:
        return [t for t in self._tasks.values() if t.pir_id == pir_id]

    async def update_task_status(
        self, task_id: str, status: str, result: Optional[Dict] = None
    ) -> Optional[PIRTask]:
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return None
        try:
            task.status = PIRTaskStatus(status)
        except ValueError:
            logger.warning(f"Invalid task status: {status}")
            return None
        if result:
            task.result = result
        if task.status == PIRTaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
        return task
