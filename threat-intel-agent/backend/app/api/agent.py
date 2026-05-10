from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.agents.orchestrator import OrchestratorAgent
from app.agents.collector import CollectorAgent
from app.agents.cleaner import CleanerAgent
from app.agents.analyst import AnalystAgent
from app.agents.graph_builder import GraphBuilderAgent
from app.core.auth import User, get_current_user
from app.core.llm import LLMService
from app.core.vector_store import VectorStore
from app.core.blacktalk_engine import BlackTalkEngine
from app.core.knowledge_graph import KnowledgeGraph
from app.core.evidence_chain import EvidenceChain
from app.core.pir_engine import PIREngine
from app.core.task_queue import Task, task_queue

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


async def _handle_query(task: Task) -> Dict:
    orchestrator = task.params.get("_orchestrator")
    query = task.params.get("query", "")
    context = task.params.get("context")
    task_queue.update_progress(task.id, 10.0)
    result = await orchestrator.execute_query(query=query, context=context)
    task_queue.update_progress(task.id, 100.0)
    return result


async def _handle_collect(task: Task) -> Dict:
    orchestrator = task.params.get("_orchestrator")
    source = task.params.get("source", "all")
    keywords = task.params.get("keywords", [])
    max_results = task.params.get("max_results", 50)
    task_queue.update_progress(task.id, 10.0)
    collect_task = {
        "type": "collect",
        "source": source,
        "keywords": keywords,
        "max_results": max_results,
    }
    result = await orchestrator.collector.execute(collect_task)
    task_queue.update_progress(task.id, 100.0)
    return result


async def _handle_clean(task: Task) -> Dict:
    orchestrator = task.params.get("_orchestrator")
    vector_store = task.params.get("_vector_store")
    intel_id = task.params.get("intel_id", "")
    task_queue.update_progress(task.id, 10.0)
    search_results = await vector_store.search_intelligence(query=intel_id, n_results=1)
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
    task_queue.update_progress(task.id, 30.0)
    clean_task = {
        "type": "clean",
        "raw_intelligence": raw_intel,
        "decode_blacktalk": True,
        "extract_entities": True,
    }
    result = await orchestrator.cleaner.execute(clean_task)
    task_queue.update_progress(task.id, 100.0)
    return result


async def _handle_analyze(task: Task) -> Dict:
    orchestrator = task.params.get("_orchestrator")
    vector_store = task.params.get("_vector_store")
    intel_id = task.params.get("intel_id", "")
    task_queue.update_progress(task.id, 10.0)
    search_results = await vector_store.search_intelligence(query=intel_id, n_results=5)
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
    task_queue.update_progress(task.id, 30.0)
    analyze_task = {
        "type": "analyze",
        "cleaned_intelligence": cleaned_intel,
    }
    result = await orchestrator.analyst.execute(analyze_task)
    task_queue.update_progress(task.id, 100.0)
    return result


async def _handle_build_graph(task: Task) -> Dict:
    orchestrator = task.params.get("_orchestrator")
    analysis_result = task.params.get("analysis_result") or {}
    task_queue.update_progress(task.id, 10.0)
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
    task_queue.update_progress(task.id, 30.0)
    build_task = {
        "type": "build",
        "analysis_result": analysis_result,
    }
    result = await orchestrator.graph_builder.execute(build_task)
    task_queue.update_progress(task.id, 100.0)
    return result


def register_agent_handlers() -> None:
    task_queue.register_handler("query", _handle_query)
    task_queue.register_handler("collect", _handle_collect)
    task_queue.register_handler("clean", _handle_clean)
    task_queue.register_handler("analyze", _handle_analyze)
    task_queue.register_handler("build_graph", _handle_build_graph)


@router.post("/query")
async def execute_query(
    data: QueryRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    try:
        task_id = await task_queue.submit("query", {
            "query": data.query,
            "context": data.context,
            "_orchestrator": orchestrator,
        })
        return {"task_id": task_id, "status": "pending"}
    except ValueError as exc:
        logger.error(f"Agent query task submission failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def get_agent_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
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
    current_user: User = Depends(get_current_user),
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
async def trigger_collection(
    data: CollectRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    try:
        task_id = await task_queue.submit("collect", {
            "source": data.source,
            "keywords": data.keywords,
            "max_results": data.max_results,
            "_orchestrator": orchestrator,
        })
        return {"task_id": task_id, "status": "pending"}
    except ValueError as exc:
        logger.error(f"Collection task submission failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clean/{intel_id}")
async def clean_intelligence(
    intel_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    vector_store = get_vector_store(request)
    try:
        task_id = await task_queue.submit("clean", {
            "intel_id": intel_id,
            "_orchestrator": orchestrator,
            "_vector_store": vector_store,
        })
        return {"task_id": task_id, "status": "pending"}
    except ValueError as exc:
        logger.error(f"Clean task submission failed for {intel_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze/{intel_id}")
async def analyze_intelligence(
    intel_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    vector_store = get_vector_store(request)
    try:
        task_id = await task_queue.submit("analyze", {
            "intel_id": intel_id,
            "_orchestrator": orchestrator,
            "_vector_store": vector_store,
        })
        return {"task_id": task_id, "status": "pending"}
    except ValueError as exc:
        logger.error(f"Analyze task submission failed for {intel_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/build-graph")
async def build_graph(
    data: BuildGraphRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    try:
        task_id = await task_queue.submit("build_graph", {
            "analysis_result": data.analysis_result,
            "_orchestrator": orchestrator,
        })
        return {"task_id": task_id, "status": "pending"}
    except ValueError as exc:
        logger.error(f"Build graph task submission failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
