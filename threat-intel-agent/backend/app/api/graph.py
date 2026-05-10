from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.core.auth import User, get_current_user, require_role, Role
from app.core.knowledge_graph import KnowledgeGraph
from app.models.entity import Entity, EntityType, Relation, RelationType

router = APIRouter(prefix="/graph", tags=["graph"])


class EntityCreate(BaseModel):
    type: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    context: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RelationCreate(BaseModel):
    source_entity_id: str = Field(..., min_length=1)
    target_entity_id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: Optional[str] = None


class PathRequest(BaseModel):
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    max_depth: int = Field(default=5, ge=1, le=10)


class CommunityRequest(BaseModel):
    algorithm: str = Field(default="louvain")
    min_size: int = Field(default=2, ge=2)


def get_knowledge_graph(request: Request) -> KnowledgeGraph:
    return request.app.state.knowledge_graph


@router.get("/stats")
async def graph_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        stats = await kg.get_statistics()
        return stats
    except Exception as exc:
        logger.error(f"Failed to get graph stats: {exc}")
        return {"node_count": 0, "edge_count": 0, "entity_types": {}}


@router.get("/entities")
async def list_entities(
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        if search:
            entities = await kg.search_entities(
                query=search,
                entity_type=entity_type,
                limit=limit + offset,
            )
            total = len(entities)
            paginated = entities[offset: offset + limit]
        else:
            all_entities = list(kg._entities.values())
            if entity_type:
                all_entities = [e for e in all_entities if e.type.value == entity_type]
            all_entities.sort(key=lambda e: e.last_seen, reverse=True)
            total = len(all_entities)
            paginated = all_entities[offset: offset + limit]
        return {
            "items": [e.model_dump() for e in paginated],
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    except Exception as exc:
        logger.error(f"Failed to list graph entities: {exc}")
        return {"items": [], "total": 0, "offset": offset, "limit": limit}


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        entity = await kg.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="实体未在知识图谱中找到")
        relations = await kg.get_entity_relations(entity_id)
        return {
            "entity": entity.model_dump(),
            "relations": [r.model_dump() for r in relations],
            "relation_count": len(relations),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get entity {entity_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/relations")
async def list_relations(
    relation_type: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        all_relations = list(kg._relations.values())
        if relation_type:
            all_relations = [r for r in all_relations if r.type.value == relation_type]
        all_relations.sort(key=lambda r: r.last_seen, reverse=True)
        total = len(all_relations)
        paginated = all_relations[offset: offset + limit]
        return {
            "items": [r.model_dump() for r in paginated],
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    except Exception as exc:
        logger.error(f"Failed to list relations: {exc}")
        return {"items": [], "total": 0, "offset": offset, "limit": limit}


@router.post("/entities", status_code=201)
async def add_entity(
    data: EntityCreate,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    kg = get_knowledge_graph(request)
    try:
        try:
            entity_type = EntityType(data.type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效实体类型: {data.type}. "
                       f"有效类型: {[t.value for t in EntityType]}",
            )
        entity = Entity(
            type=entity_type,
            value=data.value,
            context=data.context,
            confidence=data.confidence,
        )
        entity_id = await kg.add_entity(entity)
        await kg.save()
        return {"id": entity_id, **entity.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to add entity to graph: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/relations", status_code=201)
async def add_relation(
    data: RelationCreate,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    kg = get_knowledge_graph(request)
    try:
        try:
            rel_type = RelationType(data.type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效关系类型: {data.type}. "
                       f"有效类型: {[t.value for t in RelationType]}",
            )
        source = await kg.get_entity(data.source_entity_id)
        if source is None:
            raise HTTPException(
                status_code=400,
                detail=f"源实体 {data.source_entity_id} 未找到",
            )
        target = await kg.get_entity(data.target_entity_id)
        if target is None:
            raise HTTPException(
                status_code=400,
                detail=f"目标实体 {data.target_entity_id} 未找到",
            )
        relation = Relation(
            source_entity_id=data.source_entity_id,
            target_entity_id=data.target_entity_id,
            type=rel_type,
            confidence=data.confidence,
            evidence=data.evidence,
        )
        relation_id = await kg.add_relation(relation)
        await kg.save()
        return {"id": relation_id, **relation.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to add relation to graph: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/path")
async def find_path(
    data: PathRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        source = await kg.get_entity(data.source_id)
        if source is None:
            raise HTTPException(
                status_code=404,
                detail=f"源实体 {data.source_id} 未找到",
            )
        target = await kg.get_entity(data.target_id)
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"目标实体 {data.target_id} 未找到",
            )
        paths = await kg.find_path(
            data.source_id, data.target_id, max_depth=data.max_depth
        )
        if not paths:
            return {
                "source_id": data.source_id,
                "target_id": data.target_id,
                "paths": [],
                "path_count": 0,
                "message": "未找到连接路径，两个实体可能不在同一连通分量中",
            }
        enriched_paths = []
        for path in paths:
            enriched_nodes = []
            for node_id in path:
                entity = await kg.get_entity(node_id)
                if entity:
                    enriched_nodes.append({
                        "id": entity.id,
                        "type": entity.type.value,
                        "value": entity.value,
                    })
                else:
                    enriched_nodes.append({"id": node_id})
            enriched_paths.append(enriched_nodes)
        return {
            "source_id": data.source_id,
            "target_id": data.target_id,
            "paths": enriched_paths,
            "path_count": len(enriched_paths),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to find path: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/communities")
async def find_communities(
    data: CommunityRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        if len(kg._entities) == 0:
            return {
                "algorithm": data.algorithm,
                "communities": [],
                "community_count": 0,
            }
        communities = await kg.find_communities(algorithm=data.algorithm)
        result = []
        for community in communities:
            if len(community) < data.min_size:
                continue
            members = []
            for member_id in community:
                entity = await kg.get_entity(member_id)
                if entity:
                    members.append({
                        "id": entity.id,
                        "type": entity.type.value,
                        "value": entity.value,
                    })
            result.append({
                "member_count": len(members),
                "members": members,
            })
        return {
            "algorithm": data.algorithm,
            "communities": result,
            "community_count": len(result),
        }
    except Exception as exc:
        logger.error(f"Failed to find communities: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/subgraph/{entity_id}")
async def get_subgraph(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        entity = await kg.get_entity(entity_id)
        if entity is None:
            raise HTTPException(
                status_code=404,
                detail=f"实体 {entity_id} 未找到",
            )
        subgraph = await kg.get_subgraph([entity_id], depth=depth)
        return subgraph
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get subgraph for {entity_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/export")
async def export_graph(
    format: str = Query("json"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        data = await kg.export_graph(format=format)
        return data
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Failed to export graph: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/data")
async def get_graph_data(
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    depth: int = Query(1, ge=1, le=3),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    try:
        nodes = []
        edges = []

        all_entities = list(kg._entities.values())
        if entity_type:
            all_entities = [e for e in all_entities if e.type.value == entity_type]
        if search:
            search_lower = search.lower()
            all_entities = [e for e in all_entities if search_lower in e.value.lower()]

        for entity in all_entities:
            nodes.append({
                "id": entity.id,
                "label": entity.value,
                "entity_type": entity.type.value,
                "properties": {},
                "confidence": entity.confidence,
            })

        entity_ids = {e.id for e in all_entities}
        for relation in kg._relations.values():
            if relation.source_entity_id in entity_ids and relation.target_entity_id in entity_ids:
                edges.append({
                    "id": relation.id,
                    "source": relation.source_entity_id,
                    "target": relation.target_entity_id,
                    "relation_type": relation.type.value,
                    "properties": {},
                    "confidence": relation.confidence,
                })

        return {"nodes": nodes, "edges": edges}
    except Exception as exc:
        logger.error(f"Failed to get graph data: {exc}")
        return {"nodes": [], "edges": []}
