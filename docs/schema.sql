-- =============================================================================
-- AI Workflow Automation Platform — Complete Database Schema
-- =============================================================================
-- SQLite-compatible DDL (fully portable to PostgreSQL with minor type changes).
-- Existing Phase 1 tables are included as reference (CREATE TABLE IF NOT EXISTS).
-- Phase 2 new tables follow.
--
-- Conventions:
--   • All timestamps: TEXT storing ISO-8601 UTC (SQLite) / TIMESTAMPTZ (PG)
--   • Sensitive columns: suffixed with _encrypted
--   • Boolean: INTEGER 0/1 (SQLite) / BOOLEAN (PG)
--   • JSON values: stored as TEXT
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- =============================================================================
-- PHASE 1 TABLES (existing — do not modify)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- workflow_runs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_runs (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT, -- surrogate PK
    user_id                  TEXT    NOT NULL,                   -- owning user (string ID from auth)
    request_text             TEXT    NOT NULL,                   -- raw user request
    interpreted_instructions TEXT    NOT NULL,                   -- AI-parsed instructions
    workflow_payload         TEXT    NOT NULL,                   -- full workflow JSON
    execution_status         TEXT    NOT NULL DEFAULT 'pending', -- pending|running|success|failure
    execution_output         TEXT    NOT NULL DEFAULT '',        -- stdout / result text
    delivery_status          TEXT    NOT NULL DEFAULT 'pending', -- pending|sent|failed
    created_at               TEXT    NOT NULL,                   -- ISO-8601 UTC
    updated_at               TEXT    NOT NULL,                   -- ISO-8601 UTC
    scheduled_workflow_id    INTEGER                             -- FK to scheduled_workflows (nullable)
);

CREATE INDEX IF NOT EXISTS ix_workflow_runs_user_id            ON workflow_runs (user_id);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_execution_status   ON workflow_runs (execution_status);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_created_at         ON workflow_runs (created_at);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_scheduled_wf       ON workflow_runs (scheduled_workflow_id);

-- -----------------------------------------------------------------------------
-- idempotency_records
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS idempotency_records (
    id             INTEGER PRIMARY KEY AUTOINCREMENT, -- surrogate PK
    key            TEXT    NOT NULL UNIQUE,           -- idempotency key (client-supplied)
    user_id        TEXT    NOT NULL,                  -- owning user
    run_id         INTEGER NOT NULL,                  -- corresponding workflow_run
    correlation_id TEXT    NOT NULL,                  -- request correlation ID
    created_at     TEXT    NOT NULL                   -- ISO-8601 UTC
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_idempotency_records_key    ON idempotency_records (key);
CREATE        INDEX IF NOT EXISTS ix_idempotency_records_user   ON idempotency_records (user_id);
CREATE        INDEX IF NOT EXISTS ix_idempotency_records_run    ON idempotency_records (run_id);
CREATE        INDEX IF NOT EXISTS ix_idempotency_records_corr   ON idempotency_records (correlation_id);

-- -----------------------------------------------------------------------------
-- scheduled_workflows
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scheduled_workflows (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  TEXT    NOT NULL,
    name                     TEXT    NOT NULL,
    description              TEXT    NOT NULL DEFAULT '',
    request_text             TEXT    NOT NULL,
    schedule_type            TEXT    NOT NULL DEFAULT 'interval', -- interval|cron
    schedule_value           TEXT    NOT NULL DEFAULT 'every_day',
    delivery_channels        TEXT    NOT NULL DEFAULT 'dashboard',
    delivery_email           TEXT    NOT NULL DEFAULT '',
    user_context_encrypted   TEXT    NOT NULL DEFAULT '',         -- encrypted JSON
    is_active                INTEGER NOT NULL DEFAULT 1,
    last_run_at              TEXT,                                 -- ISO-8601 UTC nullable
    next_run_at              TEXT,                                 -- ISO-8601 UTC nullable
    total_runs               INTEGER NOT NULL DEFAULT 0,
    last_status              TEXT    NOT NULL DEFAULT 'pending',
    created_at               TEXT    NOT NULL,
    updated_at               TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_scheduled_workflows_user_id    ON scheduled_workflows (user_id);
CREATE INDEX IF NOT EXISTS ix_scheduled_workflows_is_active  ON scheduled_workflows (is_active);
CREATE INDEX IF NOT EXISTS ix_scheduled_workflows_next_run   ON scheduled_workflows (next_run_at);

-- -----------------------------------------------------------------------------
-- user_profiles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profiles (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                     TEXT    NOT NULL UNIQUE,  -- matches auth user string ID
    display_name                TEXT    NOT NULL DEFAULT '',
    company                     TEXT    NOT NULL DEFAULT '',
    email_encrypted             TEXT    NOT NULL DEFAULT '',
    smtp_host_encrypted         TEXT    NOT NULL DEFAULT '',
    smtp_port                   INTEGER NOT NULL DEFAULT 587,
    smtp_user_encrypted         TEXT    NOT NULL DEFAULT '',
    smtp_pass_encrypted         TEXT    NOT NULL DEFAULT '',
    slack_webhook_encrypted     TEXT    NOT NULL DEFAULT '',
    custom_api_url_encrypted    TEXT    NOT NULL DEFAULT '',
    custom_api_key_encrypted    TEXT    NOT NULL DEFAULT '',
    custom_api_headers_encrypted TEXT   NOT NULL DEFAULT '',
    extra_context_encrypted     TEXT    NOT NULL DEFAULT '',
    created_at                  TEXT    NOT NULL,
    updated_at                  TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_user_id ON user_profiles (user_id);

-- -----------------------------------------------------------------------------
-- leetcode_students
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leetcode_students (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username  TEXT    NOT NULL UNIQUE,
    real_name TEXT    NOT NULL DEFAULT '',
    batch     TEXT    NOT NULL DEFAULT 'default',
    added_at  TEXT    NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_leetcode_students_username ON leetcode_students (username);
CREATE        INDEX IF NOT EXISTS ix_leetcode_students_batch    ON leetcode_students (batch);

-- -----------------------------------------------------------------------------
-- leetcode_reports
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leetcode_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    batch        TEXT    NOT NULL DEFAULT 'default',
    report_json  TEXT    NOT NULL,
    generated_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_leetcode_reports_batch        ON leetcode_reports (batch);
CREATE INDEX IF NOT EXISTS ix_leetcode_reports_generated_at ON leetcode_reports (generated_at);

-- =============================================================================
-- PHASE 2 TABLES (new)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. users — Authentication and account state
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    email                   TEXT    NOT NULL UNIQUE,       -- login identifier
    password_hash_bcrypt    TEXT    NOT NULL,              -- bcrypt hash, never plaintext
    role                    TEXT    NOT NULL DEFAULT 'user', -- user|admin|moderator
    is_active               INTEGER NOT NULL DEFAULT 1,    -- soft-disable without deleting
    email_verified          INTEGER NOT NULL DEFAULT 0,    -- 0 until verification link clicked
    last_login_at           TEXT,                          -- ISO-8601 UTC, nullable
    failed_login_attempts   INTEGER NOT NULL DEFAULT 0,    -- brute-force counter
    locked_until            TEXT,                          -- account lockout expiry, nullable
    created_at              TEXT    NOT NULL,
    updated_at              TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email     ON users (email);
CREATE        INDEX IF NOT EXISTS ix_users_role      ON users (role);
CREATE        INDEX IF NOT EXISTS ix_users_is_active ON users (is_active);

-- -----------------------------------------------------------------------------
-- 2. refresh_tokens — JWT refresh token store with rotation support
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash  TEXT    NOT NULL UNIQUE,               -- SHA-256 of the raw token
    expires_at  TEXT    NOT NULL,                      -- ISO-8601 UTC
    revoked_at  TEXT,                                  -- set on revocation, nullable
    device_info TEXT,                                  -- UA string / device label, nullable
    created_at  TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash      ON refresh_tokens (token_hash);
CREATE        INDEX IF NOT EXISTS ix_refresh_tokens_user_id         ON refresh_tokens (user_id);
CREATE        INDEX IF NOT EXISTS ix_refresh_tokens_user_expires    ON refresh_tokens (user_id, expires_at);

-- -----------------------------------------------------------------------------
-- 3. workflows — Top-level workflow definitions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflows (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name                     TEXT    NOT NULL,
    description              TEXT    NOT NULL DEFAULT '',
    natural_language_request TEXT    NOT NULL DEFAULT '',  -- original user prompt
    current_version_id       INTEGER,                      -- FK to workflow_versions (set post-insert)
    is_active                INTEGER NOT NULL DEFAULT 1,
    is_template              INTEGER NOT NULL DEFAULT 0,   -- user-marked as reusable template
    is_public                INTEGER NOT NULL DEFAULT 0,   -- visible in marketplace/discovery
    tags                     TEXT    NOT NULL DEFAULT '[]', -- JSON array of tag strings
    category                 TEXT    NOT NULL DEFAULT '',
    total_runs               INTEGER NOT NULL DEFAULT 0,
    last_run_at              TEXT,                          -- ISO-8601 UTC nullable
    last_run_status          TEXT,                          -- success|failure|running nullable
    created_at               TEXT    NOT NULL,
    updated_at               TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_workflows_user_id       ON workflows (user_id);
CREATE INDEX IF NOT EXISTS ix_workflows_user_active   ON workflows (user_id, is_active);
CREATE INDEX IF NOT EXISTS ix_workflows_category      ON workflows (category);
CREATE INDEX IF NOT EXISTS ix_workflows_is_public     ON workflows (is_public);
CREATE INDEX IF NOT EXISTS ix_workflows_created_at    ON workflows (created_at);

-- -----------------------------------------------------------------------------
-- 4. workflow_versions — Immutable versioned snapshots
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id     INTEGER NOT NULL REFERENCES workflows (id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL DEFAULT 1,            -- monotonically increasing per workflow
    definition_json TEXT    NOT NULL,                      -- full DAG / step array as JSON
    change_summary  TEXT    NOT NULL DEFAULT '',           -- human-written commit message
    created_by      INTEGER REFERENCES users (id) ON DELETE SET NULL, -- who made this version
    is_current      INTEGER NOT NULL DEFAULT 0,            -- 1 = active version
    created_at      TEXT    NOT NULL,
    UNIQUE (workflow_id, version_number)                   -- no duplicate version numbers per workflow
);

CREATE INDEX IF NOT EXISTS ix_workflow_versions_workflow_id      ON workflow_versions (workflow_id);
CREATE INDEX IF NOT EXISTS ix_workflow_versions_created_by       ON workflow_versions (created_by);
CREATE INDEX IF NOT EXISTS ix_workflow_versions_workflow_current ON workflow_versions (workflow_id, is_current);

-- -----------------------------------------------------------------------------
-- 5. execution_logs — Per-step execution detail
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL,                -- references workflow_runs(id); no FK for loose coupling
    step_index    INTEGER NOT NULL DEFAULT 0,      -- zero-based position in the workflow
    step_name     TEXT    NOT NULL DEFAULT '',
    action        TEXT    NOT NULL DEFAULT '',     -- plugin action invoked
    status        TEXT    NOT NULL DEFAULT 'pending', -- pending|running|success|failure|skipped
    started_at    TEXT,                            -- ISO-8601 UTC nullable
    finished_at   TEXT,                            -- ISO-8601 UTC nullable
    input_json    TEXT,                            -- serialised step input
    output_json   TEXT,                            -- serialised step output
    error_message TEXT,                            -- first error if status=failure
    retry_count   INTEGER NOT NULL DEFAULT 0,
    duration_ms   INTEGER                          -- wall-clock milliseconds, nullable
);

CREATE INDEX IF NOT EXISTS ix_execution_logs_run_id    ON execution_logs (run_id);
CREATE INDEX IF NOT EXISTS ix_execution_logs_run_step  ON execution_logs (run_id, step_index);
CREATE INDEX IF NOT EXISTS ix_execution_logs_status    ON execution_logs (status);
CREATE INDEX IF NOT EXISTS ix_execution_logs_started   ON execution_logs (started_at);

-- -----------------------------------------------------------------------------
-- 6. plugins — Action plugin registry
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plugins (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_id          TEXT    NOT NULL UNIQUE,          -- stable machine identifier e.g. "send_email_v1"
    display_name       TEXT    NOT NULL,
    description        TEXT    NOT NULL DEFAULT '',
    version            TEXT    NOT NULL DEFAULT '1.0.0', -- semver string
    author             TEXT    NOT NULL DEFAULT '',
    actions_json       TEXT    NOT NULL DEFAULT '[]',    -- JSON array of action descriptor objects
    params_schema_json TEXT    NOT NULL DEFAULT '{}',    -- JSON Schema for parameter validation
    is_enabled         INTEGER NOT NULL DEFAULT 1,
    is_builtin         INTEGER NOT NULL DEFAULT 0,       -- 1 = shipped with platform, not user-installed
    installed_at       TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_plugins_plugin_id   ON plugins (plugin_id);
CREATE        INDEX IF NOT EXISTS ix_plugins_is_enabled  ON plugins (is_enabled);
CREATE        INDEX IF NOT EXISTS ix_plugins_is_builtin  ON plugins (is_builtin);

-- -----------------------------------------------------------------------------
-- 7. oauth_connections — OAuth provider tokens per user
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS oauth_connections (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    provider                 TEXT    NOT NULL,                     -- google|github|slack|microsoft|etc
    provider_user_id         TEXT    NOT NULL,                     -- provider's opaque user ID
    access_token_encrypted   TEXT    NOT NULL,                     -- encrypted access token
    refresh_token_encrypted  TEXT,                                 -- encrypted refresh token, nullable
    token_expires_at         TEXT,                                 -- ISO-8601 UTC nullable
    scopes                   TEXT    NOT NULL DEFAULT '',          -- space-separated OAuth scopes
    is_active                INTEGER NOT NULL DEFAULT 1,
    created_at               TEXT    NOT NULL,
    updated_at               TEXT    NOT NULL,
    UNIQUE (user_id, provider)                                     -- one connection per provider per user
);

CREATE INDEX IF NOT EXISTS ix_oauth_connections_user_id    ON oauth_connections (user_id);
CREATE INDEX IF NOT EXISTS ix_oauth_connections_provider   ON oauth_connections (provider);
CREATE INDEX IF NOT EXISTS ix_oauth_connections_is_active  ON oauth_connections (is_active);

-- -----------------------------------------------------------------------------
-- 8. secrets — Encrypted named secrets per user
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS secrets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,                  -- e.g. "OPENAI_API_KEY"
    value_encrypted TEXT    NOT NULL,                  -- Fernet / AES-GCM ciphertext
    description     TEXT    NOT NULL DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_used_at    TEXT,                              -- ISO-8601 UTC nullable
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS ix_secrets_user_id     ON secrets (user_id);
CREATE INDEX IF NOT EXISTS ix_secrets_user_active ON secrets (user_id, is_active);

-- -----------------------------------------------------------------------------
-- 9. schedules — Cron-based schedule definitions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id     INTEGER NOT NULL REFERENCES workflows (id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    cron_expression TEXT    NOT NULL,                  -- standard 5-field cron, e.g. "0 9 * * 1"
    timezone        TEXT    NOT NULL DEFAULT 'UTC',    -- IANA timezone name
    is_active       INTEGER NOT NULL DEFAULT 1,
    next_run_at     TEXT,                              -- ISO-8601 UTC, updated by scheduler
    last_run_at     TEXT,                              -- ISO-8601 UTC nullable
    total_runs      INTEGER NOT NULL DEFAULT 0,
    misfire_policy  TEXT    NOT NULL DEFAULT 'skip',   -- skip|run_once|run_all
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_schedules_workflow_id       ON schedules (workflow_id);
CREATE INDEX IF NOT EXISTS ix_schedules_user_id           ON schedules (user_id);
CREATE INDEX IF NOT EXISTS ix_schedules_active_next_run   ON schedules (is_active, next_run_at);

-- -----------------------------------------------------------------------------
-- 10. notifications — In-app user notification inbox
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type       TEXT    NOT NULL DEFAULT 'info',  -- success|failure|warning|info
    title      TEXT    NOT NULL,
    message    TEXT    NOT NULL DEFAULT '',
    run_id     INTEGER,                          -- nullable soft-ref to workflow_runs(id)
    is_read    INTEGER NOT NULL DEFAULT 0,
    read_at    TEXT,                             -- ISO-8601 UTC nullable
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_id    ON notifications (user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_user_read  ON notifications (user_id, is_read);
CREATE INDEX IF NOT EXISTS ix_notifications_run_id     ON notifications (run_id);
CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at);
CREATE INDEX IF NOT EXISTS ix_notifications_type       ON notifications (type);

-- -----------------------------------------------------------------------------
-- 11. workflow_templates — Curated platform templates
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_templates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    description       TEXT    NOT NULL DEFAULT '',
    category          TEXT    NOT NULL DEFAULT '',
    definition_json   TEXT    NOT NULL,            -- full workflow definition
    preview_image_url TEXT,                        -- CDN URL for thumbnail, nullable
    author_id         INTEGER REFERENCES users (id) ON DELETE SET NULL,
    use_count         INTEGER NOT NULL DEFAULT 0,
    is_featured       INTEGER NOT NULL DEFAULT 0,  -- pinned on discovery page
    tags              TEXT    NOT NULL DEFAULT '[]', -- JSON array
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_workflow_templates_category  ON workflow_templates (category);
CREATE INDEX IF NOT EXISTS ix_workflow_templates_featured  ON workflow_templates (is_featured);
CREATE INDEX IF NOT EXISTS ix_workflow_templates_use_count ON workflow_templates (use_count);
CREATE INDEX IF NOT EXISTS ix_workflow_templates_author_id ON workflow_templates (author_id);

-- -----------------------------------------------------------------------------
-- 12. workflow_marketplace — Published marketplace listings
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_marketplace (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id  INTEGER NOT NULL UNIQUE REFERENCES workflows (id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title        TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT '',
    price        REAL    NOT NULL DEFAULT 0.0,     -- 0.0 = free; future: support paid listings
    downloads    INTEGER NOT NULL DEFAULT 0,
    rating_avg   REAL    NOT NULL DEFAULT 0.0,     -- recomputed after each new review
    rating_count INTEGER NOT NULL DEFAULT 0,
    is_approved  INTEGER NOT NULL DEFAULT 0,       -- admin approval gate
    published_at TEXT,                             -- ISO-8601 UTC nullable (set when approved)
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_marketplace_workflow_id  ON workflow_marketplace (workflow_id);
CREATE        INDEX IF NOT EXISTS ix_marketplace_user_id      ON workflow_marketplace (user_id);
CREATE        INDEX IF NOT EXISTS ix_marketplace_is_approved  ON workflow_marketplace (is_approved);
CREATE        INDEX IF NOT EXISTS ix_marketplace_rating_avg   ON workflow_marketplace (rating_avg);
CREATE        INDEX IF NOT EXISTS ix_marketplace_downloads    ON workflow_marketplace (downloads);
CREATE        INDEX IF NOT EXISTS ix_marketplace_price        ON workflow_marketplace (price);

-- -----------------------------------------------------------------------------
-- 13. marketplace_reviews — User reviews for marketplace listings
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_reviews (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    marketplace_id INTEGER NOT NULL REFERENCES workflow_marketplace (id) ON DELETE CASCADE,
    reviewer_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    rating         INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text    TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL,
    UNIQUE (marketplace_id, reviewer_id)           -- one review per user per listing
);

CREATE INDEX IF NOT EXISTS ix_marketplace_reviews_marketplace_id ON marketplace_reviews (marketplace_id);
CREATE INDEX IF NOT EXISTS ix_marketplace_reviews_reviewer_id    ON marketplace_reviews (reviewer_id);
CREATE INDEX IF NOT EXISTS ix_marketplace_reviews_rating         ON marketplace_reviews (rating);

-- -----------------------------------------------------------------------------
-- 14. workflow_shares — Sharing and collaboration records
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_shares (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id         INTEGER NOT NULL REFERENCES workflows (id) ON DELETE CASCADE,
    owner_id            INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    shared_with_user_id INTEGER REFERENCES users (id) ON DELETE CASCADE, -- null = public token share
    share_token         TEXT    NOT NULL UNIQUE,          -- random URL-safe token
    permission          TEXT    NOT NULL DEFAULT 'view',  -- view|edit|run
    expires_at          TEXT,                             -- ISO-8601 UTC nullable
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_workflow_shares_token         ON workflow_shares (share_token);
CREATE        INDEX IF NOT EXISTS ix_workflow_shares_workflow_id   ON workflow_shares (workflow_id);
CREATE        INDEX IF NOT EXISTS ix_workflow_shares_owner_id      ON workflow_shares (owner_id);
CREATE        INDEX IF NOT EXISTS ix_workflow_shares_shared_with   ON workflow_shares (shared_with_user_id);
CREATE        INDEX IF NOT EXISTS ix_workflow_shares_wf_active     ON workflow_shares (workflow_id, is_active);
CREATE        INDEX IF NOT EXISTS ix_workflow_shares_expires_at    ON workflow_shares (expires_at);

-- -----------------------------------------------------------------------------
-- 15. workflow_variables — Per-workflow named variables
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_variables (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL REFERENCES workflows (id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,                  -- variable name, e.g. "RETRY_LIMIT"
    value_json  TEXT    NOT NULL DEFAULT 'null',   -- JSON-encoded value (any type)
    is_secret   INTEGER NOT NULL DEFAULT 0,        -- 1 = value_json is encrypted ciphertext
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE (workflow_id, name)
);

CREATE INDEX IF NOT EXISTS ix_workflow_variables_workflow_id ON workflow_variables (workflow_id);
CREATE INDEX IF NOT EXISTS ix_workflow_variables_is_secret   ON workflow_variables (is_secret);

-- -----------------------------------------------------------------------------
-- 16. workflow_history — Immutable audit trail
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL REFERENCES workflows (id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    action      TEXT    NOT NULL,                  -- created|updated|deleted|executed|shared
    details_json TEXT   NOT NULL DEFAULT '{}',     -- structured change details
    ip_address  TEXT,                              -- client IP at time of action, nullable
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_workflow_history_workflow_id      ON workflow_history (workflow_id);
CREATE INDEX IF NOT EXISTS ix_workflow_history_user_id          ON workflow_history (user_id);
CREATE INDEX IF NOT EXISTS ix_workflow_history_workflow_created ON workflow_history (workflow_id, created_at);
CREATE INDEX IF NOT EXISTS ix_workflow_history_action           ON workflow_history (action);
CREATE INDEX IF NOT EXISTS ix_workflow_history_created_at       ON workflow_history (created_at);

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
