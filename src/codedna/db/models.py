"""SQLAlchemy ORM models for CodeDNA."""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, Integer, Float, LargeBinary, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid4()).lower()


def utc_now() -> int:
    return int(datetime.utcnow().timestamp())


class Repo(Base):
    __tablename__ = "repos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="python")
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
    deleted_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Fingerprint(Base):
    __tablename__ = "fingerprints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    vector_dims: Mapped[int] = mapped_column(Integer, nullable=False, default=32)
    model_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    commit_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    commit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    build_duration_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
    deleted_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=True)
    __table_args__ = (Index("idx_fingerprints_repo", "repo_id", "is_active"),)


class FeatureVector(Base):
    __tablename__ = "feature_vectors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fingerprint_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    vector_dims: Mapped[int] = mapped_column(Integer, nullable=False, default=32)
    body_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    line_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    line_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
    deleted_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    __table_args__ = (Index("idx_fv_repo_file", "repo_id", "file_path"), Index("idx_fv_fingerprint", "fingerprint_id"))


class ScanResult(Base):
    __tablename__ = "scan_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fingerprint_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    dna_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    degraded: Mapped[bool] = mapped_column(Integer, nullable=False, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
    __table_args__ = (Index("idx_scan_results_repo_time", "repo_id", "created_at"),)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
    __table_args__ = (Index("idx_jobs_repo_status", "repo_id", "status"),)


class Config(Base):
    __tablename__ = "config"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=utc_now)
