"""
Phase 2 SQLAlchemy ORM models.

New tables for authentication, workflow management, marketplace, and collaboration.
All sensitive values are stored with an `_encrypted` suffix.
All timestamps are timezone-aware UTC via _utcnow().

DO NOT modify Phase 1 tables defined in models.py.
"""
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


# ── 1. Users (Authentication) ──────────────────────────────────────────────────

class User(Base):
    """Core authentication table. Stores credentials and account state."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    password_hash_bcrypt: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    workflows: Mapped[list["Workflow"]] = relationship(
        "Workflow", back_populates="owner", cascade="all, delete-orphan"
    )
    oauth_connections: Mapped[list["OAuthConnection"]] = relationship(
        "OAuthConnection", back_populates="user", cascade="all, delete-orphan"
    )
    secrets: Mapped[list["Secret"]] = relationship(
        "Secret", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="user", cascade="all, delete-orphan"
    )
    marketplace_listings: Mapped[list["WorkflowMarketplace"]] = relationship(
        "WorkflowMarketplace", back_populates="publisher", cascade="all, delete-orphan"
    )
    marketplace_reviews: Mapped[list["MarketplaceReview"]] = relationship(
        "MarketplaceReview", back_populates="reviewer", cascade="all, delete-orphan"
    )
    workflow_shares_owned: Mapped[list["WorkflowShare"]] = relationship(
        "WorkflowShare", foreign_keys="WorkflowShare.owner_id", back_populates="owner"
    )
    workflow_shares_received: Mapped[list["WorkflowShare"]] = relationship(
        "WorkflowShare", foreign_keys="WorkflowShare.shared_with_user_id", back_populates="shared_with_user"
    )
    workflow_history: Mapped[list["WorkflowHistory"]] = relationship(
        "WorkflowHistory", back_populates="user", cascade="all, delete-orphan"
    )
    authored_templates: Mapped[list["WorkflowTemplate"]] = relationship(
        "WorkflowTemplate", back_populates="author"
    )

    __table_args__ = (
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
    )


# ── 2. Refresh Tokens ──────────────────────────────────────────────────────────

class RefreshToken(Base):
    """JWT refresh tokens. Supports rotation and per-device revocation."""
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    device_info: Mapped[str] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_user_expires", "user_id", "expires_at"),
    )


# ── 3. Workflows ───────────────────────────────────────────────────────────────

class Workflow(Base):
    """
    Top-level workflow definition owned by a user.
    Actual step definitions live in WorkflowVersion for full version history.
    """
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    natural_language_request: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Pointer to the current canonical version; set after first version is created
    current_version_id: Mapped[int] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="")       # JSON array string
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="workflows")
    versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion", back_populates="workflow",
        cascade="all, delete-orphan",
        foreign_keys="WorkflowVersion.workflow_id",
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="workflow", cascade="all, delete-orphan"
    )
    marketplace_listing: Mapped["WorkflowMarketplace"] = relationship(
        "WorkflowMarketplace", back_populates="workflow", uselist=False
    )
    shares: Mapped[list["WorkflowShare"]] = relationship(
        "WorkflowShare", back_populates="workflow", cascade="all, delete-orphan"
    )
    variables: Mapped[list["WorkflowVariable"]] = relationship(
        "WorkflowVariable", back_populates="workflow", cascade="all, delete-orphan"
    )
    history: Mapped[list["WorkflowHistory"]] = relationship(
        "WorkflowHistory", back_populates="workflow", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_workflows_user_active", "user_id", "is_active"),
        Index("ix_workflows_category", "category"),
        Index("ix_workflows_is_public", "is_public"),
        Index("ix_workflows_created_at", "created_at"),
    )


# ── 4. Workflow Versions ───────────────────────────────────────────────────────

class WorkflowVersion(Base):
    """
    Immutable versioned snapshot of a workflow definition.
    New edits create a new version; old ones are never mutated.
    """
    __tablename__ = "workflow_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    definition_json: Mapped[str] = mapped_column(Text, nullable=False)   # Full workflow DAG / steps
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow", back_populates="versions", foreign_keys=[workflow_id]
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_workflow_version"),
        Index("ix_workflow_versions_workflow_current", "workflow_id", "is_current"),
    )


# ── 5. Execution Logs ──────────────────────────────────────────────────────────

class ExecutionLog(Base):
    """
    Per-step execution detail for a workflow run.
    Links to workflow_runs.id from Phase 1.
    """
    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # References workflow_runs(id) — no FK constraint to avoid cross-module coupling
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    input_json: Mapped[str] = mapped_column(Text, nullable=True)
    output_json: Mapped[str] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_execution_logs_run_step", "run_id", "step_index"),
        Index("ix_execution_logs_status", "status"),
        Index("ix_execution_logs_started_at", "started_at"),
    )


# ── 6. Plugins ─────────────────────────────────────────────────────────────────

class Plugin(Base):
    """Registry of available action plugins (built-in and user-installed)."""
    __tablename__ = "plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plugin_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    author: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")    # JSON array of action names
    params_schema_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON Schema
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_plugins_is_enabled", "is_enabled"),
        Index("ix_plugins_is_builtin", "is_builtin"),
    )


# ── 7. OAuth Connections ───────────────────────────────────────────────────────

class OAuthConnection(Base):
    """Per-user OAuth provider tokens. Tokens stored encrypted at rest."""
    __tablename__ = "oauth_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)   # google, github, slack, etc.
    provider_user_id: Mapped[str] = mapped_column(String(256), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")  # space-separated scope list
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="oauth_connections")

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_oauth_connections_user_provider"),
        Index("ix_oauth_connections_provider", "provider"),
        Index("ix_oauth_connections_is_active", "is_active"),
    )


# ── 8. Secrets ─────────────────────────────────────────────────────────────────

class Secret(Base):
    """Encrypted named secrets per user (API keys, passwords, tokens)."""
    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="secrets")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_secrets_user_name"),
        Index("ix_secrets_user_active", "user_id", "is_active"),
    )


# ── 9. Schedules ───────────────────────────────────────────────────────────────

class Schedule(Base):
    """
    Cron-based schedule definitions attached to a workflow.
    Replaces the simpler interval-only approach in scheduled_workflows (Phase 1).
    """
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    misfire_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="skip")  # skip | run_once | run_all
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="schedules")
    user: Mapped["User"] = relationship("User", back_populates="schedules")

    __table_args__ = (
        Index("ix_schedules_active_next_run", "is_active", "next_run_at"),
    )


# ── 10. Notifications ──────────────────────────────────────────────────────────

class Notification(Base):
    """In-app notification inbox per user."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="info")  # success|failure|warning|info
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Nullable FK — notification may not be tied to a specific run
    run_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
        Index("ix_notifications_type", "type"),
    )


# ── 11. Workflow Templates ─────────────────────────────────────────────────────

class WorkflowTemplate(Base):
    """
    Curated, platform-managed workflow templates.
    Unlike user workflows, templates are editorially reviewed and may be featured.
    """
    __tablename__ = "workflow_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    definition_json: Mapped[str] = mapped_column(Text, nullable=False)
    preview_image_url: Mapped[str] = mapped_column(String(512), nullable=True)
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="")  # JSON array string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="authored_templates")

    __table_args__ = (
        Index("ix_workflow_templates_category", "category"),
        Index("ix_workflow_templates_featured", "is_featured"),
        Index("ix_workflow_templates_use_count", "use_count"),
    )


# ── 12. Workflow Marketplace ───────────────────────────────────────────────────

class WorkflowMarketplace(Base):
    """Published marketplace listings backed by a user-owned workflow."""
    __tablename__ = "workflow_marketplace"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 = free
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="marketplace_listing")
    publisher: Mapped["User"] = relationship("User", back_populates="marketplace_listings")
    reviews: Mapped[list["MarketplaceReview"]] = relationship(
        "MarketplaceReview", back_populates="listing", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_marketplace_approved", "is_approved"),
        Index("ix_marketplace_rating_avg", "rating_avg"),
        Index("ix_marketplace_downloads", "downloads"),
        Index("ix_marketplace_price", "price"),
    )


# ── 13. Marketplace Reviews ────────────────────────────────────────────────────

class MarketplaceReview(Base):
    """User reviews for marketplace listings. One review per user per listing."""
    __tablename__ = "marketplace_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    marketplace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_marketplace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    review_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    listing: Mapped["WorkflowMarketplace"] = relationship("WorkflowMarketplace", back_populates="reviews")
    reviewer: Mapped["User"] = relationship("User", back_populates="marketplace_reviews")

    __table_args__ = (
        UniqueConstraint("marketplace_id", "reviewer_id", name="uq_marketplace_reviews_listing_reviewer"),
        Index("ix_marketplace_reviews_rating", "rating"),
    )


# ── 14. Workflow Shares ────────────────────────────────────────────────────────

class WorkflowShare(Base):
    """
    Sharing and collaboration records.
    Supports both named-user sharing and public token-based sharing.
    """
    __tablename__ = "workflow_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Null = public share via token only
    shared_with_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    share_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    permission: Mapped[str] = mapped_column(String(16), nullable=False, default="view")  # view|edit|run
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="shares")
    owner: Mapped["User"] = relationship(
        "User", foreign_keys=[owner_id], back_populates="workflow_shares_owned"
    )
    shared_with_user: Mapped["User"] = relationship(
        "User", foreign_keys=[shared_with_user_id], back_populates="workflow_shares_received"
    )

    __table_args__ = (
        Index("ix_workflow_shares_workflow_active", "workflow_id", "is_active"),
        Index("ix_workflow_shares_expires_at", "expires_at"),
    )


# ── 15. Workflow Variables ─────────────────────────────────────────────────────

class WorkflowVariable(Base):
    """Named variables scoped to a workflow. Secrets are flagged and stored encrypted."""
    __tablename__ = "workflow_variables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False, default="null")
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="variables")

    __table_args__ = (
        UniqueConstraint("workflow_id", "name", name="uq_workflow_variables_workflow_name"),
        Index("ix_workflow_variables_is_secret", "is_secret"),
    )


# ── 16. Workflow History ───────────────────────────────────────────────────────

class WorkflowHistory(Base):
    """Immutable audit trail of all actions performed on a workflow."""
    __tablename__ = "workflow_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # created|updated|deleted|executed|shared
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="history")
    user: Mapped["User"] = relationship("User", back_populates="workflow_history")

    __table_args__ = (
        Index("ix_workflow_history_workflow_created", "workflow_id", "created_at"),
        Index("ix_workflow_history_action", "action"),
        Index("ix_workflow_history_created_at", "created_at"),
    )
