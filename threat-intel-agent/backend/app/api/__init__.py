from fastapi import APIRouter

from .agent import router as agent_router
from .attack_prediction import router as attack_prediction_router
from .attribution import router as attribution_router
from .auth import router as auth_router
from .blacktalk import router as blacktalk_router
from .dashboard import router as dashboard_router
from .entities import router as entities_router
from .graph import router as graph_router
from .intelligence import router as intelligence_router
from .pirs import router as pirs_router
from .provenance import router as provenance_router
from .reports import router as reports_router
from .tasks import router as tasks_router
from .temporal_decay import router as temporal_decay_router
from .zero_day import router as zero_day_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(intelligence_router)
api_router.include_router(entities_router)
api_router.include_router(pirs_router)
api_router.include_router(reports_router)
api_router.include_router(blacktalk_router)
api_router.include_router(graph_router)
api_router.include_router(agent_router)
api_router.include_router(dashboard_router)
api_router.include_router(tasks_router)
api_router.include_router(zero_day_router)
api_router.include_router(attack_prediction_router)
api_router.include_router(provenance_router)
api_router.include_router(attribution_router)
api_router.include_router(temporal_decay_router)
