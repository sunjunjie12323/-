import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.agents.analyst import AnalystAgent
from app.agents.cleaner import CleanerAgent
from app.agents.collector import CollectorAgent
from app.agents.graph_builder import GraphBuilderAgent
from app.core.blacktalk_engine import BlackTalkEngine
from app.core.evidence_chain import EvidenceChain, Evidence
from app.core.knowledge_graph import KnowledgeGraph
from app.core.llm import LLMService
from app.core.pir_engine import PIREngine
from app.core.vector_store import VectorStore
from app.models.intelligence import IntelligenceReport, ThreatLevel
from app.models.pir import PIRTaskStatus


class OrchestratorAgent:
    def __init__(
        self,
        llm: LLMService,
        vector_store: VectorStore,
        blacktalk_engine: BlackTalkEngine,
        knowledge_graph: KnowledgeGraph,
        evidence_chain: EvidenceChain,
        pir_engine: PIREngine,
    ):
        self.llm = llm
        self.vector_store = vector_store
        self.blacktalk_engine = blacktalk_engine
        self.knowledge_graph = knowledge_graph
        self.evidence_chain = evidence_chain
        self.pir_engine = pir_engine

        self.collector = CollectorAgent(llm, vector_store, knowledge_graph)
        self.cleaner = CleanerAgent(llm, vector_store, blacktalk_engine)
        self.analyst = AnalystAgent(
            llm, vector_store, blacktalk_engine, knowledge_graph, evidence_chain
        )
        self.graph_builder = GraphBuilderAgent(
            llm, vector_store, knowledge_graph, evidence_chain
        )

        self.logger = logger.bind(agent="orchestrator")
        self.execution_history: List[Dict] = []

    async def execute_query(
        self, query: str, context: Dict = None
    ) -> Dict:
        execution_id = uuid4().hex
        start_time = datetime.utcnow()

        self.logger.info(f"Executing query [{execution_id}]: {query[:100]}")

        try:
            plan = await self._plan_execution(query)

            self.logger.info(
                f"Execution plan [{execution_id}]: {len(plan)} steps"
            )

            results: List[Dict] = []
            collected_items: List[Dict] = []
            cleaned_items: List[Dict] = []
            analyzed_items: List[Dict] = []

            for step_idx, step in enumerate(plan):
                agent_name = step.get("agent", "")
                task = step.get("task", {})

                self.logger.info(
                    f"Step {step_idx + 1}/{len(plan)}: {agent_name} - "
                    f"{task.get('type', 'unknown')}"
                )

                step_result = await self._execute_agent_step(
                    agent_name, task, context
                )

                results.append({
                    "step": step_idx + 1,
                    "agent": agent_name,
                    "task_type": task.get("type", "unknown"),
                    "result": step_result,
                })

                if agent_name == "collector" and step_result.get("status") == "success":
                    items = step_result.get("data", {}).get("items", [])
                    collected_items.extend(items)

                if agent_name == "cleaner" and step_result.get("status") == "success":
                    data = step_result.get("data", {})
                    if "cleaned_intelligence" in data:
                        cleaned_items.append(data["cleaned_intelligence"])
                    if "cleaned_intelligences" in data:
                        cleaned_items.extend(data["cleaned_intelligences"])

                if agent_name == "analyst" and step_result.get("status") == "success":
                    data = step_result.get("data", {})
                    if "analyzed_intelligence" in data:
                        analyzed_items.append(data["analyzed_intelligence"])

            aggregated = await self._aggregate_results(results, query)

            report = await self._generate_report(query, aggregated)

            try:
                evidence_list = await self.evidence_chain.create_evidence_chain(
                    conclusion=report.get("summary", query),
                    analysis_result={
                        "raw_intelligence_ids": [
                            item.get("id", "") for item in collected_items
                        ],
                        "analysis_summary": report.get("summary", ""),
                        "confidence_score": report.get("confidence_score", 0.5),
                        "entity_ids": [
                            e.get("value", "")
                            for item in cleaned_items
                            for e in item.get("entity_details", [])
                        ],
                    },
                )

                verification = await self.evidence_chain.verify(
                    conclusion=report.get("summary", query),
                    sources=evidence_list,
                )

                report["evidence_verification"] = verification.to_dict()
                original_confidence = report.get("confidence_score", 0.5)
                report["confidence_score"] = max(
                    0.0, min(1.0, original_confidence * verification.confidence)
                )
            except Exception as exc:
                self.logger.warning(f"Evidence verification failed: {exc}")

            end_time = datetime.utcnow()
            execution_record = {
                "execution_id": execution_id,
                "query": query,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "steps": len(plan),
                "results_summary": {
                    "collected": len(collected_items),
                    "cleaned": len(cleaned_items),
                    "analyzed": len(analyzed_items),
                },
                "status": "success",
            }
            self.execution_history.append(execution_record)

            return {
                "execution_id": execution_id,
                "query": query,
                "plan": plan,
                "step_results": results,
                "report": report,
                "collected_count": len(collected_items),
                "cleaned_count": len(cleaned_items),
                "analyzed_count": len(analyzed_items),
                "status": "success",
            }

        except Exception as exc:
            self.logger.error(f"Query execution failed [{execution_id}]: {exc}")
            end_time = datetime.utcnow()
            execution_record = {
                "execution_id": execution_id,
                "query": query,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "status": "failed",
                "error": str(exc),
            }
            self.execution_history.append(execution_record)

            return {
                "execution_id": execution_id,
                "query": query,
                "status": "failed",
                "error": str(exc),
            }

    async def execute_pir(self, pir_id: str) -> Dict:
        pir = await self.pir_engine.get_pir(pir_id)
        if not pir:
            return {"error": f"PIR {pir_id} not found"}

        self.logger.info(f"Executing PIR: {pir_id} - {pir.title}")

        tasks = await self.pir_engine.decompose_pir(pir)

        task_results: List[Dict] = []
        for task in tasks:
            try:
                await self.pir_engine.update_task_status(
                    task.id, PIRTaskStatus.RUNNING.value
                )

                agent_task = self._pir_task_to_agent_task(task, pir)
                step_result = await self._execute_agent_step(
                    task.agent_type, agent_task
                )

                await self.pir_engine.update_task_status(
                    task.id,
                    PIRTaskStatus.COMPLETED.value,
                    result=step_result,
                )

                task_results.append({
                    "task_id": task.id,
                    "agent_type": task.agent_type,
                    "status": "completed",
                    "result": step_result,
                })

            except Exception as exc:
                self.logger.error(
                    f"PIR task {task.id} failed: {exc}"
                )
                await self.pir_engine.update_task_status(
                    task.id, PIRTaskStatus.FAILED.value
                )
                task_results.append({
                    "task_id": task.id,
                    "agent_type": task.agent_type,
                    "status": "failed",
                    "error": str(exc),
                })

        evaluation = await self.pir_engine.evaluate_pir(pir_id)

        try:
            report = await self.pir_engine.generate_pir_report(pir_id)
            report_data = report.model_dump()
        except Exception as exc:
            self.logger.error(f"PIR report generation failed: {exc}")
            report_data = {
                "title": f"情报报告: {pir.title}",
                "summary": "报告生成失败",
                "error": str(exc),
            }

        return {
            "pir_id": pir_id,
            "title": pir.title,
            "task_results": task_results,
            "evaluation": evaluation,
            "report": report_data,
        }

    async def _plan_execution(self, query: str) -> List[Dict]:
        system_prompt = (
            "你是一个黑灰产情报分析任务规划专家。根据用户的查询，"
            "规划需要执行的Agent任务序列。\n\n"
            "可用的Agent：\n"
            "- collector: 情报采集，从各渠道搜索和收集情报\n"
            "- cleaner: 情报清洗，解码黑话、提取实体、标准化数据\n"
            "- analyst: 情报分析，识别威胁模式、评估威胁等级、分析攻击链\n"
            "- graph_builder: 图谱构建，更新知识图谱、发现关联关系\n\n"
            "任务类型：\n"
            "- collector: collect（采集）, search（搜索已有数据）\n"
            "- cleaner: clean（清洗单条）, batch_clean（批量清洗）\n"
            "- analyst: analyze（深度分析）, find_patterns（模式发现）, "
            "reconstruct_chain（链路重建）, predict_trend（趋势预测）\n"
            "- graph_builder: build（构建图谱）, query（查询图谱）, "
            "trace（追踪链路）, find_gangs（发现团伙）\n\n"
            "返回JSON数组，按执行顺序排列，每个元素包含：\n"
            "- agent: agent名称（collector/cleaner/analyst/graph_builder）\n"
            "- task: 任务对象，包含type和其他参数\n\n"
            "只返回JSON数组，不要其他内容。"
        )
        prompt = (
            f"用户查询：{query}\n\n"
            f"请规划执行任务序列。"
        )

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            if isinstance(result, list) and result:
                validated_plan = []
                for step in result:
                    if not isinstance(step, dict):
                        continue
                    agent = step.get("agent", "")
                    task = step.get("task", {})
                    if agent in ("collector", "cleaner", "analyst", "graph_builder"):
                        validated_plan.append(step)
                if validated_plan:
                    return validated_plan
        except Exception as exc:
            self.logger.warning(f"LLM planning failed, using default plan: {exc}")

        return self._default_plan(query)

    async def _aggregate_results(
        self, results: List[Dict], query: str
    ) -> Dict:
        successful = [r for r in results if r.get("result", {}).get("status") == "success"]
        failed = [r for r in results if r.get("result", {}).get("status") == "failed"]

        collected_data: List[Dict] = []
        cleaned_data: List[Dict] = []
        analyzed_data: List[Dict] = []
        graph_data: List[Dict] = []

        for r in successful:
            agent = r.get("agent", "")
            data = r.get("result", {}).get("data", {})

            if agent == "collector":
                items = data.get("items", [])
                collected_data.extend(items)
            elif agent == "cleaner":
                if "cleaned_intelligence" in data:
                    cleaned_data.append(data["cleaned_intelligence"])
                if "cleaned_intelligences" in data:
                    cleaned_data.extend(data["cleaned_intelligences"])
            elif agent == "analyst":
                if "analyzed_intelligence" in data:
                    analyzed_data.append(data["analyzed_intelligence"])
                if "patterns" in data:
                    analyzed_data.append({"patterns": data["patterns"]})
                if "technique_chain" in data:
                    analyzed_data.append({"technique_chain": data["technique_chain"]})
                if "trend_prediction" in data:
                    analyzed_data.append({"trend_prediction": data["trend_prediction"]})
            elif agent == "graph_builder":
                graph_data.append(data)

        context_parts: List[str] = []
        for item in analyzed_data[:5]:
            summary = item.get("analysis_summary", "")
            if summary:
                context_parts.append(f"分析结果: {summary[:300]}")
            patterns = item.get("patterns", [])
            if patterns:
                for p in patterns[:3]:
                    context_parts.append(
                        f"攻击模式: {p.get('pattern_name', '')} - {p.get('description', '')[:200]}"
                    )
        for item in cleaned_data[:3]:
            content = item.get("content", "")
            decoded = item.get("decoded_content", "")
            if decoded:
                context_parts.append(f"清洗情报: {decoded[:300]}")
            elif content:
                context_parts.append(f"原始情报: {content[:300]}")

        context_text = "\n\n".join(context_parts) if context_parts else "暂无详细分析数据"

        system_prompt = (
            "你是一个黑灰产情报综合分析专家。根据多个Agent的分析结果，"
            "综合归纳关键发现和结论。\n\n"
            "返回JSON对象，包含：\n"
            "- key_findings: 关键发现列表（字符串数组，每条不超过100字）\n"
            "- threat_assessment: 威胁评估（critical/high/medium/low/info）\n"
            "- main_threat_categories: 主要威胁类别列表\n"
            "- confidence: 综合置信度（0-1）\n"
            "- summary: 综合分析摘要（300字以内）\n\n"
            "只返回JSON，不要其他内容。"
        )
        prompt = (
            f"用户查询：{query}\n\n"
            f"成功步骤数：{len(successful)}\n"
            f"失败步骤数：{len(failed)}\n"
            f"采集情报数：{len(collected_data)}\n"
            f"清洗情报数：{len(cleaned_data)}\n"
            f"分析结果数：{len(analyzed_data)}\n\n"
            f"详细数据：\n{context_text}"
        )

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            if isinstance(result, dict):
                return {
                    "key_findings": result.get("key_findings", []),
                    "threat_assessment": result.get("threat_assessment", "info"),
                    "main_threat_categories": result.get("main_threat_categories", []),
                    "confidence": result.get("confidence", 0.5),
                    "summary": result.get("summary", ""),
                    "collected_count": len(collected_data),
                    "cleaned_count": len(cleaned_data),
                    "analyzed_count": len(analyzed_data),
                    "graph_operations": len(graph_data),
                    "successful_steps": len(successful),
                    "failed_steps": len(failed),
                }
        except Exception as exc:
            self.logger.warning(f"Result aggregation failed: {exc}")

        threat_levels = []
        for item in cleaned_data:
            tl = item.get("threat_level", "info")
            threat_levels.append(tl)
        for item in analyzed_data:
            tl = item.get("threat_level", "info")
            threat_levels.append(tl)

        overall_threat = self._pick_highest_threat(threat_levels)

        return {
            "key_findings": [f"查询: {query}", f"共采集{len(collected_data)}条情报"],
            "threat_assessment": overall_threat,
            "main_threat_categories": [],
            "confidence": 0.3,
            "summary": f"针对查询「{query}」的分析完成，共处理{len(collected_data)}条情报。",
            "collected_count": len(collected_data),
            "cleaned_count": len(cleaned_data),
            "analyzed_count": len(analyzed_data),
            "graph_operations": len(graph_data),
            "successful_steps": len(successful),
            "failed_steps": len(failed),
        }

    async def _generate_report(
        self, query: str, aggregated: Dict
    ) -> Dict:
        key_findings = aggregated.get("key_findings", [])
        threat_assessment = aggregated.get("threat_assessment", "info")
        main_categories = aggregated.get("main_threat_categories", [])
        confidence = aggregated.get("confidence", 0.5)
        summary = aggregated.get("summary", "")

        system_prompt = (
            "你是一个黑灰产情报报告撰写专家。根据综合分析结果，"
            "生成一份结构化的情报分析报告。\n\n"
            "返回JSON对象，包含：\n"
            "- title: 报告标题\n"
            "- summary: 报告摘要（200字以内）\n"
            "- key_findings: 关键发现（字符串数组）\n"
            "- threat_actors: 威胁行为者/团伙（字符串数组）\n"
            "- iocs: 失陷指标IoC（IP、域名、URL等，字符串数组）\n"
            "- recommendations: 建议措施（字符串数组）\n"
            "- confidence_score: 总体置信度（0-1）\n\n"
            "只返回JSON，不要其他内容。"
        )
        prompt = (
            f"查询：{query}\n"
            f"威胁评估：{threat_assessment}\n"
            f"主要威胁类别：{', '.join(main_categories) if main_categories else '未分类'}\n"
            f"综合置信度：{confidence:.2f}\n"
            f"关键发现：{'; '.join(key_findings[:10]) if key_findings else '无'}\n"
            f"分析摘要：{summary}\n\n"
            f"请生成情报分析报告。"
        )

        try:
            report_data = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            if isinstance(report_data, dict):
                report = IntelligenceReport(
                    title=report_data.get("title", f"情报报告: {query[:50]}"),
                    summary=report_data.get("summary", summary),
                    key_findings=report_data.get("key_findings", key_findings),
                    threat_actors=report_data.get("threat_actors", []),
                    iocs=report_data.get("iocs", []),
                    recommendations=report_data.get("recommendations", []),
                    confidence_score=float(report_data.get("confidence_score", confidence)),
                    evidence_chain=[],
                )
                return report.model_dump()
        except Exception as exc:
            self.logger.warning(f"Report generation failed: {exc}")

        report = IntelligenceReport(
            title=f"情报报告: {query[:50]}",
            summary=summary,
            key_findings=key_findings,
            threat_actors=[],
            iocs=[],
            recommendations=["建议持续监控相关情报动态"],
            confidence_score=confidence,
            evidence_chain=[],
        )
        return report.model_dump()

    async def _execute_agent_step(
        self, agent_name: str, task: Dict, context: Dict = None
    ) -> Dict:
        if context and isinstance(task, dict):
            task.setdefault("context", context)

        try:
            if agent_name == "collector":
                return await self.collector.execute(task)
            elif agent_name == "cleaner":
                return await self.cleaner.execute(task)
            elif agent_name == "analyst":
                return await self.analyst.execute(task)
            elif agent_name == "graph_builder":
                return await self.graph_builder.execute(task)
            else:
                return {
                    "status": "failed",
                    "errors": [f"Unknown agent: {agent_name}"],
                }
        except Exception as exc:
            self.logger.error(f"Agent {agent_name} execution failed: {exc}")
            return {
                "status": "failed",
                "errors": [str(exc)],
            }

    def _pir_task_to_agent_task(self, task, pir) -> Dict:
        agent_type = task.agent_type
        description = task.task_description

        if agent_type == "collector":
            return {
                "type": "collect",
                "source": "all",
                "keywords": pir.keywords,
                "max_results": 50,
            }
        elif agent_type == "cleaner":
            return {
                "type": "batch_clean",
                "raw_intelligence": [],
                "decode_blacktalk": True,
                "extract_entities": True,
            }
        elif agent_type == "analyst":
            return {
                "type": "analyze",
                "cleaned_intelligence": {},
                "context": {
                    "pir_id": pir.id,
                    "pir_title": pir.title,
                    "keywords": pir.keywords,
                },
            }
        elif agent_type == "graph_builder":
            return {
                "type": "build",
                "analysis_result": {},
            }
        else:
            return {"type": "unknown", "description": description}

    def _default_plan(self, query: str) -> List[Dict]:
        keywords = query.split()[:5] if query else []
        return [
            {
                "agent": "collector",
                "task": {
                    "type": "collect",
                    "source": "all",
                    "keywords": keywords,
                    "max_results": 50,
                },
            },
            {
                "agent": "cleaner",
                "task": {
                    "type": "batch_clean",
                    "raw_intelligence": [],
                    "decode_blacktalk": True,
                    "extract_entities": True,
                },
            },
            {
                "agent": "analyst",
                "task": {
                    "type": "analyze",
                    "cleaned_intelligence": {},
                },
            },
            {
                "agent": "graph_builder",
                "task": {
                    "type": "build",
                    "analysis_result": {},
                },
            },
        ]

    def _pick_highest_threat(self, threat_levels: List[str]) -> str:
        priority = {
            "critical": 5,
            "high": 4,
            "medium": 3,
            "low": 2,
            "info": 1,
        }
        if not threat_levels:
            return "info"
        highest = "info"
        for level in threat_levels:
            if priority.get(level, 0) > priority.get(highest, 0):
                highest = level
        return highest

    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        return self.execution_history[-limit:]

    def get_agent_status(self) -> Dict:
        return {
            "orchestrator": "active",
            "collector": {
                "name": self.collector.name,
                "registered_sources": list(self.collector.collectors.keys()),
                "active_monitors": sum(
                    1 for m in self.collector._monitor_tasks.values()
                    if m.get("status") == "active"
                ),
            },
            "cleaner": {
                "name": self.cleaner.name,
                "blacktalk_terms_count": len(
                    self.blacktalk_engine._dictionary
                ),
            },
            "analyst": {
                "name": self.analyst.name,
            },
            "graph_builder": {
                "name": self.graph_builder.name,
            },
            "execution_history_count": len(self.execution_history),
        }
