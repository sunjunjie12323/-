import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import networkx as nx
from loguru import logger

from app.models.entity import Entity, EntityType, Relation, RelationType


class KnowledgeGraph:
    PERSIST_FILENAME = "knowledge_graph.json"

    def __init__(self, persist_dir: str = "./graph_data"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.persist_path = self.persist_dir / self.PERSIST_FILENAME
        self.graph = nx.DiGraph()
        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = {}
        self._load_on_init = True
        try:
            data = self._load_sync()
            if data:
                self._import_data(data)
            logger.info(
                f"KnowledgeGraph loaded: {self.graph.number_of_nodes()} nodes, "
                f"{self.graph.number_of_edges()} edges"
            )
        except Exception:
            logger.info("KnowledgeGraph initialized empty (no persisted data found)")

    async def add_entity(self, entity: Entity) -> str:
        self._entities[entity.id] = entity
        self.graph.add_node(
            entity.id,
            type=entity.type.value,
            value=entity.value,
            confidence=entity.confidence,
            context=entity.context or "",
        )
        logger.debug(f"Added entity to graph: {entity.id} ({entity.type.value}: {entity.value})")
        return entity.id

    async def add_relation(self, relation: Relation) -> str:
        if relation.source_entity_id not in self._entities:
            logger.warning(
                f"Source entity {relation.source_entity_id} not found, adding placeholder"
            )
        if relation.target_entity_id not in self._entities:
            logger.warning(
                f"Target entity {relation.target_entity_id} not found, adding placeholder"
            )
        self._relations[relation.id] = relation
        self.graph.add_edge(
            relation.source_entity_id,
            relation.target_entity_id,
            id=relation.id,
            type=relation.type.value,
            confidence=relation.confidence,
            evidence=relation.evidence or "",
        )
        logger.debug(
            f"Added relation to graph: {relation.id} "
            f"({relation.source_entity_id} -[{relation.type.value}]-> {relation.target_entity_id})"
        )
        return relation.id

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    async def get_relation(self, relation_id: str) -> Optional[Relation]:
        return self._relations.get(relation_id)

    async def get_entity_relations(
        self,
        entity_id: str,
        direction: str = "both",
        relation_type: Optional[str] = None,
    ) -> List[Relation]:
        if entity_id not in self.graph:
            return []
        edge_ids: Set[str] = set()
        if direction in ("both", "outgoing"):
            for _, target, data in self.graph.out_edges(entity_id, data=True):
                if relation_type is None or data.get("type") == relation_type:
                    edge_ids.add(data.get("id", ""))
        if direction in ("both", "incoming"):
            for source, _, data in self.graph.in_edges(entity_id, data=True):
                if relation_type is None or data.get("type") == relation_type:
                    edge_ids.add(data.get("id", ""))
        return [self._relations[rid] for rid in edge_ids if rid in self._relations]

    async def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Entity]:
        results: List[Entity] = []
        query_lower = query.lower()
        for entity in self._entities.values():
            if entity_type and entity.type.value != entity_type:
                continue
            if query_lower in entity.value.lower() or (
                entity.context and query_lower in entity.context.lower()
            ):
                results.append(entity)
                if len(results) >= limit:
                    break
        return results

    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> List[List[str]]:
        if source_id not in self.graph or target_id not in self.graph:
            return []
        try:
            undirected = self.graph.to_undirected()
            all_paths: List[List[str]] = []
            for path in nx.all_simple_paths(
                undirected, source_id, target_id, cutoff=max_depth
            ):
                all_paths.append(path)
                if len(all_paths) >= 10:
                    break
            all_paths.sort(key=len)
            return all_paths[:5]
        except nx.NetworkXNoPath:
            return []
        except Exception as exc:
            logger.error(f"Path finding failed: {exc}")
            return []

    async def find_communities(self, algorithm: str = "louvain") -> List[List[str]]:
        if self.graph.number_of_nodes() == 0:
            return []
        try:
            undirected = self.graph.to_undirected()
            if algorithm == "louvain":
                from networkx.algorithms.community import louvain_communities

                communities = louvain_communities(undirected, seed=42)
            elif algorithm == "greedy":
                from networkx.algorithms.community import greedy_modularity_communities

                communities = greedy_modularity_communities(undirected)
            else:
                from networkx.algorithms.community import louvain_communities

                communities = louvain_communities(undirected, seed=42)

            result: List[List[str]] = []
            for community in communities:
                members = [str(node) for node in community]
                if len(members) >= 2:
                    result.append(members)
            result.sort(key=len, reverse=True)
            return result
        except Exception as exc:
            logger.error(f"Community detection failed: {exc}")
            return []

    async def get_subgraph(
        self,
        entity_ids: List[str],
        depth: int = 1,
    ) -> Dict:
        visited_nodes: Set[str] = set(entity_ids)
        visited_edges: Set[str] = set()
        current_frontier = set(entity_ids)

        for _ in range(depth):
            next_frontier: Set[str] = set()
            for node_id in current_frontier:
                if node_id not in self.graph:
                    continue
                for _, target, data in self.graph.out_edges(node_id, data=True):
                    visited_nodes.add(target)
                    edge_id = data.get("id", "")
                    if edge_id:
                        visited_edges.add(edge_id)
                    next_frontier.add(target)
                for source, _, data in self.graph.in_edges(node_id, data=True):
                    visited_nodes.add(source)
                    edge_id = data.get("id", "")
                    if edge_id:
                        visited_edges.add(edge_id)
                    next_frontier.add(source)
            current_frontier = next_frontier - visited_nodes
            if not current_frontier:
                break

        entities = [
            self._entities[eid].model_dump()
            for eid in visited_nodes
            if eid in self._entities
        ]
        relations = [
            self._relations[rid].model_dump()
            for rid in visited_edges
            if rid in self._relations
        ]
        return {
            "entities": entities,
            "relations": relations,
            "node_count": len(entities),
            "edge_count": len(relations),
        }

    async def get_statistics(self) -> Dict:
        node_count = self.graph.number_of_nodes()
        edge_count = self.graph.number_of_edges()
        type_counts: Dict[str, int] = defaultdict(int)
        for entity in self._entities.values():
            type_counts[entity.type.value] += 1
        relation_type_counts: Dict[str, int] = defaultdict(int)
        for relation in self._relations.values():
            relation_type_counts[relation.type.value] += 1
        density = (
            nx.density(self.graph) if node_count > 0 else 0.0
        )
        avg_clustering = 0.0
        if node_count > 0:
            try:
                undirected = self.graph.to_undirected()
                avg_clustering = nx.average_clustering(undirected)
            except Exception:
                avg_clustering = 0.0
        connected_components = 0
        if node_count > 0:
            try:
                undirected = self.graph.to_undirected()
                connected_components = nx.number_connected_components(undirected)
            except Exception:
                connected_components = 0
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "entity_types": dict(type_counts),
            "relation_types": dict(relation_type_counts),
            "density": density,
            "average_clustering": avg_clustering,
            "connected_components": connected_components,
        }

    async def export_graph(self, format: str = "json") -> Dict:
        if format != "json":
            raise ValueError(f"Unsupported export format: {format}. Only 'json' is supported.")
        entities_data = {}
        for eid, entity in self._entities.items():
            entities_data[eid] = entity.model_dump()
        relations_data = {}
        for rid, relation in self._relations.items():
            relations_data[rid] = relation.model_dump()
        node_data = {}
        for node_id in self.graph.nodes:
            node_data[node_id] = dict(self.graph.nodes[node_id])
        edge_data = []
        for source, target, data in self.graph.edges(data=True):
            edge_data.append({"source": source, "target": target, **data})
        return {
            "entities": entities_data,
            "relations": relations_data,
            "nodes": node_data,
            "edges": edge_data,
            "statistics": {
                "node_count": self.graph.number_of_nodes(),
                "edge_count": self.graph.number_of_edges(),
            },
        }

    async def import_graph(self, data: Dict):
        entities_data = data.get("entities", {})
        for eid, edata in entities_data.items():
            try:
                entity = Entity(**edata)
                self._entities[eid] = entity
                self.graph.add_node(
                    eid,
                    type=entity.type.value,
                    value=entity.value,
                    confidence=entity.confidence,
                    context=entity.context or "",
                )
            except Exception as exc:
                logger.warning(f"Failed to import entity {eid}: {exc}")
        relations_data = data.get("relations", {})
        for rid, rdata in relations_data.items():
            try:
                relation = Relation(**rdata)
                self._relations[rid] = relation
                self.graph.add_edge(
                    relation.source_entity_id,
                    relation.target_entity_id,
                    id=relation.id,
                    type=relation.type.value,
                    confidence=relation.confidence,
                    evidence=relation.evidence or "",
                )
            except Exception as exc:
                logger.warning(f"Failed to import relation {rid}: {exc}")
        logger.info(
            f"Imported graph: {len(self._entities)} entities, {len(self._relations)} relations"
        )

    async def save(self):
        try:
            data = await self.export_graph(format="json")
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"KnowledgeGraph saved to {self.persist_path}")
        except Exception as exc:
            logger.error(f"Failed to save KnowledgeGraph: {exc}")
            raise

    async def load(self):
        if not self.persist_path.exists():
            logger.debug("No persisted graph file found, starting fresh")
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            await self.import_graph(data)
            logger.info(f"KnowledgeGraph loaded from {self.persist_path}")
        except Exception as exc:
            logger.error(f"Failed to load KnowledgeGraph: {exc}")
            raise

    def _load_sync(self) -> Optional[Dict]:
        if not self.persist_path.exists():
            return None
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _import_data(self, data: Dict):
        entities_data = data.get("entities", {})
        for eid, edata in entities_data.items():
            try:
                entity = Entity(**edata)
                self._entities[eid] = entity
                self.graph.add_node(
                    eid,
                    type=entity.type.value,
                    value=entity.value,
                    confidence=entity.confidence,
                    context=entity.context or "",
                )
            except Exception:
                pass
        relations_data = data.get("relations", {})
        for rid, rdata in relations_data.items():
            try:
                relation = Relation(**rdata)
                self._relations[rid] = relation
                self.graph.add_edge(
                    relation.source_entity_id,
                    relation.target_entity_id,
                    id=relation.id,
                    type=relation.type.value,
                    confidence=relation.confidence,
                    evidence=relation.evidence or "",
                )
            except Exception:
                pass
