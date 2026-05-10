from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class IntelligenceSource(str, Enum):
    TELEGRAM = "telegram"
    FORUM = "forum"
    WECHAT = "wechat"
    DARKWEB = "darkweb"
    QQ_GROUP = "qq_group"
    WEIBO = "weibo"
    OTHER = "other"


class ThreatLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IntelligenceStatus(str, Enum):
    RAW = "raw"
    CLEANED = "cleaned"
    ANALYZED = "analyzed"
    REPORTED = "reported"


def _new_id() -> str:
    return uuid4().hex


class RawIntelligence(BaseModel):
    id: str = Field(default_factory=_new_id)
    source: IntelligenceSource
    source_url: Optional[str] = None
    content: str
    raw_content: Optional[str] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CleanedIntelligence(BaseModel):
    id: str = Field(default_factory=_new_id)
    raw_id: str
    content: str
    decoded_content: Optional[str] = None
    blacktalk_terms: Dict[str, str] = Field(default_factory=dict)
    entities: List[str] = Field(default_factory=list)
    threat_level: ThreatLevel = ThreatLevel.INFO
    cleaned_at: datetime = Field(default_factory=datetime.utcnow)


class AnalyzedIntelligence(BaseModel):
    id: str = Field(default_factory=_new_id)
    cleaned_id: str
    threat_level: ThreatLevel = ThreatLevel.INFO
    threat_categories: List[str] = Field(default_factory=list)
    attack_patterns: List[str] = Field(default_factory=list)
    technique_chain: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    analysis_summary: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class IntelligenceReport(BaseModel):
    id: str = Field(default_factory=_new_id)
    pir_id: Optional[str] = None
    title: str
    summary: str = ""
    key_findings: List[str] = Field(default_factory=list)
    threat_actors: List[str] = Field(default_factory=list)
    iocs: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_chain: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
