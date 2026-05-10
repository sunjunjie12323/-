from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User, get_current_user, require_role, Role
from app.db.crud import PIRCRUD
from app.db.database import get_db
from app.models.pir import PIR, PIRPriority, PIRStatus, PIRTask

router = APIRouter(prefix="/pirs", tags=["pirs"])


@router.post("", response_model=PIR, status_code=201)
async def create_pir(
    data: PIR,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = PIRCRUD(db)
    result = await crud.create_pir(data)
    await db.commit()
    return result


@router.get("", response_model=dict)
async def list_pirs(
    status: PIRStatus | None = None,
    priority: PIRPriority | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = PIRCRUD(db)
    items, total = await crud.list_pirs(status=status, priority=priority, offset=offset, limit=limit)
    await db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{pir_id}", response_model=PIR)
async def get_pir(
    pir_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = PIRCRUD(db)
    result = await crud.get_pir(pir_id)
    if result is None:
        raise HTTPException(status_code=404, detail="PIR not found")
    return result


@router.patch("/{pir_id}", response_model=PIR)
async def update_pir(
    pir_id: str,
    updates: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = PIRCRUD(db)
    result = await crud.update_pir(pir_id, **updates)
    if result is None:
        raise HTTPException(status_code=404, detail="PIR not found")
    await db.commit()
    return result


@router.delete("/{pir_id}", status_code=204)
async def delete_pir(
    pir_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = PIRCRUD(db)
    deleted = await crud.delete_pir(pir_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="PIR not found")
    await db.commit()


@router.post("/{pir_id}/tasks", response_model=PIRTask, status_code=201)
async def create_pir_task(
    pir_id: str,
    data: PIRTask,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = PIRCRUD(db)
    pir = await crud.get_pir(pir_id)
    if pir is None:
        raise HTTPException(status_code=404, detail="PIR not found")
    data.pir_id = pir_id
    result = await crud.create_pir_task(data)
    await db.commit()
    return result


@router.get("/{pir_id}/tasks", response_model=List[PIRTask])
async def list_pir_tasks(
    pir_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud = PIRCRUD(db)
    return await crud.list_pir_tasks(pir_id)


@router.patch("/tasks/{task_id}", response_model=PIRTask)
async def update_pir_task(
    task_id: str,
    updates: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    crud = PIRCRUD(db)
    result = await crud.update_pir_task(task_id, **updates)
    if result is None:
        raise HTTPException(status_code=404, detail="PIR task not found")
    await db.commit()
    return result
