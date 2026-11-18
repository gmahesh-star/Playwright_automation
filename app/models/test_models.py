"""SQLAlchemy ORM models for the testing platform.

Uses portable types (String + JSON) so the same models work with
SQLite (local dev) and PostgreSQL (production) without changes.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ── Portable UUID type (works on SQLite + PostgreSQL) ───────────────


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Stores as a 36-char string on SQLite, native UUID on PostgreSQL.
    """

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(value))

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


# ── Enums ───────────────────────────────────────────────────────────────


class BrowserType(str, enum.Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── Models ──────────────────────────────────────────────────────────────


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    suites: Mapped[list[TestSuite]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    auth_profiles: Mapped[list[AuthProfile]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )


class TestSuite(Base):
    __tablename__ = "test_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    project: Mapped[Project] = relationship(back_populates="suites")
    test_cases: Mapped[list[TestCase]] = relationship(
        back_populates="suite", cascade="all, delete-orphan", lazy="selectin"
    )
    runs: Mapped[list[TestRun]] = relationship(
        back_populates="suite", cascade="all, delete-orphan", lazy="selectin"
    )


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured test definition stored as JSON
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    assertions: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    # Device / context configuration
    device_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Network mock rules
    mock_rules: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    # Auth profile reference
    auth_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("auth_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Baseline screenshots for visual regression (mapping of step_index → artifact path)
    baseline_screenshots: Mapped[dict[str, str] | None] = mapped_column(
        JSON, nullable=True, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    suite: Mapped[TestSuite] = relationship(back_populates="test_cases")
    auth_profile: Mapped[AuthProfile | None] = relationship(lazy="selectin")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, name="run_status", create_constraint=True),
        default=RunStatus.PENDING,
    )
    browser: Mapped[BrowserType] = mapped_column(
        SAEnum(BrowserType, name="browser_type", create_constraint=True),
        default=BrowserType.CHROMIUM,
    )

    # Per-test-case execution results
    results: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Artifact paths
    trace_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Webhook / CI metadata
    trigger_source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    suite: Mapped[TestSuite] = relationship(back_populates="runs")


class AuthProfile(Base):
    __tablename__ = "auth_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Serialised Playwright storage_state (cookies + localStorage)
    storage_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Path to the saved JSON file on disk
    storage_state_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    project: Mapped[Project] = relationship(back_populates="auth_profiles")
