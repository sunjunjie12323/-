import asyncio
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.core.auth import User, get_current_user, require_role, Role

router = APIRouter(prefix="/agent", tags=["agent"])


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    context: Optional[Dict] = None
    max_iterations: int = Field(default=3, ge=1, le=10)


class TaskResponse(BaseModel):
    task_id: str
    status: str = "pending"
    message: str = ""


def get_orchestrator(request: Request):
    return request.app.state.orchestrator


@router.post("/query")
async def submit_query(
    data: QueryRequest,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    from app.core.task_queue import task_queue
    try:
        task_id = await task_queue.submit(
            task_type="query",
            params={"query": data.query, "context": data.context},
        )
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "查询已提交",
        }
    except Exception as exc:
        logger.error(f"Failed to submit query: {exc}")
        raise HTTPException(status_code=500, detail=f"查询提交失败: {str(exc)}")


@router.get("/status")
async def get_agent_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    try:
        status = orchestrator.get_agent_status()
        return {"agents": status}
    except Exception as exc:
        logger.error(f"Failed to get agent status: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history")
async def get_execution_history(
    limit: int = 20,
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    try:
        history = orchestrator.get_execution_history(limit=limit)
        return {
            "items": history,
            "total": len(history),
        }
    except Exception as exc:
        logger.error(f"Failed to get execution history: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/execution/{execution_id}")
async def get_execution_detail(
    execution_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator(request)
    try:
        history = orchestrator.get_execution_history(limit=100)
        for h in history:
            if h.get("execution_id") == execution_id:
                return h
        raise HTTPException(status_code=404, detail="执行记录未找到")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get execution detail: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/collect")
async def trigger_collection(
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    from app.core.task_queue import task_queue
    try:
        task_id = await task_queue.submit(
            task_type="collect",
            params={"source": "all", "keywords": [], "max_results": 10},
        )
        return {"task_id": task_id, "status": "pending", "message": "情报收集任务已提交"}
    except Exception as exc:
        logger.error(f"Failed to trigger collection: {exc}")
        raise HTTPException(status_code=500, detail=f"情报收集任务提交失败: {str(exc)}")


@router.post("/analyze")
async def trigger_analysis(
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    from app.core.task_queue import task_queue
    try:
        task_id = await task_queue.submit(
            task_type="analyze",
            params={"cleaned_intelligence": {}},
        )
        return {"task_id": task_id, "status": "pending", "message": "情报分析任务已提交"}
    except Exception as exc:
        logger.error(f"Failed to trigger analysis: {exc}")
        raise HTTPException(status_code=500, detail=f"情报分析任务提交失败: {str(exc)}")


def register_agent_handlers():
    from app.core.task_queue import task_queue

    async def _handle_query(task):
        from app.main import app
        orchestrator = app.state.orchestrator
        try:
            result = await asyncio.wait_for(
                orchestrator.execute_query(
                    query=task.params.get("query", ""),
                    context=task.params.get("context"),
                ),
                timeout=120.0,
            )
            return result
        except asyncio.TimeoutError:
            return {"status": "error", "error": "查询超时(120s)", "partial_results": None}

    async def _handle_collect(task):
        from app.main import app
        orchestrator = app.state.orchestrator
        return await orchestrator.collector.execute({
            "type": "collect",
            "source": task.params.get("source", "all"),
            "keywords": task.params.get("keywords", []),
            "max_results": task.params.get("max_results", 10),
        })

    async def _handle_clean(task):
        from app.main import app
        orchestrator = app.state.orchestrator
        return await orchestrator.cleaner.execute({
            "type": "clean",
            "raw_intelligence": task.params.get("raw_intelligence"),
        })

    async def _handle_analyze(task):
        from app.main import app
        orchestrator = app.state.orchestrator
        return await orchestrator.analyst.execute({
            "type": "analyze",
            "cleaned_intelligence": task.params.get("cleaned_intelligence"),
        })

    async def _handle_build_graph(task):
        from app.main import app
        orchestrator = app.state.orchestrator
        return await orchestrator.graph_builder.execute({
            "type": "build",
            "analysis_result": task.params.get("analysis_result"),
        })

    task_queue.register_handler("query", _handle_query)
    task_queue.register_handler("collect", _handle_collect)
    task_queue.register_handler("clean", _handle_clean)
    task_queue.register_handler("analyze", _handle_analyze)
    task_queue.register_handler("build_graph", _handle_build_graph)
