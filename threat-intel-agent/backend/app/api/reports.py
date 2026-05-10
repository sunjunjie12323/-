from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User, get_current_user, require_role, Role
from app.db.crud import ReportCRUD
from app.db.database import get_db
from app.models.report import Report, ReportStatus

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=Report, status_code=201)
async def create_report(
    data: Report,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = ReportCRUD(db)
    result = await crud.create_report(data)
    await db.commit()
    return result


@router.get("", response_model=dict)
async def list_reports(
    status: ReportStatus | None = None,
    pir_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = ReportCRUD(db)
    items, total = await crud.list_reports(status=status, pir_id=pir_id, offset=offset, limit=limit)
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{report_id}", response_model=Report)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = ReportCRUD(db)
    result = await crud.get_report(report_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return result


@router.patch("/{report_id}", response_model=Report)
async def update_report(
    report_id: str,
    updates: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = ReportCRUD(db)
    result = await crud.update_report(report_id, **updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await db.commit()
    return result


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = ReportCRUD(db)
    deleted = await crud.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    await db.commit()
