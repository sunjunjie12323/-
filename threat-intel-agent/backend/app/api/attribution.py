import asyncio
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.core.auth import User, get_current_user, require_role, Role
from app.core.entity_attribution import EntityAttribution

router = APIRouter(prefix="/attribution", tags=["attribution"])


def get_entity_attribution(request: Request) -> EntityAttribution:
    return request.app.state.entity_attribution


@router.post("/fingerprint/{entity_id}")
async def compute_behavioral_fingerprint(
    entity_id: str,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    attribution = get_entity_attribution(request)
    try:
        fingerprint = await asyncio.wait_for(
            attribution.compute_behavioral_fingerprint(entity_id),
            timeout=60,
        )
        return fingerprint.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Behavioral fingerprint computation timed out for entity '{entity_id}'")
        raise HTTPException(status_code=504, detail="Behavioral fingerprint computation timed out")
    except Exception as exc:
        logger.error(f"Behavioral fingerprint computation failed for entity '{entity_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/find-same/{entity_id}")
async def find_same_entity(
    entity_id: str,
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    request: Request = None,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    attribution = get_entity_attribution(request)
    try:
        matches = await asyncio.wait_for(
            attribution.find_same_entity(entity_id, threshold=threshold),
            timeout=60,
        )
        all_entity_ids = [
            eid for eid in attribution.knowledge_graph._entities
            if eid != entity_id
        ]
        return {
            "matches": [m.to_dict() for m in matches],
            "total_compared": len(all_entity_ids),
        }
    except asyncio.TimeoutError:
        logger.error(f"Same entity search timed out for entity '{entity_id}'")
        raise HTTPException(status_code=504, detail="Same entity search timed out")
    except Exception as exc:
        logger.error(f"Same entity search failed for entity '{entity_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/find-same-by-name/{name}")
async def find_same_entity_by_name(
    name: str,
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    request: Request = None,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    kg = request.app.state.knowledge_graph
    entity = None
    for e in kg._entities.values():
        if e.value.lower() == name.lower():
            entity = e
            break
    if not entity:
        results = await kg.search_entities(name, limit=1)
        if results:
            entity = results[0]
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {name}")
    entity_id = entity.id
    attribution = get_entity_attribution(request)
    try:
        matches = await asyncio.wait_for(
            attribution.find_same_entity(entity_id, threshold=threshold),
            timeout=60,
        )
        all_entity_ids = [
            eid for eid in attribution.knowledge_graph._entities
            if eid != entity_id
        ]
        return {
            "entity_id": entity_id,
            "entity_name": entity.value,
            "matches": [m.to_dict() for m in matches],
            "total_compared": len(all_entity_ids),
        }
    except asyncio.TimeoutError:
        logger.error(f"Same entity search timed out for name '{name}'")
        raise HTTPException(status_code=504, detail="Same entity search timed out")
    except Exception as exc:
        logger.error(f"Same entity search failed for name '{name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/report/{entity_id}")
async def generate_attribution_report(
    entity_id: str,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    attribution = get_entity_attribution(request)
    try:
        report = await asyncio.wait_for(
            attribution.generate_attribution_report(entity_id),
            timeout=60,
        )
        return report
    except asyncio.TimeoutError:
        logger.error(f"Attribution report generation timed out for entity '{entity_id}'")
        raise HTTPException(status_code=504, detail="Attribution report generation timed out")
    except Exception as exc:
        logger.error(f"Attribution report generation failed for entity '{entity_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
