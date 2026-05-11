"""
Alert Engine — Real-time threat intelligence alert system.
Monitors incoming intelligence, triggers alerts based on rules,
and dispatches notifications via multiple channels.
"""
import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class AlertRule:
    rule_id: str
    name: str
    description: str
    conditions: Dict
    severity: str = "high"
    enabled: bool = True
    cooldown_minutes: int = 60
    last_triggered: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Alert:
    alert_id: str
    rule_id: str
    rule_name: str
    severity: str
    title: str
    description: str
    intelligence_id: str
    entity_value: str
    entity_type: str
    threat_level: str
    timestamp: str
    acknowledged: bool = False
    notification_sent: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class AlertEngine:
    def __init__(self, persist_dir: str = "./alert_data"):
        self.persist_dir = persist_dir
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.notification_channels: Dict[str, Callable] = {}
        self._load()
        self._init_default_rules()

    def _init_default_rules(self):
        defaults = [
            AlertRule("rule-critical-threat", "高危威胁检测", "检测到critical级别威胁情报",
                      {"threat_level": "critical"}, "critical", True, 30),
            AlertRule("rule-zero-day", "零日漏洞检测", "检测到零日漏洞相关情报",
                      {"keyword": "0day,zero-day,零日,CVE-2024,CVE-2025"}, "critical", True, 60),
            AlertRule("rule-ransomware", "勒索软件检测", "检测到勒索软件相关情报",
                      {"keyword": "ransomware,勒索,LockBit,BlackCat,ALPHV"}, "high", True, 120),
            AlertRule("rule-apt", "APT攻击检测", "检测到APT组织活动",
                      {"keyword": "APT,advanced persistent threat,国家级攻击"}, "high", True, 240),
            AlertRule("rule-supply-chain", "供应链攻击检测", "检测到供应链攻击",
                      {"keyword": "supply chain,供应链,dependency"}, "high", True, 120),
            AlertRule("rule-darkweb-sale", "暗网交易检测", "检测到暗网数据/工具出售",
                      {"keyword": "暗网,darknet,sale,出售,贩卖"}, "medium", True, 180),
            AlertRule("rule-data-breach", "数据泄露检测", "检测到数据泄露事件",
                      {"keyword": "data breach,数据泄露,信息泄露"}, "high", True, 60),
            AlertRule("rule-botnet", "僵尸网络检测", "检测到僵尸网络活动",
                      {"keyword": "botnet,僵尸网络,C2,command and control"}, "medium", True, 240),
        ]
        for rule in defaults:
            if rule.rule_id not in self.rules:
                self.rules[rule.rule_id] = rule

    def register_notification_channel(self, name: str, handler: Callable):
        self.notification_channels[name] = handler

    async def evaluate_intelligence(self, intel_data: Dict, skip_cooldown: bool = False) -> List[Alert]:
        triggered_alerts = []
        content = intel_data.get("content", "")
        threat_level = intel_data.get("threat_level", "info")
        entity_type = intel_data.get("entity_type", "")
        intel_id = intel_data.get("id", "")
        entity_value = intel_data.get("value", intel_data.get("title", ""))

        for rule in self.rules.values():
            if not rule.enabled:
                continue
            if not skip_cooldown and self._is_in_cooldown(rule):
                continue
            if self._matches_rule(rule, content, threat_level, entity_type):
                alert = Alert(
                    alert_id=hashlib.md5(f"{rule.rule_id}:{intel_id}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16],
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    title=f"[{rule.name}] {entity_value[:50]}",
                    description=f"规则'{rule.name}'触发: {content[:100]}",
                    intelligence_id=intel_id,
                    entity_value=entity_value,
                    entity_type=entity_type,
                    threat_level=threat_level,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                self.active_alerts[alert.alert_id] = alert
                self.alert_history.append(alert)
                rule.last_triggered = datetime.now(timezone.utc).isoformat()
                triggered_alerts.append(alert)
                await self._dispatch_notifications(alert)

        if triggered_alerts:
            self._save()
        return triggered_alerts

    def _is_in_cooldown(self, rule: AlertRule) -> bool:
        if not rule.last_triggered:
            return False
        try:
            last = datetime.fromisoformat(rule.last_triggered)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
            return elapsed < rule.cooldown_minutes
        except:
            return False

    def _matches_rule(self, rule: AlertRule, content: str, threat_level: str, entity_type: str) -> bool:
        conditions = rule.conditions
        if "threat_level" in conditions:
            if threat_level != conditions["threat_level"]:
                return False
        if "entity_type" in conditions:
            if entity_type != conditions["entity_type"]:
                return False
        if "keyword" in conditions:
            keywords = [k.strip() for k in conditions["keyword"].split(",")]
            content_lower = content.lower()
            if not any(kw.lower() in content_lower for kw in keywords):
                return False
        return True

    async def _dispatch_notifications(self, alert: Alert):
        for channel_name, handler in self.notification_channels.items():
            try:
                result = handler(alert)
                if hasattr(result, '__await__'):
                    result = await result
                alert.notification_sent[channel_name] = True
                logger.info(f"Alert notification sent via {channel_name}: {alert.title}")
            except Exception as e:
                alert.notification_sent[channel_name] = False
                logger.warning(f"Failed to send notification via {channel_name}: {e}")

    def acknowledge_alert(self, alert_id: str) -> bool:
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            self._save()
            return True
        return False

    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        alerts = list(self.active_alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_stats(self) -> Dict:
        active = list(self.active_alerts.values())
        return {
            "total_alerts": len(self.alert_history),
            "active_alerts": len(active),
            "acknowledged": sum(1 for a in active if a.acknowledged),
            "by_severity": {
                "critical": sum(1 for a in active if a.severity == "critical"),
                "high": sum(1 for a in active if a.severity == "high"),
                "medium": sum(1 for a in active if a.severity == "medium"),
                "low": sum(1 for a in active if a.severity == "low"),
            },
            "rules_total": len(self.rules),
            "rules_enabled": sum(1 for r in self.rules.values() if r.enabled),
        }

    def _save(self):
        os.makedirs(self.persist_dir, exist_ok=True)
        data = {
            "rules": {k: v.to_dict() for k, v in self.rules.items()},
            "active_alerts": {k: v.to_dict() for k, v in self.active_alerts.items()},
            "alert_history": [a.to_dict() for a in self.alert_history[-500:]],
        }
        with open(os.path.join(self.persist_dir, "alerts.json"), "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        path = os.path.join(self.persist_dir, "alerts.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                for k, v in data.get("rules", {}).items():
                    self.rules[k] = AlertRule(**v)
                for k, v in data.get("active_alerts", {}).items():
                    self.active_alerts[k] = Alert(**v)
                self.alert_history = [Alert(**a) for a in data.get("alert_history", [])]
                logger.info(f"AlertEngine loaded: {len(self.rules)} rules, {len(self.active_alerts)} active alerts")
            except Exception as e:
                logger.warning(f"Failed to load alert data: {e}")
