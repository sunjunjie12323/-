from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class RawIntelligenceTable(Base):
    __tablename__ = "raw_intelligence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="raw", index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    cleaned: Mapped["CleanedIntelligenceTable | None"] = relationship(
        "CleanedIntelligenceTable", back_populates="raw", uselist=False, lazy="selectin"
    )


class CleanedIntelligenceTable(Base):
    __tablename__ = "cleaned_intelligence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    raw_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("raw_intelligence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    decoded_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    blacktalk_terms_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    threat_level: Mapped[str] = mapped_column(String(16), nullable=False, default="info", index=True)
    cleaned_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), index=True
    )

    raw: Mapped["RawIntelligenceTable"] = relationship(
        "RawIntelligenceTable", back_populates="cleaned", lazy="selectin"
    )
    analyzed: Mapped["AnalyzedIntelligenceTable | None"] = relationship(
        "AnalyzedIntelligenceTable", back_populates="cleaned", uselist=False, lazy="selectin"
    )


class AnalyzedIntelligenceTable(Base):
    __tablename__ = "analyzed_intelligence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cleaned_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cleaned_intelligence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    threat_level: Mapped[str] = mapped_column(String(16), nullable=False, default="info", index=True)
    threat_categories_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    attack_patterns_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    technique_chain_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    analysis_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_refs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), index=True
    )

    cleaned: Mapped["CleanedIntelligenceTable"] = relationship(
        "CleanedIntelligenceTable", back_populates="analyzed", lazy="selectin"
    )


class EntityTable(Base):
    __tablename__ = "entity"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class RelationTable(Base):
    __tablename__ = "relation"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_entity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("entity.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("entity.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())


class PIRTable(Base):
    __tablename__ = "pir"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    results_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    tasks: Mapped[list["PIRTaskTable"]] = relationship(
        "PIRTaskTable", back_populates="pir", lazy="selectin", cascade="all, delete-orphan"
    )


class PIRTaskTable(Base):
    __tablename__ = "pir_task"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pir_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pir.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pir: Mapped["PIRTable"] = relationship("PIRTable", back_populates="tasks", lazy="selectin")


class ReportTable(Base):
    __tablename__ = "report"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    pir_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("pir.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    key_findings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    threat_actors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    iocs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    attack_chains_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_chain_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    author: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
