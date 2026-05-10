import asyncio
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.core.auth import User, get_current_user, require_role, Role
from app.core.zero_day_detector import ZeroDayDetector

router = APIRouter(prefix="/zero-day", tags=["zero-day"])


class ZeroDayDetectRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)


def get_zero_day_detector(request: Request) -> ZeroDayDetector:
    return request.app.state.zero_day_detector


@router.post("/detect")
async def detect_zero_day_terms(
    data: ZeroDayDetectRequest,
    request: Request,
    current_user: User = Depends(require_role(Role.ADMIN, Role.ANALYST)),
):
    detector = get_zero_day_detector(request)
    try:
        zero_day_terms = await asyncio.wait_for(
            detector.detect_zero_day_terms(data.text),
            timeout=60,
        )
        known_count = 0
        try:
            decode_result = await detector.blacktalk_engine.decode(data.text)
            if isinstance(decode_result, dict):
                known_count = decode_result.get("terms_found", 0)
            elif hasattr(decode_result, 'terms_found'):
                known_count = decode_result.terms_found
        except Exception:
            pass
        return {
            "zero_day_terms": [t.to_dict() for t in zero_day_terms],
            "known_terms_count": known_count,
            "total_analyzed": len(zero_day_terms) + known_count,
        }
    except asyncio.TimeoutError:
        logger.error("Zero-day detection timed out")
        raise HTTPException(status_code=504, detail="Zero-day detection timed out")
    except Exception as exc:
        logger.error(f"Zero-day detection failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/drift/{term}")
async def track_semantic_drift(
    term: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    detector = get_zero_day_detector(request)
    try:
        result = await asyncio.wait_for(
            detector.track_semantic_drift(term),
            timeout=60,
        )
        return result.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Semantic drift analysis timed out for term '{term}'")
        raise HTTPException(status_code=504, detail="Semantic drift analysis timed out")
    except Exception as exc:
        logger.error(f"Semantic drift analysis failed for term '{term}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/migration/{term}")
async def track_cross_platform_migration(
    term: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    detector = get_zero_day_detector(request)
    try:
        result = await asyncio.wait_for(
            detector.track_cross_platform_migration(term),
            timeout=60,
        )
        return result.to_dict()
    except asyncio.TimeoutError:
        logger.error(f"Cross-platform migration analysis timed out for term '{term}'")
        raise HTTPException(status_code=504, detail="Cross-platform migration analysis timed out")
    except Exception as exc:
        logger.error(f"Cross-platform migration analysis failed for term '{term}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
