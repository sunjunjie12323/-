from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User, get_current_user, require_role, Role
from app.db.crud import IntelligenceCRUD
from app.db.database import async_session_factory, get_db
from app.db.tables import (
    AnalyzedIntelligenceTable,
    CleanedIntelligenceTable,
    RawIntelligenceTable,
)
from app.models.intelligence import (
    AnalyzedIntelligence,
    CleanedIntelligence,
    IntelligenceSource,
    IntelligenceStatus,
    RawIntelligence,
    ThreatLevel,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class RawIntelligenceCreate(BaseModel):
    source: IntelligenceSource = IntelligenceSource.OTHER
    source_url: Optional[str] = None
    content: str = Field(..., min_length=1)
    raw_content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StatusUpdateRequest(BaseModel):
    status: IntelligenceStatus


class IntelligenceStatsResponse(BaseModel):
    by_source: Dict[str, int] = {}
    by_threat_level: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    total: int = 0


@router.get("")
async def list_intelligence(
    source: Optional[str] = None,
    threat_level: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items: List[Dict[str, Any]] = []
    total = 0

    try:
        conditions_raw = []
        conditions_cleaned = []
        conditions_analyzed = []

        if source:
            conditions_raw.append(RawIntelligenceTable.source == source)

        if status:
            conditions_raw.append(RawIntelligenceTable.status == status)
            if status in ("cleaned", "analyzed"):
                conditions_cleaned.append(RawIntelligenceTable.status == status)

        if threat_level:
            conditions_cleaned.append(CleanedIntelligenceTable.threat_level == threat_level)
            conditions_analyzed.append(AnalyzedIntelligenceTable.threat_level == threat_level)

        if search:
            search_pattern = f"%{search}%"
            conditions_raw.append(RawIntelligenceTable.content.ilike(search_pattern))
            conditions_cleaned.append(CleanedIntelligenceTable.content.ilike(search_pattern))
            conditions_analyzed.append(AnalyzedIntelligenceTable.analysis_summary.ilike(search_pattern))

        raw_stmt = select(RawIntelligenceTable)
        raw_count_stmt = select(func.count()).select_from(RawIntelligenceTable)
        for cond in conditions_raw:
            raw_stmt = raw_stmt.where(cond)
            raw_count_stmt = raw_count_stmt.where(cond)

        raw_total_result = await db.execute(raw_count_stmt)
        raw_total = raw_total_result.scalar() or 0

        raw_stmt = raw_stmt.order_by(RawIntelligenceTable.collected_at.desc()).offset(offset).limit(limit)
        raw_result = await db.execute(raw_stmt)
        raw_rows = raw_result.scalars().all()

        for row in raw_rows:
            items.append({
                "id": row.id,
                "source": row.source,
                "content": (row.content[:300] + "...") if row.content and len(row.content) > 300 else (row.content or ""),
                "threat_level": None,
                "status": row.status,
                "collected_at": row.collected_at.isoformat() if row.collected_at else None,
                "entities_count": 0,
                "blacktalk_count": 0,
                "type": "raw",
            })

        remaining = limit - len(raw_rows)
        cleaned_offset = max(0, offset - raw_total) if offset > raw_total else 0

        if remaining > 0 or threat_level or (status and status in ("cleaned", "analyzed")):
            cleaned_stmt = select(CleanedIntelligenceTable)
            cleaned_count_stmt = select(func.count()).select_from(CleanedIntelligenceTable)
            for cond in conditions_cleaned:
                cleaned_stmt = cleaned_stmt.where(cond)
                cleaned_count_stmt = cleaned_count_stmt.where(cond)

            cleaned_total_result = await db.execute(cleaned_count_stmt)
            cleaned_total = cleaned_total_result.scalar() or 0

            if not threat_level and not (status and status in ("cleaned", "analyzed")):
                cleaned_stmt = cleaned_stmt.order_by(CleanedIntelligenceTable.cleaned_at.desc()).offset(cleaned_offset).limit(remaining)
            else:
                cleaned_stmt = cleaned_stmt.order_by(CleanedIntelligenceTable.cleaned_at.desc()).offset(offset).limit(limit)

            cleaned_result = await db.execute(cleaned_stmt)
            cleaned_rows = cleaned_result.scalars().all()

            for row in cleaned_rows:
                import json
                entities = []
                try:
                    entities = json.loads(row.entities_json) if row.entities_json else []
                except (json.JSONDecodeError, TypeError):
                    entities = []
                blacktalk_terms = {}
                try:
                    blacktalk_terms = json.loads(row.blacktalk_terms_json) if row.blacktalk_terms_json else {}
                except (json.JSONDecodeError, TypeError):
                    blacktalk_terms = {}

                items.append({
                    "id": row.id,
                    "source": None,
                    "content": (row.content[:300] + "...") if row.content and len(row.content) > 300 else (row.content or ""),
                    "threat_level": row.threat_level,
                    "status": "cleaned",
                    "collected_at": row.cleaned_at.isoformat() if row.cleaned_at else None,
                    "entities_count": len(entities) if isinstance(entities, list) else 0,
                    "blacktalk_count": len(blacktalk_terms) if isinstance(blacktalk_terms, dict) else 0,
                    "type": "cleaned",
                })

            analyzed_stmt = select(AnalyzedIntelligenceTable)
            analyzed_count_stmt = select(func.count()).select_from(AnalyzedIntelligenceTable)
            for cond in conditions_analyzed:
                analyzed_stmt = analyzed_stmt.where(cond)
                analyzed_count_stmt = analyzed_count_stmt.where(cond)

            analyzed_total_result = await db.execute(analyzed_count_stmt)
            analyzed_total = analyzed_total_result.scalar() or 0

            analyzed_stmt = analyzed_stmt.order_by(AnalyzedIntelligenceTable.analyzed_at.desc()).offset(offset).limit(limit)
            analyzed_result = await db.execute(analyzed_stmt)
            analyzed_rows = analyzed_result.scalars().all()

            for row in analyzed_rows:
                items.append({
                    "id": row.id,
                    "source": None,
                    "content": (row.analysis_summary[:300] + "...") if row.analysis_summary and len(row.analysis_summary) > 300 else (row.analysis_summary or ""),
                    "threat_level": row.threat_level,
                    "status": "analyzed",
                    "collected_at": row.analyzed_at.isoformat() if row.analyzed_at else None,
                    "entities_count": 0,
                    "blacktalk_count": 0,
                    "type": "analyzed",
                })

            total = raw_total + cleaned_total + analyzed_total
        else:
            total = raw_total

        if threat_level:
            items = [i for i in items if i.get("threat_level") == threat_level]
            total = len(items)

        items.sort(key=lambda x: x.get("collected_at") or "", reverse=True)
        items = items[:limit]

    except Exception as exc:
        logger.warning(f"Failed to list unified intelligence: {exc}")
        total = 0

    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/stats")
async def get_intelligence_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    by_source: Dict[str, int] = {}
    by_threat_level: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    total = 0

    try:
        result = await db.execute(
            select(RawIntelligenceTable.source, func.count()).group_by(RawIntelligenceTable.source)
        )
        for source, count in result.all():
            by_source[source] = count
            total += count

        result = await db.execute(
            select(RawIntelligenceTable.status, func.count()).group_by(RawIntelligenceTable.status)
        )
        for status, count in result.all():
            by_status[status] = count

        result = await db.execute(
            select(CleanedIntelligenceTable.threat_level, func.count()).group_by(CleanedIntelligenceTable.threat_level)
        )
        for level, count in result.all():
            by_threat_level[level] = by_threat_level.get(level, 0) + count

        result = await db.execute(
            select(AnalyzedIntelligenceTable.threat_level, func.count()).group_by(AnalyzedIntelligenceTable.threat_level)
        )
        for level, count in result.all():
            by_threat_level[level] = by_threat_level.get(level, 0) + count

        cleaned_count_result = await db.execute(select(func.count()).select_from(CleanedIntelligenceTable))
        analyzed_count_result = await db.execute(select(func.count()).select_from(AnalyzedIntelligenceTable))
        total += (cleaned_count_result.scalar() or 0) + (analyzed_count_result.scalar() or 0)

    except Exception as exc:
        logger.warning(f"Failed to get intelligence stats: {exc}")

    return {
        "by_source": by_source,
        "by_threat_level": by_threat_level,
        "by_status": by_status,
        "total": total,
    }


@router.get("/{intel_id}")
async def get_intelligence_detail(
    intel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = IntelligenceCRUD(db)

    raw = await crud.get_raw(intel_id)
    if raw is not None:
        return {"type": "raw", "data": raw.model_dump()}

    cleaned = await crud.get_cleaned(intel_id)
    if cleaned is not None:
        return {"type": "cleaned", "data": cleaned.model_dump()}

    analyzed = await crud.get_analyzed(intel_id)
    if analyzed is not None:
        return {"type": "analyzed", "data": analyzed.model_dump()}

    raise HTTPException(status_code=404, detail="Intelligence not found")


@router.post("", status_code=201)
async def create_intelligence(
    data: RawIntelligenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    raw = RawIntelligence(
        source=data.source,
        source_url=data.source_url,
        content=data.content,
        raw_content=data.raw_content,
        metadata=data.metadata,
    )
    result = await crud.create_raw(raw)
    await db.commit()
    return result.model_dump()


@router.patch("/{intel_id}/status")
async def update_intelligence_status(
    intel_id: str,
    data: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    result = await crud.update_status(intel_id, data.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Intelligence not found")
    await db.commit()
    return result.model_dump()


@router.delete("/{intel_id}", status_code=204)
async def delete_intelligence(
    intel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    deleted = await crud.delete_raw(intel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Intelligence not found")
    await db.commit()


@router.post("/raw", response_model=RawIntelligence, status_code=201)
async def create_raw_intelligence(
    data: RawIntelligence,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    result = await crud.create_raw(data)
    await db.commit()
    return result


@router.get("/raw", response_model=dict)
async def list_raw_intelligence(
    source: IntelligenceSource | None = None,
    status: IntelligenceStatus | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = IntelligenceCRUD(db)
    items, total = await crud.list_raw(source=source, status=status, offset=offset, limit=limit)
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/raw/{raw_id}", response_model=RawIntelligence)
async def get_raw_intelligence(
    raw_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = IntelligenceCRUD(db)
    result = await crud.get_raw(raw_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Raw intelligence not found")
    return result


@router.patch("/raw/{raw_id}/status", response_model=RawIntelligence)
async def update_raw_status(
    raw_id: str,
    status: IntelligenceStatus,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    result = await crud.update_status(raw_id, status)
    if result is None:
        raise HTTPException(status_code=404, detail="Raw intelligence not found")
    await db.commit()
    return result


@router.delete("/raw/{raw_id}", status_code=204)
async def delete_raw_intelligence(
    raw_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    deleted = await crud.delete_raw(raw_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Raw intelligence not found")
    await db.commit()


@router.post("/cleaned", response_model=CleanedIntelligence, status_code=201)
async def create_cleaned_intelligence(
    data: CleanedIntelligence,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    raw = await crud.get_raw(data.raw_id)
    if raw is None:
        raise HTTPException(status_code=400, detail="Referenced raw intelligence not found")
    result = await crud.create_cleaned(data)
    await db.commit()
    return result


@router.get("/cleaned", response_model=dict)
async def list_cleaned_intelligence(
    threat_level: ThreatLevel | None = None,
    raw_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = IntelligenceCRUD(db)
    items, total = await crud.list_cleaned(
        threat_level=threat_level, raw_id=raw_id, offset=offset, limit=limit
    )
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/cleaned/{cleaned_id}", response_model=CleanedIntelligence)
async def get_cleaned_intelligence(
    cleaned_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = IntelligenceCRUD(db)
    result = await crud.get_cleaned(cleaned_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Cleaned intelligence not found")
    return result


@router.post("/analyzed", response_model=AnalyzedIntelligence, status_code=201)
async def create_analyzed_intelligence(
    data: AnalyzedIntelligence,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = IntelligenceCRUD(db)
    cleaned = await crud.get_cleaned(data.cleaned_id)
    if cleaned is None:
        raise HTTPException(status_code=400, detail="Referenced cleaned intelligence not found")
    result = await crud.create_analyzed(data)
    await db.commit()
    return result


@router.get("/analyzed", response_model=dict)
async def list_analyzed_intelligence(
    threat_level: ThreatLevel | None = None,
    cleaned_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = IntelligenceCRUD(db)
    items, total = await crud.list_analyzed(
        threat_level=threat_level, cleaned_id=cleaned_id, offset=offset, limit=limit
    )
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/analyzed/{analyzed_id}", response_model=AnalyzedIntelligence)
async def get_analyzed_intelligence(
    analyzed_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = IntelligenceCRUD(db)
    result = await crud.get_analyzed(analyzed_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analyzed intelligence not found")
    return result
