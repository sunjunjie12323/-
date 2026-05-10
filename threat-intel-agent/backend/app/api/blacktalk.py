from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.core.blacktalk_engine import BlackTalkEngine
from app.core.llm import LLMService
from app.core.vector_store import VectorStore

router = APIRouter(prefix="/blacktalk", tags=["blacktalk"])


class BlackTalkTermCreate(BaseModel):
    term: str = Field(..., min_length=1, max_length=100)
    meaning: str = Field(..., min_length=1, max_length=500)
    context: str = Field(default="", max_length=1000)
    source: str = Field(default="manual")


class BlackTalkDecodeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


def get_blacktalk_engine(request: Request) -> BlackTalkEngine:
    return request.app.state.blacktalk_engine


def get_llm(request: Request) -> LLMService:
    return request.app.state.llm


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


@router.get("/terms")
async def list_terms(
    category: Optional[str] = None,
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    request: Request = None,
):
    engine = get_blacktalk_engine(request)
    try:
        all_terms = await engine.get_all(category=category)
        if search:
            search_lower = search.lower()
            all_terms = [
                t for t in all_terms
                if search_lower in t.term.lower()
                or search_lower in t.meaning.lower()
            ]
        total = len(all_terms)
        paginated = all_terms[offset: offset + limit]
        return {
            "items": [t.to_dict() for t in paginated],
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    except Exception as exc:
        logger.error(f"Failed to list blacktalk terms: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/terms/{term_id}")
async def get_term(term_id: str, request: Request):
    engine = get_blacktalk_engine(request)
    term = engine._dictionary.get(term_id)
    if term is None:
        raise HTTPException(status_code=404, detail="Black talk term not found")
    return term.to_dict()


@router.post("/terms", status_code=201)
async def add_term(data: BlackTalkTermCreate, request: Request):
    engine = get_blacktalk_engine(request)
    try:
        bt = await engine.learn(
            term=data.term,
            meaning=data.meaning,
            context=data.context,
            source=data.source,
        )
        return bt.to_dict()
    except Exception as exc:
        logger.error(f"Failed to add blacktalk term: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/decode")
async def decode_text(data: BlackTalkDecodeRequest, request: Request):
    engine = get_blacktalk_engine(request)
    try:
        decoded_text, decoded_terms = await engine.decode(data.text)
        auto_learned = []
        if decoded_terms:
            try:
                learned = await engine.auto_learn(data.text, decoded_terms)
                auto_learned = [t.to_dict() for t in learned]
            except Exception as exc:
                logger.warning(f"Auto-learn during decode failed: {exc}")
        return {
            "original_text": data.text,
            "decoded_text": decoded_text,
            "decoded_terms": decoded_terms,
            "terms_found": len(decoded_terms),
            "auto_learned": auto_learned,
        }
    except Exception as exc:
        logger.error(f"Failed to decode text: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search")
async def search_blacktalk(
    q: str = Query(..., min_length=1),
    n: int = Query(10, ge=1, le=50),
    request: Request = None,
):
    engine = get_blacktalk_engine(request)
    try:
        terms = await engine.search(query=q, n=n)
        return {
            "query": q,
            "results": [t.to_dict() for t in terms],
            "total": len(terms),
        }
    except Exception as exc:
        logger.error(f"Blacktalk search failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stats")
async def get_stats(request: Request):
    engine = get_blacktalk_engine(request)
    try:
        all_terms = await engine.get_all()
        category_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}
        confidence_sum = 0.0
        for t in all_terms:
            category_counts[t.category] = category_counts.get(t.category, 0) + 1
            source_counts[t.source] = source_counts.get(t.source, 0) + 1
            confidence_sum += t.confidence
        avg_confidence = confidence_sum / len(all_terms) if all_terms else 0.0
        return {
            "total_terms": len(all_terms),
            "categories": category_counts,
            "sources": source_counts,
            "average_confidence": round(avg_confidence, 3),
        }
    except Exception as exc:
        logger.error(f"Failed to get blacktalk stats: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
