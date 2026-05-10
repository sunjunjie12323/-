import asyncio
import json
import os
import shutil
import tarfile
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Set

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger

from app.api import api_router
from app.config import settings
from app.core.auth import create_default_admin, cleanup_expired_blacklisted_tokens
from app.core.blacktalk_engine import BlackTalkEngine
from app.core.evidence_chain import EvidenceChain
from app.core.exceptions import AppException, RateLimitExceededException
from app.core.knowledge_graph import KnowledgeGraph
from app.core.llm import LLMService
from app.core.pir_engine import PIREngine
from app.core.rate_limiter import rate_limiter
from app.core.task_queue import task_queue
from app.core.vector_store import VectorStore
from app.core.zero_day_detector import ZeroDayDetector
from app.core.attack_chain_predictor import AttackChainPredictor
from app.core.provenance_chain import ProvenanceChain
from app.core.entity_attribution import EntityAttribution
from app.core.temporal_decay import TemporalDecay
from app.core.intelligence_organism import IntelligenceOrganismEngine
from app.db.database import init_db


class MetricsState:
    intelligence_total: int = 0
    search_total: int = 0
    api_requests_total: Dict[str, int] = {}


metrics_state = MetricsState()

_audit_log_dir = Path("./logs")
_audit_log_dir.mkdir(parents=True, exist_ok=True)
_audit_logger = logger.bind(name="audit")
_audit_logger.add(
    str(_audit_log_dir / "audit.log"),
    rotation="10 MB",
    retention="30 days",
    compression="gz",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
    filter=lambda record: record["extra"].get("name") == "audit",
)

_unauthenticated_limiter = rate_limiter.__class__(requests_per_minute=30)
_authenticated_limiter = rate_limiter.__class__(requests_per_minute=120)

_backup_task_handle: asyncio.Task | None = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected, total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected, total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        disconnected = set()
        payload = json.dumps(message, ensure_ascii=False, default=str)
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.add(connection)
        self.active_connections -= disconnected


manager = ConnectionManager()


async def _initialize_services(app: FastAPI):
    logger.info("Initializing core services...")

    logger.info("[1/17] Creating LLMService...")
    llm = LLMService()
    app.state.llm = llm
    logger.info("LLMService created")

    logger.info("[2/17] Creating VectorStore with local embedding engine...")
    from app.core.local_embedding import LocalEmbeddingEngine
    embedding_engine = LocalEmbeddingEngine(dim=256)
    vector_store = VectorStore(
        persist_dir=settings.CHROMA_PERSIST_DIR,
        embedding_engine=embedding_engine,
    )
    app.state.vector_store = vector_store
    app.state.embedding_engine = embedding_engine
    logger.info(f"VectorStore created (local TF-IDF+SVD embedding, dim={embedding_engine.dim})")

    logger.info("[3/17] Creating KnowledgeGraph...")
    knowledge_graph = KnowledgeGraph(persist_dir="./graph_data")
    app.state.knowledge_graph = knowledge_graph
    logger.info("KnowledgeGraph created")

    logger.info("[4/17] Creating BlackTalkEngine...")
    blacktalk_engine = BlackTalkEngine(llm=llm, vector_store=vector_store)
    app.state.blacktalk_engine = blacktalk_engine
    logger.info(f"BlackTalkEngine created with {len(blacktalk_engine._dictionary)} seed terms")

    logger.info("[5/17] Initializing BlackTalkEngine vectors...")
    try:
        await asyncio.wait_for(blacktalk_engine.initialize_vectors(), timeout=30.0)
        logger.info("BlackTalkEngine vectors initialized")
    except asyncio.TimeoutError:
        logger.warning("BlackTalkEngine vector initialization timed out (30s), skipping. Vectors will be built on-demand.")
    except Exception as exc:
        logger.warning(f"BlackTalkEngine vector initialization failed: {exc}. Vectors will be built on-demand.")

    logger.info("[6/17] Creating EvidenceChain...")
    evidence_chain = EvidenceChain(llm=llm, vector_store=vector_store)
    app.state.evidence_chain = evidence_chain
    logger.info("EvidenceChain created")

    logger.info("[7/17] Creating PIREngine...")
    pir_engine = PIREngine(llm=llm, vector_store=vector_store)
    app.state.pir_engine = pir_engine
    logger.info("PIREngine created")

    logger.info("[8/17] Creating OrchestratorAgent with all sub-agents...")
    from app.agents.orchestrator import OrchestratorAgent

    orchestrator = OrchestratorAgent(
        llm=llm,
        vector_store=vector_store,
        blacktalk_engine=blacktalk_engine,
        knowledge_graph=knowledge_graph,
        evidence_chain=evidence_chain,
        pir_engine=pir_engine,
    )
    app.state.orchestrator = orchestrator
    logger.info("OrchestratorAgent created with all sub-agents")

    logger.info("[9/17] Creating collectors...")
    from app.collectors.telegram_collector import TelegramCollector
    from app.collectors.forum_collector import ForumCollector
    from app.collectors.wechat_collector import WeChatCollector
    from app.collectors.darkweb_collector import DarkWebCollector
    from app.collectors.realtime_collector import RealTimeCollector
    from app.collectors.commercial_collector import CommercialCollector

    telegram_collector = TelegramCollector()
    forum_collector = ForumCollector()
    wechat_collector = WeChatCollector()
    darkweb_collector = DarkWebCollector()
    realtime_collector = RealTimeCollector()
    commercial_collector = CommercialCollector()

    app.state.telegram_collector = telegram_collector
    app.state.forum_collector = forum_collector
    app.state.wechat_collector = wechat_collector
    app.state.darkweb_collector = darkweb_collector
    app.state.realtime_collector = realtime_collector
    app.state.commercial_collector = commercial_collector
    logger.info("All collectors created (including commercial sources)")

    logger.info("[10/17] Registering collectors with CollectorAgent...")
    orchestrator.collector.register_collector("telegram", telegram_collector.collect)
    orchestrator.collector.register_collector("forum", forum_collector.collect)
    orchestrator.collector.register_collector("wechat", wechat_collector.collect)
    orchestrator.collector.register_collector("darkweb", darkweb_collector.collect)
    orchestrator.collector.register_collector("realtime", realtime_collector.collect)
    orchestrator.collector.register_collector("commercial", commercial_collector.collect)
    logger.info("All collectors registered")

    logger.info("[11/17] Registering task queue handlers and starting workers...")
    from app.api.agent import register_agent_handlers
    register_agent_handlers()
    await task_queue.start()
    logger.info(f"Task queue started with {settings.MAX_CONCURRENT_TASKS} workers")

    logger.info("[12/17] Creating innovation engines (real ML algorithms, no LLM)...")

    zero_day_detector = ZeroDayDetector(vector_store=vector_store, blacktalk_engine=blacktalk_engine)
    app.state.zero_day_detector = zero_day_detector
    logger.info("ZeroDayDetector created (Skip-gram + KL divergence)")

    attack_chain_predictor = AttackChainPredictor(vector_store=vector_store, knowledge_graph=knowledge_graph)
    app.state.attack_chain_predictor = attack_chain_predictor
    logger.info("AttackChainPredictor created (MITRE ATT&CK + Markov chain)")

    provenance_chain = ProvenanceChain(vector_store=vector_store)
    app.state.provenance_chain = provenance_chain
    logger.info("ProvenanceChain created (SHA-256 cryptographic chain + N-gram hallucination detection)")

    entity_attribution = EntityAttribution(vector_store=vector_store, knowledge_graph=knowledge_graph)
    app.state.entity_attribution = entity_attribution
    logger.info("EntityAttribution created (TransE knowledge graph embedding)")

    temporal_decay = TemporalDecay(vector_store=vector_store)
    app.state.temporal_decay = temporal_decay
    logger.info("TemporalDecay created (MLE half-life estimation)")

    intelligence_organism = IntelligenceOrganismEngine(vector_store=vector_store, knowledge_graph=knowledge_graph)
    app.state.intelligence_organism = intelligence_organism
    logger.info("IntelligenceOrganismEngine created (TF-IDF cosine similarity validation)")

    logger.info("[13/17] Creating default admin user...")
    create_default_admin()
    app.state.connection_manager = manager
    logger.info("All services initialized and stored in app.state")


async def _shutdown_services(app: FastAPI):
    logger.info("Shutting down services...")

    logger.info("Stopping task queue workers...")
    try:
        await task_queue.stop()
        logger.info("Task queue stopped")
    except Exception as exc:
        logger.warning(f"Failed to stop task queue: {exc}")

    if hasattr(app.state, "realtime_collector"):
        try:
            await app.state.realtime_collector.close()
            logger.info("RealTimeCollector session closed")
        except Exception as exc:
            logger.warning(f"Failed to close RealTimeCollector: {exc}")

    for name in ("telegram_collector", "forum_collector", "wechat_collector", "darkweb_collector", "commercial_collector"):
        collector = getattr(app.state, name, None)
        if collector and hasattr(collector, "close"):
            try:
                await collector.close()
                logger.info(f"{name} session closed")
            except Exception as exc:
                logger.warning(f"Failed to close {name}: {exc}")

    if hasattr(app.state, "knowledge_graph"):
        try:
            await app.state.knowledge_graph.save()
            logger.info("KnowledgeGraph saved")
        except Exception as exc:
            logger.warning(f"Failed to save KnowledgeGraph: {exc}")

    if hasattr(app.state, "intelligence_organism"):
        try:
            await app.state.intelligence_organism.save_to_disk()
            logger.info("IntelligenceOrganism data saved")
        except Exception as exc:
            logger.warning(f"Failed to save IntelligenceOrganism data: {exc}")

    if hasattr(app.state, "vector_store"):
        try:
            await app.state.vector_store.persist()
            logger.info("VectorStore persisted")
        except Exception as exc:
            logger.warning(f"Failed to persist VectorStore: {exc}")

    if hasattr(app.state, "llm"):
        try:
            await app.state.llm.close()
            logger.info("LLMService client closed")
        except Exception as exc:
            logger.warning(f"Failed to close LLMService: {exc}")

    logger.info("All services shut down")


async def _periodic_backup(app: FastAPI):
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            await _create_backup(app)
        except Exception as exc:
            logger.error(f"Backup task failed: {exc}")


async def _create_backup(app: FastAPI):
    backup_dir = Path("./backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = backup_dir / f"backup_{timestamp}.tar.gz"

    dirs_to_backup = ["./chroma_data", "./graph_data", "./model_data"]
    db_path = Path("./threat_intel.db")

    with tarfile.open(str(archive_path), "w:gz") as tar:
        for dir_path in dirs_to_backup:
            p = Path(dir_path)
            if p.exists():
                tar.add(str(p), arcname=p.name)
        if db_path.exists():
            tar.add(str(db_path), arcname=db_path.name)

    logger.info(f"Backup created: {archive_path}")

    backups = sorted(backup_dir.glob("backup_*.tar.gz"))
    while len(backups) > 7:
        oldest = backups.pop(0)
        oldest.unlink()
        logger.info(f"Removed old backup: {oldest}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Threat Intel Agent backend...")

    await init_db()
    logger.info("Database initialized successfully")

    try:
        from app.db.seed import fix_seed_sources, seed_from_real_data
        await fix_seed_sources()
        await seed_from_real_data()
    except Exception as exc:
        logger.warning(f"Seed operations skipped: {exc}")

    await _initialize_services(app)
    logger.info("All services initialized successfully")

    global _backup_task_handle
    _backup_task_handle = asyncio.create_task(_periodic_backup(app))
    logger.info("Automatic backup task started (every 6 hours)")

    yield

    if _backup_task_handle:
        _backup_task_handle.cancel()
        try:
            await _backup_task_handle
        except asyncio.CancelledError:
            pass
        logger.info("Backup task cancelled")

    await _shutdown_services(app)
    logger.info("Shutting down Threat Intel Agent backend...")


app = FastAPI(
    title="黑灰产情报分析Agent",
    description="Black/Grey Market Intelligence Analysis Agent API — 提供情报采集、清洗、分析、报告全流程管理",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Threat Intel Agent API",
    },
    license_info={
        "name": "Proprietary",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def https_redirect_middleware(request: Request, call_next):
    if request.url.scheme == "http" and request.headers.get("x-forwarded-proto") == "https":
        https_url = request.url.replace(scheme="https")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=str(https_url), status_code=301)
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json", "/metrics"):
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    user_id = None
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from app.core.auth import decode_access_token, is_token_blacklisted
            token = auth_header[7:]
            if not is_token_blacklisted(token):
                token_data = decode_access_token(token)
                user_id = token_data.user_id
        except Exception:
            pass
    if user_id:
        allowed, retry_after = _authenticated_limiter.check_rate_limit(client_ip, user_id)
    else:
        allowed, retry_after = _unauthenticated_limiter.check_rate_limit(client_ip)
    if not allowed:
        from app.core.exceptions import RateLimitExceededException
        exc = RateLimitExceededException(
            detail=f"Rate limit exceeded. Retry after {retry_after:.0f} seconds.",
            details={"retry_after_seconds": round(retry_after, 1)},
        )
        return JSONResponse(
            status_code=429,
            content={"error": exc.to_dict()},
            headers={"Retry-After": str(int(retry_after))},
        )
    return await call_next(request)


@app.middleware("http")
async def audit_logging_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    user_id = "anonymous"
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from app.core.auth import decode_access_token, is_token_blacklisted
            token = auth_header[7:]
            if not is_token_blacklisted(token):
                token_data = decode_access_token(token)
                user_id = token_data.user_id
        except Exception:
            user_id = "invalid_token"
    client_ip = request.client.host if request.client else "unknown"
    endpoint = request.url.path
    metrics_state.api_requests_total[endpoint] = metrics_state.api_requests_total.get(endpoint, 0) + 1
    _audit_logger.info(
        f"{request.method} {endpoint} user={user_id} ip={client_ip} "
        f"status={response.status_code} duration={duration_ms:.1f}ms"
    )
    return response


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    error_response = {"error": exc.to_dict()}
    response = JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )
    if isinstance(exc, RateLimitExceededException):
        retry_after = exc.details.get("retry_after_seconds", 60)
        response.headers["Retry-After"] = str(int(retry_after))
    return response


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            f"Unhandled exception in {request.method} {request.url.path}: {exc}\n"
            f"{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error",
                    "details": {"path": str(request.url.path)},
                }
            },
        )


app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check(request: Request):
    services_status = {}
    for attr in ("llm", "vector_store", "knowledge_graph", "blacktalk_engine",
                 "evidence_chain", "pir_engine", "orchestrator",
                 "zero_day_detector", "attack_chain_predictor", "provenance_chain",
                 "entity_attribution", "temporal_decay", "intelligence_organism"):
        services_status[attr] = hasattr(request.app.state, attr)

    task_queue_stats = {
        "total_tasks": len(task_queue._tasks),
        "pending": sum(1 for t in task_queue._tasks.values() if t.status.value == "pending"),
        "running": sum(1 for t in task_queue._tasks.values() if t.status.value == "running"),
        "completed": sum(1 for t in task_queue._tasks.values() if t.status.value == "completed"),
        "failed": sum(1 for t in task_queue._tasks.values() if t.status.value == "failed"),
    }

    return {
        "status": "healthy",
        "service": "threat-intel-agent",
        "version": "2.0.0",
        "services": services_status,
        "task_queue": task_queue_stats,
    }


@app.get("/metrics", tags=["system"], response_class=PlainTextResponse)
async def prometheus_metrics(request: Request):
    active_organisms = 0
    if hasattr(request.app.state, "intelligence_organism"):
        try:
            organism_engine = request.app.state.intelligence_organism
            active_organisms = sum(
                1 for o in getattr(organism_engine, "_organisms", {}).values()
                if getattr(o, "is_alive", lambda: True)()
            )
        except Exception:
            active_organisms = 0

    graph_nodes = 0
    graph_edges = 0
    if hasattr(request.app.state, "knowledge_graph"):
        try:
            kg = request.app.state.knowledge_graph
            graph_nodes = kg.graph.number_of_nodes() if hasattr(kg, "graph") else 0
            graph_edges = kg.graph.number_of_edges() if hasattr(kg, "graph") else 0
        except Exception:
            graph_nodes = 0
            graph_edges = 0

    lines = [
        f"# HELP threat_intel_intelligence_total Total number of intelligence items",
        f"# TYPE threat_intel_intelligence_total counter",
        f"threat_intel_intelligence_total {metrics_state.intelligence_total}",
        f"",
        f"# HELP threat_intel_search_total Total number of searches",
        f"# TYPE threat_intel_search_total counter",
        f"threat_intel_search_total {metrics_state.search_total}",
        f"",
        f"# HELP threat_intel_api_requests_total Total API requests by endpoint",
        f"# TYPE threat_intel_api_requests_total counter",
    ]
    for endpoint, count in sorted(metrics_state.api_requests_total.items()):
        safe_label = endpoint.replace("/", "_").strip("_") or "root"
        lines.append(f'threat_intel_api_requests_total{{endpoint="{endpoint}"}} {count}')
    lines.extend([
        f"",
        f"# HELP threat_intel_active_organisms Number of alive organisms",
        f"# TYPE threat_intel_active_organisms gauge",
        f"threat_intel_active_organisms {active_organisms}",
        f"",
        f"# HELP threat_intel_graph_nodes Number of graph nodes",
        f"# TYPE threat_intel_graph_nodes gauge",
        f"threat_intel_graph_nodes {graph_nodes}",
        f"",
        f"# HELP threat_intel_graph_edges Number of graph edges",
        f"# TYPE threat_intel_graph_edges gauge",
        f"threat_intel_graph_edges {graph_edges}",
        f"",
    ])
    return "\n".join(lines)


@app.websocket("/ws/intelligence")
async def websocket_intelligence(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type", "unknown")
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif msg_type == "subscribe":
                    await websocket.send_text(
                        json.dumps({"type": "subscribed", "channels": message.get("channels", [])})
                    )
                elif msg_type == "agent_status":
                    orchestrator = websocket.app.state.orchestrator
                    status = orchestrator.get_agent_status()
                    await websocket.send_text(
                        json.dumps({"type": "agent_status", "data": status}, ensure_ascii=False, default=str)
                    )
                else:
                    await manager.broadcast(message)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid JSON"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
