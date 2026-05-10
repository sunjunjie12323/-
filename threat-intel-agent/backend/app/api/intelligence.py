from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import IntelligenceCRUD
from app.db.database import get_db
from app.models.intelligence import (
    AnalyzedIntelligence,
    CleanedIntelligence,
    IntelligenceSource,
    IntelligenceStatus,
    RawIntelligence,
    ThreatLevel,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.post("/raw", response_model=RawIntelligence, status_code=201)
async def create_raw_intelligence(
    data: RawIntelligence,
    db: AsyncSession = Depends(get_db),
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
):
    crud = IntelligenceCRUD(db)
    items, total = await crud.list_raw(source=source, status=status, offset=offset, limit=limit)
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/raw/{raw_id}", response_model=RawIntelligence)
async def get_raw_intelligence(raw_id: str, db: AsyncSession = Depends(get_db)):
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
):
    crud = IntelligenceCRUD(db)
    result = await crud.update_status(raw_id, status)
    if result is None:
        raise HTTPException(status_code=404, detail="Raw intelligence not found")
    await db.commit()
    return result


@router.delete("/raw/{raw_id}", status_code=204)
async def delete_raw_intelligence(raw_id: str, db: AsyncSession = Depends(get_db)):
    crud = IntelligenceCRUD(db)
    deleted = await crud.delete_raw(raw_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Raw intelligence not found")
    await db.commit()


@router.post("/cleaned", response_model=CleanedIntelligence, status_code=201)
async def create_cleaned_intelligence(
    data: CleanedIntelligence,
    db: AsyncSession = Depends(get_db),
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
):
    crud = IntelligenceCRUD(db)
    items, total = await crud.list_cleaned(
        threat_level=threat_level, raw_id=raw_id, offset=offset, limit=limit
    )
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/cleaned/{cleaned_id}", response_model=CleanedIntelligence)
async def get_cleaned_intelligence(cleaned_id: str, db: AsyncSession = Depends(get_db)):
    crud = IntelligenceCRUD(db)
    result = await crud.get_cleaned(cleaned_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Cleaned intelligence not found")
    return result


@router.post("/analyzed", response_model=AnalyzedIntelligence, status_code=201)
async def create_analyzed_intelligence(
    data: AnalyzedIntelligence,
    db: AsyncSession = Depends(get_db),
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
):
    crud = IntelligenceCRUD(db)
    items, total = await crud.list_analyzed(
        threat_level=threat_level, cleaned_id=cleaned_id, offset=offset, limit=limit
    )
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/analyzed/{analyzed_id}", response_model=AnalyzedIntelligence)
async def get_analyzed_intelligence(analyzed_id: str, db: AsyncSession = Depends(get_db)):
    crud = IntelligenceCRUD(db)
    result = await crud.get_analyzed(analyzed_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analyzed intelligence not found")
    return result
