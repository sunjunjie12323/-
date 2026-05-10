from collections import Counter
from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
from sqlalchemy import func, select

from app.agents.orchestrator import OrchestratorAgent
from app.core.blacktalk_engine import BlackTalkEngine
from app.core.knowledge_graph import KnowledgeGraph
from app.core.vector_store import VectorStore
from app.db.database import async_session_factory
from app.db.tables import (
    AnalyzedIntelligenceTable,
    CleanedIntelligenceTable,
    RawIntelligenceTable,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_orchestrator(request: Request) -> OrchestratorAgent:
    return request.app.state.orchestrator


def get_knowledge_graph(request: Request) -> KnowledgeGraph:
    return request.app.state.knowledge_graph


def get_blacktalk_engine(request: Request) -> BlackTalkEngine:
    return request.app.state.blacktalk_engine


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


@router.get("/stats")
async def get_dashboard_stats(request: Request):
    kg = get_knowledge_graph(request)
    bt = get_blacktalk_engine(request)
    vector_store = get_vector_store(request)
    orchestrator = get_orchestrator(request)

    try:
        graph_stats = await kg.get_statistics()
    except Exception:
        graph_stats = {"node_count": 0, "edge_count": 0}

    try:
        bt_terms = await bt.get_all()
        blacktalk_count = len(bt_terms)
    except Exception:
        blacktalk_count = 0

    try:
        intel_count = await vector_store.count("intelligence")
        entity_count = await vector_store.count("entities")
    except Exception:
        intel_count = 0
        entity_count = 0

    try:
        history = orchestrator.get_execution_history(limit=100)
        total_executions = len(history)
        successful = sum(1 for h in history if h.get("status") == "success")
        failed = sum(1 for h in history if h.get("status") == "failed")
    except Exception:
        total_executions = 0
        successful = 0
        failed = 0

    db_raw_count = 0
    db_cleaned_count = 0
    db_analyzed_count = 0
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(RawIntelligenceTable)
            )
            db_raw_count = result.scalar() or 0

            result = await session.execute(
                select(func.count()).select_from(CleanedIntelligenceTable)
            )
            db_cleaned_count = result.scalar() or 0

            result = await session.execute(
                select(func.count()).select_from(AnalyzedIntelligenceTable)
            )
            db_analyzed_count = result.scalar() or 0
    except Exception as exc:
        logger.warning(f"Failed to query DB stats: {exc}")

    return {
        "intelligence": {
            "raw": db_raw_count,
            "cleaned": db_cleaned_count,
            "analyzed": db_analyzed_count,
            "total": db_raw_count + db_cleaned_count + db_analyzed_count,
        },
        "knowledge_graph": {
            "nodes": graph_stats.get("node_count", 0),
            "edges": graph_stats.get("edge_count", 0),
            "entity_types": graph_stats.get("entity_types", {}),
        },
        "blacktalk": {
            "total_terms": blacktalk_count,
        },
        "vector_store": {
            "intelligence_vectors": intel_count,
            "entity_vectors": entity_count,
        },
        "agents": {
            "total_executions": total_executions,
            "successful": successful,
            "failed": failed,
        },
    }


@router.get("/recent")
async def get_recent_intelligence(
    limit: int = Query(10, ge=1, le=50),
    request: Request = None,
):
    items = []
    try:
        async with async_session_factory() as session:
            stmt = (
                select(RawIntelligenceTable)
                .order_by(RawIntelligenceTable.collected_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                items.append({
                    "id": row.id,
                    "type": "raw",
                    "source": row.source,
                    "content": (row.content[:200] + "...") if row.content and len(row.content) > 200 else row.content,
                    "threat_level": None,
                    "collected_at": row.collected_at.isoformat() if row.collected_at else None,
                })

            stmt = (
                select(CleanedIntelligenceTable)
                .order_by(CleanedIntelligenceTable.cleaned_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                items.append({
                    "id": row.id,
                    "type": "cleaned",
                    "source": None,
                    "content": (row.content[:200] + "...") if row.content and len(row.content) > 200 else row.content,
                    "threat_level": row.threat_level,
                    "collected_at": row.cleaned_at.isoformat() if row.cleaned_at else None,
                })

            stmt = (
                select(AnalyzedIntelligenceTable)
                .order_by(AnalyzedIntelligenceTable.analyzed_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                items.append({
                    "id": row.id,
                    "type": "analyzed",
                    "source": None,
                    "content": (row.analysis_summary[:200] + "...") if row.analysis_summary and len(row.analysis_summary) > 200 else row.analysis_summary,
                    "threat_level": row.threat_level,
                    "collected_at": row.analyzed_at.isoformat() if row.analyzed_at else None,
                })
    except Exception as exc:
        logger.warning(f"Failed to query recent intelligence from DB: {exc}")

    items.sort(key=lambda x: x.get("collected_at") or "", reverse=True)
    return {"items": items[:limit], "total": len(items)}


@router.get("/threat-distribution")
async def get_threat_distribution(request: Request):
    distribution: Dict[str, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }
    try:
        async with async_session_factory() as session:
            stmt = (
                select(CleanedIntelligenceTable.threat_level, func.count())
                .group_by(CleanedIntelligenceTable.threat_level)
            )
            result = await session.execute(stmt)
            for level, count in result.all():
                if level in distribution:
                    distribution[level] = count

            stmt = (
                select(AnalyzedIntelligenceTable.threat_level, func.count())
                .group_by(AnalyzedIntelligenceTable.threat_level)
            )
            result = await session.execute(stmt)
            for level, count in result.all():
                if level in distribution:
                    distribution[level] += count
    except Exception as exc:
        logger.warning(f"Failed to query threat distribution: {exc}")

    try:
        kg = get_knowledge_graph(request)
        graph_stats = await kg.get_statistics()
        entity_types = graph_stats.get("entity_types", {})
    except Exception:
        entity_types = {}

    return {
        "threat_levels": distribution,
        "entity_types": entity_types,
    }


@router.get("/agent-status")
async def get_agent_status(request: Request):
    orchestrator = get_orchestrator(request)
    try:
        status = orchestrator.get_agent_status()
        history = orchestrator.get_execution_history(limit=10)

        recent_executions = []
        for h in history:
            recent_executions.append({
                "execution_id": h.get("execution_id", ""),
                "query": h.get("query", ""),
                "status": h.get("status", ""),
                "duration_seconds": h.get("duration_seconds", 0),
                "start_time": h.get("start_time", ""),
                "end_time": h.get("end_time", ""),
                "steps": h.get("steps", 0),
                "results_summary": h.get("results_summary"),
                "error": h.get("error"),
            })

        return {
            "agents": status,
            "recent_executions": recent_executions,
        }
    except Exception as exc:
        logger.error(f"Failed to get agent status: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
