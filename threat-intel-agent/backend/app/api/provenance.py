import asyncio
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.core.auth import User, get_current_user, require_role, Role
from app.core.provenance_chain import ProvenanceChain

router = APIRouter(prefix="/provenance", tags=["provenance"])


class ProvenanceRecordRequest(BaseModel):
    intelligence_id: str = Field(..., min_length=1)
    stage: str = Field(..., min_length=1)
    input_data: Dict = Field(default_factory=dict)
    output_data: Dict = Field(default_factory=dict)
    algorithm_input: Optional[str] = None
    algorithm_output: Optional[str] = None
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    operator: str = Field(default="automated")


def get_provenance_chain(request: Request) -> ProvenanceChain:
    return request.app.state.provenance_chain


@router.post("/record")
async def record_provenance(
    data: ProvenanceRecordRequest,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    chain = get_provenance_chain(request)
    try:
        record = await asyncio.wait_for(
            chain.record_provenance(
                intelligence_id=data.intelligence_id,
                stage=data.stage,
                input_data=data.input_data,
                output_data=data.output_data,
                algorithm_input=data.algorithm_input,
                algorithm_output=data.algorithm_output,
                confidence_before=data.confidence_before,
                confidence_after=data.confidence_after,
            ),
            timeout=60,
        )
        return record.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Provenance recording timed out for intelligence '{data.intelligence_id}'")
        raise HTTPException(status_code=504, detail="Provenance recording timed out")
    except Exception as exc:
        logger.error(f"Provenance recording failed for intelligence '{data.intelligence_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/verify/{intelligence_id}")
async def verify_provenance(
    intelligence_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    chain = get_provenance_chain(request)
    try:
        result = await asyncio.wait_for(
            chain.verify_provenance(intelligence_id),
            timeout=60,
        )
        return result.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Provenance verification timed out for intelligence '{intelligence_id}'")
        raise HTTPException(status_code=504, detail="Provenance verification timed out")
    except Exception as exc:
        logger.error(f"Provenance verification failed for intelligence '{intelligence_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/evolution/{intelligence_id}")
async def get_confidence_evolution(
    intelligence_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    chain = get_provenance_chain(request)
    try:
        evolution = await asyncio.wait_for(
            chain.get_confidence_evolution(intelligence_id),
            timeout=60,
        )
        return {
            "intelligence_id": intelligence_id,
            "evolution": [e.to_dict() for e in evolution],
        }
    except asyncio.TimeoutError:
        logger.error(f"Confidence evolution timed out for intelligence '{intelligence_id}'")
        raise HTTPException(status_code=504, detail="Confidence evolution timed out")
    except Exception as exc:
        logger.error(f"Confidence evolution failed for intelligence '{intelligence_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/hallucination-check/{intelligence_id}")
async def detect_hallucination(
    intelligence_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    chain = get_provenance_chain(request)
    try:
        result = await asyncio.wait_for(
            chain.detect_hallucination(intelligence_id),
            timeout=60,
        )
        return result.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Hallucination check timed out for intelligence '{intelligence_id}'")
        raise HTTPException(status_code=504, detail="Hallucination check timed out")
    except Exception as exc:
        logger.error(f"Hallucination check failed for intelligence '{intelligence_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search-by-content")
async def search_by_content(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    chain = get_provenance_chain(request)
    query_lower = query.lower()
    matched = []
    for intel_id, records in chain._chains.items():
        for record in records:
            input_text = json.dumps(record.metadata.get("input_data", {}), ensure_ascii=False, default=str).lower()
            output_text = json.dumps(record.metadata.get("output_data", {}), ensure_ascii=False, default=str).lower()
            algo_input = (record.algorithm_input or "").lower()
            algo_output = (record.algorithm_output or "").lower()
            if query_lower in input_text or query_lower in output_text or query_lower in algo_input or query_lower in algo_output:
                matched.append({
                    "intelligence_id": intel_id,
                    "stage": record.stage,
                    "timestamp": record.timestamp,
                    "snippet": (record.algorithm_output or json.dumps(record.metadata.get("output_data", {}), ensure_ascii=False, default=str))[:200],
                })
                break
    matched = matched[:limit]
    if not matched:
        raise HTTPException(status_code=404, detail=f"No intelligence found matching: {query}")
    return {"query": query, "results": matched, "total": len(matched)}


@router.get("/chain/{intelligence_id}")
async def get_provenance_chain_records(
    intelligence_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    chain = get_provenance_chain(request)
    try:
        records = chain.get_chain(intelligence_id)
        return {
            "intelligence_id": intelligence_id,
            "records": [r.to_dict() for r in records],
        }
    except Exception as exc:
        logger.error(f"Failed to get provenance chain for intelligence '{intelligence_id}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
