import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api import api_router
from app.config import settings
from app.core.blacktalk_engine import BlackTalkEngine
from app.core.evidence_chain import EvidenceChain
from app.core.knowledge_graph import KnowledgeGraph
from app.core.llm import LLMService
from app.core.pir_engine import PIREngine
from app.core.vector_store import VectorStore
from app.db.database import init_db


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

    logger.info("[1/11] Creating LLMService...")
    llm = LLMService()
    app.state.llm = llm
    logger.info("LLMService created")

    logger.info("[2/11] Creating VectorStore...")
    vector_store = VectorStore(
        persist_dir=settings.CHROMA_PERSIST_DIR,
        llm=llm,
    )
    app.state.vector_store = vector_store
    logger.info("VectorStore created")

    logger.info("[3/11] Creating KnowledgeGraph...")
    knowledge_graph = KnowledgeGraph(persist_dir="./graph_data")
    app.state.knowledge_graph = knowledge_graph
    logger.info("KnowledgeGraph created")

    logger.info("[4/11] Creating BlackTalkEngine...")
    blacktalk_engine = BlackTalkEngine(llm=llm, vector_store=vector_store)
    app.state.blacktalk_engine = blacktalk_engine
    logger.info(f"BlackTalkEngine created with {len(blacktalk_engine._dictionary)} seed terms")

    logger.info("[5/11] Initializing BlackTalkEngine vectors...")
    try:
        await asyncio.wait_for(blacktalk_engine.initialize_vectors(), timeout=30.0)
        logger.info("BlackTalkEngine vectors initialized")
    except asyncio.TimeoutError:
        logger.warning("BlackTalkEngine vector initialization timed out (30s), skipping. Vectors will be built on-demand.")
    except Exception as exc:
        logger.warning(f"BlackTalkEngine vector initialization failed: {exc}. Vectors will be built on-demand.")

    logger.info("[6/11] Creating EvidenceChain...")
    evidence_chain = EvidenceChain(llm=llm, vector_store=vector_store)
    app.state.evidence_chain = evidence_chain
    logger.info("EvidenceChain created")

    logger.info("[7/11] Creating PIREngine...")
    pir_engine = PIREngine(llm=llm, vector_store=vector_store)
    app.state.pir_engine = pir_engine
    logger.info("PIREngine created")

    logger.info("[8/11] Creating OrchestratorAgent with all sub-agents...")
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

    logger.info("[9/11] Creating collectors...")
    from app.collectors.telegram_collector import TelegramCollector
    from app.collectors.forum_collector import ForumCollector
    from app.collectors.wechat_collector import WeChatCollector
    from app.collectors.darkweb_collector import DarkWebCollector

    telegram_collector = TelegramCollector(llm=llm)
    forum_collector = ForumCollector(llm=llm)
    wechat_collector = WeChatCollector(llm=llm)
    darkweb_collector = DarkWebCollector(llm=llm)

    app.state.telegram_collector = telegram_collector
    app.state.forum_collector = forum_collector
    app.state.wechat_collector = wechat_collector
    app.state.darkweb_collector = darkweb_collector
    logger.info("All collectors created")

    logger.info("[10/11] Registering collectors with CollectorAgent...")
    orchestrator.collector.register_collector("telegram", telegram_collector.collect)
    orchestrator.collector.register_collector("forum", forum_collector.collect)
    orchestrator.collector.register_collector("wechat", wechat_collector.collect)
    orchestrator.collector.register_collector("darkweb", darkweb_collector.collect)
    logger.info("All collectors registered")

    logger.info("[11/11] Storing service references in app.state...")
    app.state.connection_manager = manager
    logger.info("All services initialized and stored in app.state")


async def _shutdown_services(app: FastAPI):
    logger.info("Shutting down services...")

    if hasattr(app.state, "knowledge_graph"):
        try:
            await app.state.knowledge_graph.save()
            logger.info("KnowledgeGraph saved")
        except Exception as exc:
            logger.warning(f"Failed to save KnowledgeGraph: {exc}")

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Threat Intel Agent backend...")

    await init_db()
    logger.info("Database initialized successfully")

    await _initialize_services(app)
    logger.info("All services initialized successfully")

    yield

    await _shutdown_services(app)
    logger.info("Shutting down Threat Intel Agent backend...")


app = FastAPI(
    title="黑灰产情报分析Agent",
    description="Black/Grey Market Intelligence Analysis Agent API — 提供情报采集、清洗、分析、报告全流程管理",
    version="1.0.0",
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
async def error_handling_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        logger.error(
            f"Unhandled exception in {request.method} {request.url.path}: {exc}\n"
            f"{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "path": str(request.url.path),
            },
        )


app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check(request: Request):
    services_status = {}
    for attr in ("llm", "vector_store", "knowledge_graph", "blacktalk_engine",
                 "evidence_chain", "pir_engine", "orchestrator"):
        services_status[attr] = hasattr(request.app.state, attr)

    return {
        "status": "healthy",
        "service": "threat-intel-agent",
        "version": "1.0.0",
        "services": services_status,
    }


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
