from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.agents.orchestrator import OrchestratorAgent
from app.agents.collector import CollectorAgent
from app.agents.cleaner import CleanerAgent
from app.agents.analyst import AnalystAgent
from app.agents.graph_builder import GraphBuilderAgent
from app.core.llm import LLMService
from app.core.vector_store import VectorStore
from app.core.blacktalk_engine import BlackTalkEngine
from app.core.knowledge_graph import KnowledgeGraph
from app.core.evidence_chain import EvidenceChain
from app.core.pir_engine import PIREngine

router = APIRouter(prefix="/agent", tags=["agent"])


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    context: Optional[Dict] = None


class CollectRequest(BaseModel):
    source: str = Field(default="all")
    keywords: List[str] = Field(default_factory=list)
    max_results: int = Field(default=50, ge=1, le=500)


class BuildGraphRequest(BaseModel):
    analysis_result: Optional[Dict] = None


def get_orchestrator(request: Request) -> OrchestratorAgent:
    return request.app.state.orchestrator


def get_llm(request: Request) -> LLMService:
    return request.app.state.llm


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


@router.post("/query")
async def execute_query(data: QueryRequest, request: Request):
    orchestrator = get_orchestrator(request)
    try:
        result = await orchestrator.execute_query(
            query=data.query,
            context=data.context,
        )
        return result
    except Exception as exc:
        logger.error(f"Agent query execution failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def get_agent_status(request: Request):
    orchestrator = get_orchestrator(request)
    try:
        status = orchestrator.get_agent_status()
        return status
    except Exception as exc:
        logger.error(f"Failed to get agent status: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history")
async def get_execution_history(
    limit: int = Query(20, ge=1, le=100),
    request: Request = None,
):
    orchestrator = get_orchestrator(request)
    try:
        history = orchestrator.get_execution_history(limit=limit)
        return {
            "history": history,
            "total": len(history),
        }
    except Exception as exc:
        logger.error(f"Failed to get execution history: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/collect")
async def trigger_collection(data: CollectRequest, request: Request):
    orchestrator = get_orchestrator(request)
    try:
        task = {
            "type": "collect",
            "source": data.source,
            "keywords": data.keywords,
            "max_results": data.max_results,
        }
        result = await orchestrator.collector.execute(task)
        return result
    except Exception as exc:
        logger.error(f"Collection trigger failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clean/{intel_id}")
async def clean_intelligence(intel_id: str, request: Request):
    orchestrator = get_orchestrator(request)
    vector_store = get_vector_store(request)
    try:
        search_results = await vector_store.search_intelligence(
            query=intel_id, n_results=1
        )
        raw_intel = None
        if search_results:
            for result in search_results:
                if result.get("id") == intel_id:
                    raw_intel = {
                        "id": result["id"],
                        "content": result.get("document", ""),
                        "metadata": result.get("metadata", {}),
                    }
                    break
        if raw_intel is None:
            raw_intel = {"id": intel_id, "content": intel_id}
        task = {
            "type": "clean",
            "raw_intelligence": raw_intel,
            "decode_blacktalk": True,
            "extract_entities": True,
        }
        result = await orchestrator.cleaner.execute(task)
        return result
    except Exception as exc:
        logger.error(f"Clean intelligence failed for {intel_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze/{intel_id}")
async def analyze_intelligence(intel_id: str, request: Request):
    orchestrator = get_orchestrator(request)
    vector_store = get_vector_store(request)
    try:
        search_results = await vector_store.search_intelligence(
            query=intel_id, n_results=5
        )
        cleaned_intel = None
        for result in search_results:
            metadata = result.get("metadata", {})
            if metadata.get("status") == "cleaned" and result.get("id") == intel_id:
                cleaned_intel = {
                    "id": result["id"],
                    "content": result.get("document", ""),
                    "metadata": metadata,
                }
                break
        if cleaned_intel is None:
            if search_results:
                best = search_results[0]
                cleaned_intel = {
                    "id": best.get("id", intel_id),
                    "content": best.get("document", ""),
                    "metadata": best.get("metadata", {}),
                }
            else:
                cleaned_intel = {"id": intel_id, "content": intel_id}
        task = {
            "type": "analyze",
            "cleaned_intelligence": cleaned_intel,
        }
        result = await orchestrator.analyst.execute(task)
        return result
    except Exception as exc:
        logger.error(f"Analyze intelligence failed for {intel_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/build-graph")
async def build_graph(data: BuildGraphRequest, request: Request):
    orchestrator = get_orchestrator(request)
    try:
        analysis_result = data.analysis_result or {}
        if not analysis_result:
            stats = await orchestrator.knowledge_graph.get_statistics()
            if stats["node_count"] > 0:
                all_entities = list(orchestrator.knowledge_graph._entities.values())
                recent_entities = sorted(
                    all_entities, key=lambda e: e.last_seen, reverse=True
                )[:10]
                analysis_result = {
                    "entity_details": [
                        {"type": e.type.value, "value": e.value, "context": e.context or ""}
                        for e in recent_entities
                    ],
                    "confidence_score": 0.5,
                }
        task = {
            "type": "build",
            "analysis_result": analysis_result,
        }
        result = await orchestrator.graph_builder.execute(task)
        return result
    except Exception as exc:
        logger.error(f"Build graph failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
