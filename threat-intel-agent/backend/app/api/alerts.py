from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.core.auth import User, get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/active")
async def get_active_alerts(
    request: Request,
    severity: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
):
    engine = request.app.state.alert_engine
    alerts = engine.get_active_alerts(severity=severity)
    return {"alerts": [a.to_dict() for a in alerts], "total": len(alerts)}


@router.get("/stats")
async def get_alert_stats(request: Request, user: User = Depends(get_current_user)):
    return request.app.state.alert_engine.get_alert_stats()


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    request: Request,
    alert_id: str,
    user: User = Depends(get_current_user),
):
    engine = request.app.state.alert_engine
    if not engine.acknowledge_alert(alert_id):
        raise HTTPException(404, "Alert not found")
    return {"status": "acknowledged"}


@router.get("/rules")
async def get_alert_rules(request: Request, user: User = Depends(get_current_user)):
    engine = request.app.state.alert_engine
    return {"rules": [r.to_dict() for r in engine.rules.values()]}


@router.put("/rules/{rule_id}/toggle")
async def toggle_alert_rule(
    request: Request,
    rule_id: str,
    enabled: bool = Query(...),
    user: User = Depends(get_current_user),
):
    engine = request.app.state.alert_engine
    if rule_id not in engine.rules:
        raise HTTPException(404, "Rule not found")
    engine.rules[rule_id].enabled = enabled
    engine._save()
    return {"status": "updated", "enabled": enabled}


@router.post("/test-trigger")
async def test_trigger_alert(
    request: Request,
    user: User = Depends(get_current_user),
):
    engine = request.app.state.alert_engine
    test_intel = {
        "id": "test-" + __import__('hashlib').md5(__import__('datetime').datetime.now().isoformat().encode()).hexdigest()[:8],
        "content": "检测到新的零日漏洞CVE-2025-0001，已被APT组织在暗网出售利用工具",
        "threat_level": "critical",
        "entity_type": "vulnerability",
        "value": "CVE-2025-0001",
    }
    alerts = await engine.evaluate_intelligence(test_intel, skip_cooldown=True)
    return {"triggered_alerts": len(alerts), "alerts": [a.to_dict() for a in alerts]}
