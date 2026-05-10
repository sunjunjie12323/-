import asyncio
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.core.auth import User, get_current_user, require_role, Role
from app.core.attack_chain_predictor import AttackChainPredictor

router = APIRouter(prefix="/attack-prediction", tags=["attack-prediction"])


class PredictRequest(BaseModel):
    entity_id: str = Field(..., min_length=1)
    depth: int = Field(default=3, ge=1, le=10)


class SimulateRequest(BaseModel):
    entity_id: str = Field(..., min_length=1)
    steps: int = Field(default=5, ge=1, le=20)


class PredictByNameRequest(BaseModel):
    name: str = Field(..., min_length=1)
    depth: int = Field(default=3, ge=1, le=10)


class EarlyWarningRequest(BaseModel):
    entity_id: str = Field(..., min_length=1)


def get_attack_chain_predictor(request: Request) -> AttackChainPredictor:
    return request.app.state.attack_chain_predictor


@router.post("/predict")
async def predict_next_steps(
    data: PredictRequest,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    predictor = get_attack_chain_predictor(request)
    try:
        result = await asyncio.wait_for(
            predictor.predict_next_steps(data.entity_id, depth=data.depth),
            timeout=60,
        )
        return result.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Attack prediction timed out for entity '{data.entity_id}'")
        raise HTTPException(status_code=504, detail="Attack prediction timed out")
    except Exception as exc:
        logger.error(f"Attack prediction failed for entity '{data.entity_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/predict-by-name")
async def predict_by_name(
    data: PredictByNameRequest,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    kg = request.app.state.knowledge_graph
    entity = None
    for e in kg._entities.values():
        if e.value.lower() == data.name.lower():
            entity = e
            break
    if not entity:
        results = await kg.search_entities(data.name, limit=1)
        if results:
            entity = results[0]
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {data.name}")
    entity_id = entity.id
    predictor = get_attack_chain_predictor(request)
    try:
        result = await asyncio.wait_for(
            predictor.predict_next_steps(entity_id, depth=data.depth),
            timeout=60,
        )
        return {
            "entity_id": entity_id,
            "entity_name": entity.value,
            "predictions": result.to_dict(),
        }
    except asyncio.TimeoutError:
        logger.error(f"Attack prediction timed out for entity '{entity_id}'")
        raise HTTPException(status_code=504, detail="Attack prediction timed out")
    except Exception as exc:
        logger.error(f"Attack prediction failed for entity '{entity_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/simulate")
async def simulate_attack_chain(
    data: SimulateRequest,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    predictor = get_attack_chain_predictor(request)
    try:
        result = await asyncio.wait_for(
            predictor.simulate_attack_chain(data.entity_id, steps=data.steps),
            timeout=60,
        )
        return result.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Attack chain simulation timed out for entity '{data.entity_id}'")
        raise HTTPException(status_code=504, detail="Attack chain simulation timed out")
    except Exception as exc:
        logger.error(f"Attack chain simulation failed for entity '{data.entity_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/early-warning")
async def find_early_warning_signals(
    data: EarlyWarningRequest,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    predictor = get_attack_chain_predictor(request)
    try:
        prediction = await asyncio.wait_for(
            predictor.predict_next_steps(data.entity_id, depth=3),
            timeout=60,
        )
        warnings = await asyncio.wait_for(
            predictor.find_early_warning_signals(prediction),
            timeout=60,
        )
        return {
            "warnings": [w.to_dict() for w in warnings],
            "total_signals": len(warnings),
        }
    except asyncio.TimeoutError:
        logger.error(f"Early warning analysis timed out for entity '{data.entity_id}'")
        raise HTTPException(status_code=504, detail="Early warning analysis timed out")
    except Exception as exc:
        logger.error(f"Early warning analysis failed for entity '{data.entity_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
