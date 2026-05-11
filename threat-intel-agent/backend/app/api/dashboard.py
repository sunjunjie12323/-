from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from sqlalchemy import func, select

from app.core.auth import User, get_current_user
from app.db.database import async_session_factory
from app.db.tables import (
    AnalyzedIntelligenceTable,
    CleanedIntelligenceTable,
    PIRTable,
    RawIntelligenceTable,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_orchestrator(request: Request):
    return request.app.state.orchestrator


def get_knowledge_graph(request: Request):
    return request.app.state.knowledge_graph


def get_blacktalk_engine(request: Request):
    return request.app.state.blacktalk_engine


def get_vector_store(request: Request):
    return request.app.state.vector_store


@router.get("/stats")
async def get_dashboard_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    kg = get_knowledge_graph(request)
    bt = get_blacktalk_engine(request)
    vector_store = get_vector_store(request)
    orchestrator = get_orchestrator(request)

    graph_node_count = 0
    graph_edge_count = 0
    entity_types: Dict[str, int] = {}
    try:
        graph_stats = await kg.get_statistics()
        graph_node_count = graph_stats.get("node_count", 0)
        graph_edge_count = graph_stats.get("edge_count", 0)
        entity_types = graph_stats.get("entity_types", {})
    except Exception:
        pass

    blacktalk_stats: Dict = {"total_terms": 0, "categories": {}}
    try:
        bt_terms = await bt.get_all()
        blacktalk_count = len(bt_terms)
        category_counts: Dict[str, int] = {}
        for t in bt_terms:
            category_counts[t.category] = category_counts.get(t.category, 0) + 1
        blacktalk_stats = {"total_terms": blacktalk_count, "categories": category_counts}
    except Exception:
        pass

    db_raw_count = 0
    db_cleaned_count = 0
    db_analyzed_count = 0
    active_pir_count = 0
    threat_alert_count = 0

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

            result = await session.execute(
                select(func.count()).select_from(PIRTable).where(
                    PIRTable.status.in_(["active", "executing"])
                )
            )
            active_pir_count = result.scalar() or 0

            result = await session.execute(
                select(func.count()).select_from(CleanedIntelligenceTable).where(
                    CleanedIntelligenceTable.threat_level.in_(["critical", "high"])
                )
            )
            high_threats = result.scalar() or 0

            result = await session.execute(
                select(func.count()).select_from(AnalyzedIntelligenceTable).where(
                    AnalyzedIntelligenceTable.threat_level.in_(["critical", "high"])
                )
            )
            high_threats += result.scalar() or 0
            threat_alert_count = high_threats
    except Exception as exc:
        logger.warning(f"Failed to query DB stats: {exc}")

    total_intelligence = db_raw_count + db_cleaned_count + db_analyzed_count

    try:
        vs_intel_count = await vector_store.count("intelligence")
        if vs_intel_count > total_intelligence:
            total_intelligence = vs_intel_count
    except Exception as exc:
        logger.warning(f"Failed to get VectorStore intelligence count: {exc}")

    threat_level_distribution: Dict[str, int] = {
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
                if level in threat_level_distribution:
                    threat_level_distribution[level] = count

            stmt = (
                select(AnalyzedIntelligenceTable.threat_level, func.count())
                .group_by(AnalyzedIntelligenceTable.threat_level)
            )
            result = await session.execute(stmt)
            for level, count in result.all():
                if level in threat_level_distribution:
                    threat_level_distribution[level] += count
    except Exception as exc:
        logger.warning(f"Failed to query threat distribution: {exc}")

    source_type_distribution: Dict[str, int] = {}
    try:
        async with async_session_factory() as session:
            stmt = (
                select(RawIntelligenceTable.source, func.count())
                .group_by(RawIntelligenceTable.source)
            )
            result = await session.execute(stmt)
            for source, count in result.all():
                source_type_distribution[source] = count
    except Exception as exc:
        logger.warning(f"Failed to query source distribution: {exc}")

    recent_intelligence: List[Dict] = []
    try:
        async with async_session_factory() as session:
            stmt = (
                select(RawIntelligenceTable)
                .order_by(RawIntelligenceTable.collected_at.desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                recent_intelligence.append({
                    "id": row.id,
                    "title": f"[{row.source}] {(row.content[:50] + '...') if row.content and len(row.content) > 50 else (row.content or '')}",
                    "content": row.content or "",
                    "source": row.source,
                    "source_type": row.source,
                    "threat_level": "info",
                    "collected_at": row.collected_at.isoformat() if row.collected_at else None,
                    "is_processed": row.status != "raw",
                    "entities": [],
                    "tags": [],
                })
    except Exception as exc:
        logger.warning(f"Failed to query recent intelligence: {exc}")

    agent_statuses: List[Dict] = []
    recent_executions: List[Dict] = []
    try:
        status = orchestrator.get_agent_status()
        if isinstance(status, list):
            agent_statuses = status
        elif isinstance(status, dict):
            for name, info in status.items():
                agent_statuses.append({
                    "name": name,
                    "status": info.get("status", "idle") if isinstance(info, dict) else "idle",
                    "current_task": info.get("current_task") if isinstance(info, dict) else None,
                    "execution_count": info.get("execution_count", 0) if isinstance(info, dict) else 0,
                })

        history = orchestrator.get_execution_history(limit=10)
        for h in history:
            recent_executions.append({
                "id": h.get("execution_id", ""),
                "query": h.get("query", ""),
                "status": h.get("status", ""),
                "started_at": h.get("start_time", ""),
                "completed_at": h.get("end_time", ""),
                "result_summary": h.get("results_summary"),
                "agent_name": h.get("agent_name", ""),
            })
    except Exception as exc:
        logger.warning(f"Failed to get agent status: {exc}")

    organism_stats: Dict = {"total": 0, "alive": 0}
    try:
        organism_engine = request.app.state.intelligence_organism
        all_organisms = list(organism_engine.organisms.values())
        organism_stats = {
            "total": len(all_organisms),
            "alive": sum(1 for o in all_organisms if o.is_alive),
        }
    except Exception:
        pass

    return {
        "total_intelligence": total_intelligence,
        "knowledge_graph": {"node_count": graph_node_count, "edge_count": graph_edge_count},
        "blacktalk": blacktalk_stats,
        "active_pirs": active_pir_count,
        "threat_alerts": threat_alert_count,
        "threat_level_distribution": threat_level_distribution,
        "source_type_distribution": source_type_distribution,
        "recent_intelligence": recent_intelligence,
        "agent_statuses": agent_statuses,
        "recent_executions": recent_executions,
        "organism_stats": organism_stats,
    }


@router.get("/recent")
async def get_recent_intelligence(
    limit: int = Query(10, ge=1, le=50),
    request: Request = None,
    current_user: User = Depends(get_current_user),
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
async def get_threat_distribution(
    request: Request,
    current_user: User = Depends(get_current_user),
):
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
async def get_agent_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
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
