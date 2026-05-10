import os
import pickle
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from app.core.knowledge_graph import KnowledgeGraph
from app.core.vector_store import VectorStore


@dataclass
class PredictedStep:
    step: int
    action: str
    technique_id: str
    technique_name: str
    probability: float
    reasoning: str
    related_entities: List[str] = field(default_factory=list)
    time_window: str = ""
    risk_level: str = "medium"

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "action": self.action,
            "technique_id": self.technique_id,
            "technique_name": self.technique_name,
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


MITRE_TECHNIQUES = {
    "T1595": {"name": "主动扫描", "tactic": "reconnaissance", "risk": "low"},
    "T1592": {"name": "收集受害者主机信息", "tactic": "reconnaissance", "risk": "low"},
    "T1589": {"name": "收集受害者身份信息", "tactic": "reconnaissance", "risk": "medium"},
    "T1566": {"name": "钓鱼攻击", "tactic": "initial_access", "risk": "high"},
    "T1190": {"name": "利用公开应用漏洞", "tactic": "initial_access", "risk": "critical"},
    "T1078": {"name": "有效账号", "tactic": "initial_access", "risk": "high"},
    "T1059": {"name": "命令行脚本执行", "tactic": "execution", "risk": "high"},
    "T1204": {"name": "用户执行", "tactic": "execution", "risk": "medium"},
    "T1053": {"name": "计划任务", "tactic": "execution", "risk": "medium"},
    "T1055": {"name": "进程注入", "tactic": "defense_evasion", "risk": "high"},
    "T1070": {"name": "痕迹清除", "tactic": "defense_evasion", "risk": "high"},
    "T1562": {"name": "削弱防御", "tactic": "defense_evasion", "risk": "critical"},
    "T1027": {"name": "混淆文件或信息", "tactic": "defense_evasion", "risk": "medium"},
    "T1082": {"name": "系统信息发现", "tactic": "discovery", "risk": "low"},
    "T1083": {"name": "文件和目录发现", "tactic": "discovery", "risk": "low"},
    "T1046": {"name": "网络服务发现", "tactic": "discovery", "risk": "medium"},
    "T1005": {"name": "本地数据收集", "tactic": "collection", "risk": "medium"},
    "T1039": {"name": "共享驱动器数据收集", "tactic": "collection", "risk": "medium"},
    "T1041": {"name": "通过C2通道渗出数据", "tactic": "exfiltration", "risk": "high"},
    "T1048": {"name": "通过替代协议渗出", "tactic": "exfiltration", "risk": "high"},
    "T1071": {"name": "应用层协议通信", "tactic": "command_and_control", "risk": "high"},
    "T1573": {"name": "加密通道", "tactic": "command_and_control", "risk": "medium"},
    "T1095": {"name": "非应用层协议通信", "tactic": "command_and_control", "risk": "medium"},
    "T1486": {"name": "数据加密勒索", "tactic": "impact", "risk": "critical"},
    "T1489": {"name": "服务停止", "tactic": "impact", "risk": "critical"},
    "T1490": {"name": " inhibit system recovery", "tactic": "impact", "risk": "critical"},
    "T1111": {"name": "认证钓鱼", "tactic": "credential_access", "risk": "high"},
    "T1558": {"name": "Kerberoasting", "tactic": "credential_access", "risk": "high"},
    "T1003": {"name": "操作系统凭证转储", "tactic": "credential_access", "risk": "critical"},
    "T1548": {"name": "权限提升滥用", "tactic": "privilege_escalation", "risk": "high"},
    "T1068": {"name": "漏洞利用提权", "tactic": "privilege_escalation", "risk": "critical"},
    "T1547": {"name": "启动项劫持", "tactic": "persistence", "risk": "high"},
    "T1133": {"name": "外部远程服务", "tactic": "persistence", "risk": "medium"},
    "T1050": {"name": "新建服务", "tactic": "persistence", "risk": "medium"},
    "T1098": {"name": "账号操作", "tactic": "persistence", "risk": "medium"},
    "T1070.004": {"name": "文件删除", "tactic": "defense_evasion", "risk": "medium"},
    "T1071.001": {"name": "Web协议通信", "tactic": "command_and_control", "risk": "high"},
    "T1566.001": {"name": "钓鱼附件", "tactic": "initial_access", "risk": "high"},
    "T1566.002": {"name": "钓鱼链接", "tactic": "initial_access", "risk": "high"},
    "T1059.001": {"name": "PowerShell执行", "tactic": "execution", "risk": "high"},
    "T1059.003": {"name": "Windows命令行", "tactic": "execution", "risk": "medium"},
}

MITRE_TRANSITIONS = {
    "reconnaissance": {"initial_access": 0.7, "reconnaissance": 0.3},
    "initial_access": {"execution": 0.5, "persistence": 0.2, "credential_access": 0.15, "defense_evasion": 0.15},
    "execution": {"persistence": 0.25, "privilege_escalation": 0.25, "defense_evasion": 0.2, "discovery": 0.15, "credential_access": 0.15},
    "persistence": {"privilege_escalation": 0.3, "defense_evasion": 0.25, "discovery": 0.2, "credential_access": 0.15, "execution": 0.1},
    "privilege_escalation": {"credential_access": 0.3, "discovery": 0.25, "collection": 0.2, "defense_evasion": 0.15, "persistence": 0.1},
    "defense_evasion": {"credential_access": 0.2, "discovery": 0.2, "persistence": 0.2, "execution": 0.2, "privilege_escalation": 0.2},
    "credential_access": {"discovery": 0.3, "collection": 0.25, "lateral_movement": 0.2, "persistence": 0.15, "privilege_escalation": 0.1},
    "discovery": {"collection": 0.3, "lateral_movement": 0.25, "credential_access": 0.2, "command_and_control": 0.15, "execution": 0.1},
    "lateral_movement": {"collection": 0.3, "credential_access": 0.25, "discovery": 0.2, "command_and_control": 0.15, "persistence": 0.1},
    "collection": {"command_and_control": 0.35, "exfiltration": 0.3, "collection": 0.15, "lateral_movement": 0.1, "impact": 0.1},
    "command_and_control": {"exfiltration": 0.4, "impact": 0.25, "collection": 0.15, "lateral_movement": 0.1, "defense_evasion": 0.1},
    "exfiltration": {"impact": 0.3, "command_and_control": 0.2, "defense_evasion": 0.2, "exfiltration": 0.15, "collection": 0.15},
    "impact": {"defense_evasion": 0.3, "exfiltration": 0.2, "impact": 0.2, "command_and_control": 0.15, "persistence": 0.15},
}

ENTITY_TYPE_TO_TACTIC = {
    "malware": "execution",
    "threat_actor": "initial_access",
    "vulnerability": "initial_access",
    "attack_pattern": "execution",
    "tool": "execution",
    "ip": "command_and_control",
    "ip_address": "command_and_control",
    "domain": "command_and_control",
    "url": "initial_access",
    "hash": "execution",
    "email": "initial_access",
    "phone": "initial_access",
    "organization": "reconnaissance",
    "person": "credential_access",
    "location": "reconnaissance",
    "financial_account": "credential_access",
    "account": "credential_access",
    "website": "initial_access",
    "service": "discovery",
    "blacktalk": "reconnaissance",
    "crypto_wallet": "command_and_control",
    "payment_method": "credential_access",
}


class AttackChainPredictor:
    MAX_BFS_DEPTH = 4
    MAX_NEIGHBORS = 20
    PATTERN_MIN_LENGTH = 2
    SMOOTHING_ALPHA = 0.1

    def __init__(self, vector_store: VectorStore, knowledge_graph: KnowledgeGraph):
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self._transition_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._technique_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._total_transitions = 0
        self._persist_dir = "./model_data/attack_chain"
        os.makedirs(self._persist_dir, exist_ok=True)
        self._load_model()

    def _load_model(self):
        model_path = os.path.join(self._persist_dir, "markov_chain.pkl")
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    data = pickle.load(f)
                self._transition_counts = defaultdict(lambda: defaultdict(int), data.get("transition_counts", {}))
                self._technique_counts = defaultdict(lambda: defaultdict(int), data.get("technique_counts", {}))
                self._total_transitions = data.get("total_transitions", 0)
                logger.info(f"Markov chain loaded: {self._total_transitions} transitions")
            except Exception as exc:
                logger.warning(f"Failed to load Markov chain: {exc}")

    def _save_model(self):
        model_path = os.path.join(self._persist_dir, "markov_chain.pkl")
        data = {
            "transition_counts": dict(self._transition_counts),
            "technique_counts": dict(self._technique_counts),
            "total_transitions": self._total_transitions,
        }
        with open(model_path, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"Markov chain saved: {self._total_transitions} transitions")

    def train_from_graph(self):
        transitions_learned = 0
        if not self.knowledge_graph.graph or self.knowledge_graph.graph.number_of_nodes() == 0:
            logger.warning("Knowledge graph empty, using MITRE ATT&CK prior transitions")
            self._load_mitre_priors()
            return

        self._load_mitre_priors()

        tactic_entity_counts: Dict[str, int] = defaultdict(int)
        for node_id in self.knowledge_graph.graph.nodes():
            node_data = self.knowledge_graph.graph.nodes[node_id]
            entity_type = node_data.get("type", node_data.get("entity_type", "unknown"))
            tactic = ENTITY_TYPE_TO_TACTIC.get(entity_type, "unknown")
            if tactic != "unknown":
                tactic_entity_counts[tactic] += 1

        total_entities = sum(tactic_entity_counts.values()) or 1
        for src_tactic in list(self._transition_counts.keys()):
            for dst_tactic in list(self._transition_counts[src_tactic].keys()):
                obs_count = tactic_entity_counts.get(dst_tactic, 0)
                obs_freq = obs_count / total_entities
                boost = int(obs_freq * 50)
                if boost > 0:
                    self._transition_counts[src_tactic][dst_tactic] += boost
                    self._total_transitions += boost

        for source in self.knowledge_graph.graph.nodes():
            source_entity = self.knowledge_graph.graph.nodes[source]
            source_type = source_entity.get("type", source_entity.get("entity_type", "unknown"))
            source_tactic = ENTITY_TYPE_TO_TACTIC.get(source_type, "unknown")

            for _, target, data in self.knowledge_graph.graph.out_edges(source, data=True):
                target_entity = self.knowledge_graph.graph.nodes[target]
                target_type = target_entity.get("type", target_entity.get("entity_type", "unknown"))
                target_tactic = ENTITY_TYPE_TO_TACTIC.get(target_type, "unknown")

                if source_tactic != "unknown" and target_tactic != "unknown":
                    self._transition_counts[source_tactic][target_tactic] += 1
                    self._total_transitions += 1
                    transitions_learned += 1

                    relation_type = data.get("type", data.get("relation_type", "unknown"))
                    matching_techniques = [
                        tid for tid, tinfo in MITRE_TECHNIQUES.items()
                        if tinfo["tactic"] == target_tactic
                    ]
                    if matching_techniques:
                        self._technique_counts[target_tactic][relation_type] = len(matching_techniques)

        logger.info(f"Learned {transitions_learned} transitions from knowledge graph (adjusted with {sum(tactic_entity_counts.values())} entity observations)")
        self._save_model()

    def _load_mitre_priors(self):
        for src_tactic, transitions in MITRE_TRANSITIONS.items():
            for dst_tactic, prob in transitions.items():
                count = int(prob * 100)
                self._transition_counts[src_tactic][dst_tactic] += count
                self._total_transitions += count
        logger.info(f"Loaded MITRE ATT&CK prior transitions: {self._total_transitions} total")
        self._save_model()

    def _get_transition_prob(self, from_tactic: str, to_tactic: str) -> float:
        from_counts = self._transition_counts.get(from_tactic, {})
        total = sum(from_counts.values())
        if total == 0:
            prior = MITRE_TRANSITIONS.get(from_tactic, {}).get(to_tactic, 0.01)
            return prior
        count = from_counts.get(to_tactic, 0)
        smoothed = (count + self.SMOOTHING_ALPHA) / (total + self.SMOOTHING_ALPHA * len(MITRE_TRANSITIONS))
        return smoothed

    def _predict_next_tactics(self, current_tactic: str, top_k: int = 3) -> List[Tuple[str, float]]:
        candidates = []
        for tactic in MITRE_TRANSITIONS.get(current_tactic, {}):
            prob = self._get_transition_prob(current_tactic, tactic)
            candidates.append((tactic, prob))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def _get_techniques_for_tactic(self, tactic: str) -> List[Tuple[str, dict]]:
        return [
            (tid, tinfo) for tid, tinfo in MITRE_TECHNIQUES.items()
            if tinfo["tactic"] == tactic
        ]

    def _map_entity_to_tactic(self, entity_id: str) -> str:
        if entity_id in self.knowledge_graph.graph.nodes:
            entity_type = self.knowledge_graph.graph.nodes[entity_id].get("type", self.knowledge_graph.graph.nodes[entity_id].get("entity_type", "unknown"))
            return ENTITY_TYPE_TO_TACTIC.get(entity_type, "reconnaissance")
        return "reconnaissance"

    async def predict_next_steps(self, entity_id: str, depth: int = 3) -> PredictionResult:
        entity = await self.knowledge_graph.get_entity(entity_id)
        if not entity:
            return PredictionResult(entity_id=entity_id, entity_name="unknown")

        entity_name = entity.value
        current_tactic = self._map_entity_to_tactic(entity_id)
        next_tactics = self._predict_next_tactics(current_tactic, top_k=depth)

        patterns = await self._find_attack_patterns(entity_id, depth)
        pattern_count = len(patterns)

        predictions: List[PredictedStep] = []
        for step_idx, (tactic, tactic_prob) in enumerate(next_tactics):
            techniques = self._get_techniques_for_tactic(tactic)
            if not techniques:
                continue

            risk_weights = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}
            technique_scores = []
            for tid, tinfo in techniques:
                risk = tinfo.get("risk", "medium")
                base_weight = risk_weights.get(risk, 1.0)
                graph_boost = 0.0
                tc = self._technique_counts.get(tactic, {})
                for rel_type, count in tc.items():
                    if rel_type and rel_type.lower() in tinfo["name"].lower():
                        graph_boost += count * 0.5
                score = base_weight + graph_boost
                technique_scores.append((tid, tinfo, score))

            total_score = sum(s for _, _, s in technique_scores)
            technique_scores.sort(key=lambda x: x[2], reverse=True)
            top_techniques = technique_scores[:3]

            for tid, tinfo, score in top_techniques:
                technique_prob = score / total_score if total_score > 0 else 1.0 / len(top_techniques)
                combined_prob = tactic_prob * technique_prob
                combined_prob = min(combined_prob, 1.0)

                for pattern in patterns:
                    if len(pattern) >= 2 and pattern[0] == entity_id:
                        for nid in pattern[1:]:
                            n_entity = await self.knowledge_graph.get_entity(nid)
                            if n_entity:
                                n_tactic = ENTITY_TYPE_TO_TACTIC.get(n_entity.type.value if hasattr(n_entity.type, 'value') else str(n_entity.type), "")
                                if n_tactic == tactic:
                                    combined_prob = min(combined_prob * 1.3, 1.0)

                risk = tinfo.get("risk", "medium")
                predictions.append(PredictedStep(
                    step=len(predictions) + 1,
                    action=f"可能执行{tinfo['name']}({tid})",
                    technique_id=tid,
                    technique_name=tinfo["name"],
                    probability=round(combined_prob, 3),
                    reasoning=f"基于MITRE ATT&CK马尔可夫链: {current_tactic}→{tactic}(P={tactic_prob:.3f}), 技术{tid}属于{tactic}阶段",
                    related_entities=[entity_id],
                    time_window=self._estimate_time_window(tactic),
                    risk_level=risk,
                ))

        predictions.sort(key=lambda p: p.probability, reverse=True)

        overall_confidence = 0.0
        if predictions:
            overall_confidence = sum(p.probability for p in predictions) / len(predictions)
            if pattern_count > 0:
                overall_confidence = min(overall_confidence * (1 + 0.1 * min(pattern_count, 5)), 1.0)

        return PredictionResult(
            entity_id=entity_id,
            entity_name=entity_name,
            predictions=predictions,
            confidence=overall_confidence,
            based_on_patterns=pattern_count,
        )

    def _estimate_time_window(self, tactic: str) -> str:
        windows = {
            "reconnaissance": "1-30天",
            "initial_access": "1-7天",
            "execution": "数小时内",
            "persistence": "1-3天",
            "privilege_escalation": "数小时内",
            "defense_evasion": "数小时内",
            "credential_access": "1-3天",
            "discovery": "1-7天",
            "lateral_movement": "1-14天",
            "collection": "1-7天",
            "command_and_control": "持续",
            "exfiltration": "1-3天",
            "impact": "数小时内",
        }
        return windows.get(tactic, "未知")

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

    async def simulate_attack_chain(self, start_entity_id: str, steps: int = 5) -> SimulatedChain:
        entity = await self.knowledge_graph.get_entity(start_entity_id)
        if not entity:
            return SimulatedChain(start_entity=start_entity_id)

        all_paths: List[Dict] = []
        critical_junctions: List[Dict] = []
        current_tactic = self._map_entity_to_tactic(start_entity_id)

        self._simulate_markov_chain(
            current_tactic=current_tactic,
            current_path=[],
            current_prob=1.0,
            remaining_steps=steps,
            all_paths=all_paths,
            critical_junctions=critical_junctions,
            visited_tactics=set(),
        )

        max_prob_path: List[PredictedStep] = []
        if all_paths:
            best_path = max(all_paths, key=lambda p: p.get("cumulative_probability", 0))
            for i, step_data in enumerate(best_path.get("steps", [])):
                technique_id = step_data.get("technique_id", "")
                technique_info = MITRE_TECHNIQUES.get(technique_id, {})
                max_prob_path.append(PredictedStep(
                    step=i + 1,
                    action=step_data.get("action", ""),
                    technique_id=technique_id,
                    technique_name=technique_info.get("name", ""),
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

    def _simulate_markov_chain(
        self,
        current_tactic: str,
        current_path: List[Dict],
        current_prob: float,
        remaining_steps: int,
        all_paths: List[Dict],
        critical_junctions: List[Dict],
        visited_tactics: set,
    ) -> None:
        if remaining_steps <= 0 or current_prob < 0.05:
            if current_path:
                all_paths.append({
                    "steps": current_path.copy(),
                    "cumulative_probability": current_prob,
                })
            return

        next_tactics = self._predict_next_tactics(current_tactic, top_k=3)

        if len(next_tactics) > 1:
            critical_junctions.append({
                "tactic": current_tactic,
                "step": len(current_path) + 1,
                "branch_count": len(next_tactics),
                "branches": [{"tactic": t, "probability": p} for t, p in next_tactics],
            })

        for tactic, tactic_prob in next_tactics:
            techniques = self._get_techniques_for_tactic(tactic)
            if not techniques:
                continue

            best_technique = min(techniques, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x[1]["risk"], 4))
            tid, tinfo = best_technique

            new_prob = current_prob * tactic_prob
            step_data = {
                "action": f"执行{tinfo['name']}({tid})",
                "technique_id": tid,
                "technique_name": tinfo["name"],
                "probability": tactic_prob,
                "reasoning": f"马尔可夫链: {current_tactic}→{tactic}(P={tactic_prob:.3f})",
                "time_window": self._estimate_time_window(tactic),
                "risk_level": tinfo.get("risk", "medium"),
                "related_entities": [],
            }

            new_path = current_path + [step_data]

            if tactic not in visited_tactics:
                new_visited = visited_tactics | {tactic}
                self._simulate_markov_chain(
                    current_tactic=tactic,
                    current_path=new_path,
                    current_prob=new_prob,
                    remaining_steps=remaining_steps - 1,
                    all_paths=all_paths,
                    critical_junctions=critical_junctions,
                    visited_tactics=new_visited,
                )
            else:
                all_paths.append({
                    "steps": new_path,
                    "cumulative_probability": new_prob,
                })

    async def find_early_warning_signals(self, prediction: PredictionResult) -> List[EarlyWarning]:
        warnings: List[EarlyWarning] = []

        for pred in prediction.predictions:
            search_terms = [pred.technique_name, pred.technique_id, pred.action]
            for term in search_terms:
                try:
                    results = await self.vector_store.search_intelligence(term, n_results=3)
                    for result in results:
                        doc = result.get("document", "")
                        metadata = result.get("metadata", {})
                        if not doc:
                            continue

                        overlap = sum(1 for kw in pred.action.split() if kw in doc)
                        if overlap >= 1 or pred.technique_id in doc:
                            urgency = self._determine_urgency(pred, result)
                            actions = self._generate_recommended_actions(pred, urgency)
                            warnings.append(EarlyWarning(
                                predicted_step=pred.action,
                                signal_description=f"发现与{pred.technique_id}({pred.technique_name})相关的情报活动: {doc[:150]}",
                                signal_source=metadata.get("source", "unknown"),
                                urgency=urgency,
                                recommended_actions=actions,
                            ))
                except Exception:
                    pass

        seen = set()
        unique_warnings = []
        for w in warnings:
            key = (w.predicted_step, w.signal_source)
            if key not in seen:
                seen.add(key)
                unique_warnings.append(w)

        unique_warnings.sort(
            key=lambda w: {"immediate": 0, "urgent": 1, "monitor": 2}.get(w.urgency, 2)
        )
        return unique_warnings

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
            actions.append(f"针对{step.technique_id}({step.technique_name})加强监控")
            actions.append("通知相关安全团队")
        elif urgency == "urgent":
            actions.append(f"加强对{step.technique_name}相关指标的监控")
            actions.append("更新防御规则")
        else:
            actions.append(f"持续关注{step.technique_name}相关动态")
            actions.append("定期复查情报更新")
        if step.related_entities:
            actions.append(f"重点关注关联实体: {', '.join(step.related_entities[:5])}")
        return actions
