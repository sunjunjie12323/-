import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.knowledge_graph import KnowledgeGraph
from app.core.llm import LLMService
from app.core.vector_store import VectorStore


@dataclass
class PredictedStep:
    step: int
    action: str
    probability: float
    reasoning: str
    related_entities: List[str] = field(default_factory=list)
    time_window: str = ""
    risk_level: str = "medium"

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "action": self.action,
            "probability": self.probability,
            "reasoning": self.reasoning,
            "related_entities": self.related_entities,
            "time_window": self.time_window,
            "risk_level": self.risk_level,
        }


@dataclass
class PredictionResult:
    entity_id: str
    entity_name: str
    predictions: List[PredictedStep] = field(default_factory=list)
    confidence: float = 0.0
    based_on_patterns: int = 0

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "predictions": [p.to_dict() for p in self.predictions],
            "confidence": self.confidence,
            "based_on_patterns": self.based_on_patterns,
        }


@dataclass
class SimulatedChain:
    start_entity: str
    paths: List[Dict] = field(default_factory=list)
    critical_junctions: List[Dict] = field(default_factory=list)
    max_probability_path: List[PredictedStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "start_entity": self.start_entity,
            "paths": self.paths,
            "critical_junctions": self.critical_junctions,
            "max_probability_path": [p.to_dict() for p in self.max_probability_path],
        }


@dataclass
class EarlyWarning:
    predicted_step: str
    signal_description: str
    signal_source: str
    urgency: str = "monitor"
    recommended_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "predicted_step": self.predicted_step,
            "signal_description": self.signal_description,
            "signal_source": self.signal_source,
            "urgency": self.urgency,
            "recommended_actions": self.recommended_actions,
        }


class AttackChainPredictor:
    MAX_BFS_DEPTH = 4
    MAX_NEIGHBORS = 20
    PATTERN_MIN_LENGTH = 2

    def __init__(self, llm: LLMService, vector_store: VectorStore, knowledge_graph: KnowledgeGraph):
        self.llm = llm
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph

    async def predict_next_steps(self, entity_id: str, depth: int = 3) -> PredictionResult:
        entity = await self.knowledge_graph.get_entity(entity_id)
        if not entity:
            return PredictionResult(entity_id=entity_id, entity_name="unknown")

        entity_name = entity.value
        context = await self._gather_entity_context(entity_id, depth)
        patterns = await self._find_attack_patterns(entity_id, depth)
        pattern_count = len(patterns)

        try:
            predictions = await self._llm_predict(entity_name, context, patterns)
        except Exception as exc:
            logger.error(f"LLM prediction failed for entity '{entity_id}': {exc}")
            predictions = self._heuristic_predictions(entity_id, patterns)

        validated_predictions = await self._cross_validate_predictions(predictions, entity_id)

        overall_confidence = 0.0
        if validated_predictions:
            overall_confidence = sum(p.probability for p in validated_predictions) / len(validated_predictions)
            if pattern_count > 0:
                overall_confidence = min(overall_confidence * (1 + 0.1 * min(pattern_count, 5)), 1.0)

        return PredictionResult(
            entity_id=entity_id,
            entity_name=entity_name,
            predictions=validated_predictions,
            confidence=overall_confidence,
            based_on_patterns=pattern_count,
        )

    async def _gather_entity_context(self, entity_id: str, depth: int) -> str:
        subgraph = await self.knowledge_graph.get_subgraph([entity_id], depth=min(depth, 2))
        entities = subgraph.get("entities", [])
        relations = subgraph.get("relations", [])

        context_parts = []
        for e in entities:
            etype = e.get("type", "unknown")
            evalue = e.get("value", "")
            econf = e.get("confidence", 0.0)
            context_parts.append(f"实体[{etype}]: {evalue} (置信度:{econf:.2f})")

        for r in relations:
            rtype = r.get("type", "unknown")
            source = r.get("source_entity_id", "")[:8]
            target = r.get("target_entity_id", "")[:8]
            context_parts.append(f"关系: {source} -[{rtype}]-> {target}")

        intel_results = await self.vector_store.search_intelligence(entity_id, n_results=5)
        for result in intel_results[:3]:
            doc = result.get("document", "")
            if doc:
                context_parts.append(f"相关情报: {doc[:200]}")

        return "\n".join(context_parts)

    async def _find_attack_patterns(self, entity_id: str, depth: int) -> List[List[str]]:
        if entity_id not in self.knowledge_graph.graph:
            return []

        patterns: List[List[str]] = []
        visited: set = set()
        queue = deque([(entity_id, [entity_id])])
        visited.add(entity_id)

        while queue and len(patterns) < 10:
            current_id, path = queue.popleft()
            if len(path) > depth + 1:
                continue

            if self.knowledge_graph.graph.out_degree(current_id) > 0:
                for _, neighbor, data in self.knowledge_graph.graph.out_edges(current_id, data=True):
                    if neighbor not in visited and len(visited) < self.MAX_NEIGHBORS:
                        new_path = path + [neighbor]
                        if len(new_path) >= self.PATTERN_MIN_LENGTH + 1:
                            patterns.append(new_path)
                        visited.add(neighbor)
                        queue.append((neighbor, new_path))

        return patterns

    async def _llm_predict(
        self, entity_name: str, context: str, patterns: List[List[str]]
    ) -> List[PredictedStep]:
        patterns_text = ""
        if patterns:
            pattern_strs = []
            for i, p in enumerate(patterns[:5]):
                entities_in_path = []
                for eid in p:
                    entity = await self.knowledge_graph.get_entity(eid)
                    entities_in_path.append(entity.value if entity else eid[:8])
                pattern_strs.append(f"模式{i+1}: {' -> '.join(entities_in_path)}")
            patterns_text = "\n".join(pattern_strs)

        system_prompt = (
            "你是一个网络威胁攻击链预测专家。基于已知攻击实体和上下文，预测接下来最可能发生的攻击步骤。\n"
            "输出JSON格式数组：\n"
            '[{"step":1,"action":"具体行动描述","probability":0.85,"reasoning":"推理依据",'
            '"related_entities":["相关实体"],"time_window":"7天内",'
            '"risk_level":"critical/high/medium/low"}]\n'
            "probability范围0-1。考虑攻击者的动机、能力、已有资源。\n"
            "预测3-5个步骤，按概率从高到低排列。\n"
            "只返回JSON数组，不要其他内容。"
        )
        prompt_parts = [
            f"攻击实体：{entity_name}",
            f"\n当前上下文：\n{context}",
        ]
        if patterns_text:
            prompt_parts.append(f"\n已知攻击模式：\n{patterns_text}")

        prompt = "\n".join(prompt_parts)

        result = await self.llm.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )

        predictions: List[PredictedStep] = []
        items = result if isinstance(result, list) else result.get("predictions", result.get("steps", []))
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                predictions.append(PredictedStep(
                    step=int(item.get("step", len(predictions) + 1)),
                    action=item.get("action", ""),
                    probability=float(item.get("probability", 0.5)),
                    reasoning=item.get("reasoning", ""),
                    related_entities=item.get("related_entities", []),
                    time_window=item.get("time_window", "未知"),
                    risk_level=item.get("risk_level", "medium"),
                ))

        predictions.sort(key=lambda p: p.probability, reverse=True)
        return predictions

    def _heuristic_predictions(self, entity_id: str, patterns: List[List[str]]) -> List[PredictedStep]:
        predictions: List[PredictedStep] = []
        if not patterns:
            return predictions

        next_entities: Dict[str, int] = {}
        for pattern in patterns:
            if len(pattern) >= 2 and pattern[0] == entity_id:
                next_eid = pattern[1]
                next_entities[next_eid] = next_entities.get(next_eid, 0) + 1

        sorted_next = sorted(next_entities.items(), key=lambda x: x[1], reverse=True)
        for i, (eid, count) in enumerate(sorted_next[:5]):
            predictions.append(PredictedStep(
                step=i + 1,
                action=f"可能转向实体 {eid[:8]}",
                probability=min(count / max(len(patterns), 1), 1.0),
                reasoning=f"在{count}个已知攻击模式中出现",
                related_entities=[eid],
                time_window="未知",
                risk_level="medium",
            ))

        return predictions

    async def _cross_validate_predictions(
        self, predictions: List[PredictedStep], entity_id: str
    ) -> List[PredictedStep]:
        if not predictions:
            return predictions

        validated: List[PredictedStep] = []
        for pred in predictions:
            action_text = pred.action
            try:
                results = await self.vector_store.search_intelligence(action_text, n_results=3)
                support_count = 0
                for result in results:
                    doc = result.get("document", "")
                    if doc and any(kw in doc for kw in action_text.split()[:3]):
                        support_count += 1

                if support_count > 0:
                    pred.probability = min(pred.probability * 1.1, 1.0)
                else:
                    pred.probability = pred.probability * 0.85
            except Exception:
                pass

            validated.append(pred)

        return validated

    async def simulate_attack_chain(
        self, start_entity_id: str, steps: int = 5
    ) -> SimulatedChain:
        entity = await self.knowledge_graph.get_entity(start_entity_id)
        if not entity:
            return SimulatedChain(start_entity=start_entity_id)

        all_paths: List[Dict] = []
        critical_junctions: List[Dict] = []

        await self._build_path_tree(
            current_entity_id=start_entity_id,
            current_path=[],
            current_prob=1.0,
            remaining_steps=steps,
            all_paths=all_paths,
            critical_junctions=critical_junctions,
            visited=set(),
        )

        max_prob_path: List[PredictedStep] = []
        if all_paths:
            best_path = max(all_paths, key=lambda p: p.get("cumulative_probability", 0))
            for i, step_data in enumerate(best_path.get("steps", [])):
                max_prob_path.append(PredictedStep(
                    step=i + 1,
                    action=step_data.get("action", ""),
                    probability=step_data.get("probability", 0.0),
                    reasoning=step_data.get("reasoning", ""),
                    related_entities=step_data.get("related_entities", []),
                    time_window=step_data.get("time_window", ""),
                    risk_level=step_data.get("risk_level", "medium"),
                ))

        return SimulatedChain(
            start_entity=start_entity_id,
            paths=all_paths,
            critical_junctions=critical_junctions,
            max_probability_path=max_prob_path,
        )

    async def _build_path_tree(
        self,
        current_entity_id: str,
        current_path: List[Dict],
        current_prob: float,
        remaining_steps: int,
        all_paths: List[Dict],
        critical_junctions: List[Dict],
        visited: set,
    ) -> None:
        if remaining_steps <= 0 or current_prob < 0.05:
            if current_path:
                all_paths.append({
                    "steps": current_path.copy(),
                    "cumulative_probability": current_prob,
                })
            return

        visited.add(current_entity_id)

        try:
            prediction = await self.predict_next_steps(current_entity_id, depth=2)
        except Exception as exc:
            logger.warning(f"Prediction failed during simulation at '{current_entity_id}': {exc}")
            if current_path:
                all_paths.append({
                    "steps": current_path.copy(),
                    "cumulative_probability": current_prob,
                })
            visited.discard(current_entity_id)
            return

        if not prediction.predictions:
            if current_path:
                all_paths.append({
                    "steps": current_path.copy(),
                    "cumulative_probability": current_prob,
                })
            visited.discard(current_entity_id)
            return

        if len(prediction.predictions) > 1:
            critical_junctions.append({
                "entity_id": current_entity_id,
                "step": len(current_path) + 1,
                "branch_count": len(prediction.predictions),
                "branches": [
                    {"action": p.action, "probability": p.probability}
                    for p in prediction.predictions
                ],
            })

        for pred in prediction.predictions[:3]:
            step_data = pred.to_dict()
            new_prob = current_prob * pred.probability

            next_entity_id = None
            if pred.related_entities:
                next_entity_id = pred.related_entities[0]

            new_path = current_path + [step_data]

            if next_entity_id and next_entity_id not in visited:
                await self._build_path_tree(
                    current_entity_id=next_entity_id,
                    current_path=new_path,
                    current_prob=new_prob,
                    remaining_steps=remaining_steps - 1,
                    all_paths=all_paths,
                    critical_junctions=critical_junctions,
                    visited=visited.copy(),
                )
            else:
                all_paths.append({
                    "steps": new_path,
                    "cumulative_probability": new_prob,
                })

        visited.discard(current_entity_id)

    async def find_early_warning_signals(
        self, prediction: PredictionResult
    ) -> List[EarlyWarning]:
        warnings: List[EarlyWarning] = []

        for pred in prediction.predictions:
            try:
                signals = await self._search_signals_for_step(pred)
                warnings.extend(signals)
            except Exception as exc:
                logger.warning(
                    f"Early warning search failed for step '{pred.action}': {exc}"
                )

        warnings.sort(
            key=lambda w: {"immediate": 0, "urgent": 1, "monitor": 2}.get(w.urgency, 2)
        )
        return warnings

    async def _search_signals_for_step(self, step: PredictedStep) -> List[EarlyWarning]:
        warnings: List[EarlyWarning] = []
        action_keywords = step.action.split()[:5]
        search_query = " ".join(action_keywords)

        try:
            results = await self.vector_store.search_intelligence(search_query, n_results=5)
        except Exception:
            return warnings

        for result in results:
            doc = result.get("document", "")
            metadata = result.get("metadata", {})
            if not doc:
                continue

            try:
                is_signal = await self._llm_check_signal(step.action, doc)
            except Exception:
                is_signal = self._heuristic_signal_check(step.action, doc)

            if is_signal:
                urgency = self._determine_urgency(step, result)
                actions = self._generate_recommended_actions(step, urgency)

                warnings.append(EarlyWarning(
                    predicted_step=step.action,
                    signal_description=f"发现与预测步骤相关的情报活动: {doc[:150]}",
                    signal_source=metadata.get("source", "unknown"),
                    urgency=urgency,
                    recommended_actions=actions,
                ))

        return warnings

    async def _llm_check_signal(self, predicted_action: str, intelligence_text: str) -> bool:
        system_prompt = (
            "你是一个威胁情报预警专家。判断以下情报是否表明预测的攻击步骤正在发生或即将发生。\n"
            "只回答 '是' 或 '否'。"
        )
        prompt = (
            f"预测的攻击步骤：{predicted_action}\n\n"
            f"情报内容：{intelligence_text[:500]}\n\n"
            "该情报是否表明此攻击步骤正在发生或即将发生？"
        )

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=10,
            )
            return "是" in response.strip()
        except Exception:
            return False

    def _heuristic_signal_check(self, predicted_action: str, intelligence_text: str) -> bool:
        action_words = set(predicted_action.split())
        intel_words = set(intelligence_text.split())
        overlap = action_words & intel_words
        return len(overlap) >= 2

    def _determine_urgency(self, step: PredictedStep, intel_result: Dict) -> str:
        if step.risk_level in ("critical", "high") and step.probability >= 0.7:
            return "immediate"
        if step.risk_level in ("critical", "high") or step.probability >= 0.6:
            return "urgent"
        return "monitor"

    def _generate_recommended_actions(self, step: PredictedStep, urgency: str) -> List[str]:
        actions: List[str] = []

        if urgency == "immediate":
            actions.append("立即启动应急响应流程")
            actions.append(f"针对'{step.action}'加强监控")
            actions.append("通知相关安全团队")
        elif urgency == "urgent":
            actions.append(f"加强对'{step.action}'相关指标的监控")
            actions.append("更新防御规则")
        else:
            actions.append(f"持续关注'{step.action}'相关动态")
            actions.append("定期复查情报更新")

        if step.related_entities:
            actions.append(f"重点关注关联实体: {', '.join(step.related_entities[:5])}")

        return actions
