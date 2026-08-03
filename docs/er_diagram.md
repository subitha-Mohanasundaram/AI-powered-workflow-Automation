# AI Workflow Automation Platform — Entity Relationship Diagram

## Overview

The schema is split into two phases:

- **Phase 1** — Core workflow execution, scheduling, user profiles, and LeetCode tracker (existing tables, read-only reference).
- **Phase 2** — Authentication, versioned workflow management, marketplace, collaboration, and observability (new tables).

---

## ASCII ER Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          PHASE 1 (existing)                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

  ┌──────────────────────┐          ┌──────────────────────┐
  │    workflow_runs     │          │ scheduled_workflows  │
  ├──────────────────────┤          ├──────────────────────┤
  │ id (PK)              │◄────────┐│ id (PK)              │
  │ user_id              │         ││ user_id              │
  │ request_text         │         ││ name                 │
  │ interpreted_instruct.│         ││ schedule_type/value  │
  │ workflow_payload     │         ││ delivery_channels    │
  │ execution_status     │         ││ user_context_enc     │
  │ execution_output     │         ││ is_active            │
  │ delivery_status      │         ││ next_run_at          │
  │ scheduled_workflow_id│─────────┘│ last_run_at          │
  │ created_at           │          │ total_runs           │
  │ updated_at           │          └──────────────────────┘
  └──────────────────────┘

  ┌──────────────────────┐          ┌──────────────────────┐
  │ idempotency_records  │          │    user_profiles     │
  ├──────────────────────┤          ├──────────────────────┤
  │ id (PK)              │          │ id (PK)              │
  │ key (UNIQUE)         │          │ user_id (UNIQUE)     │
  │ user_id              │          │ display_name         │
  │ run_id               │          │ company              │
  │ correlation_id       │          │ email_encrypted      │
  │ created_at           │          │ smtp_*_encrypted     │
  └──────────────────────┘          │ slack_webhook_enc    │
                                    │ custom_api_*_enc     │
  ┌──────────────────────┐          └──────────────────────┘
  │  leetcode_students   │
  ├──────────────────────┤          ┌──────────────────────┐
  │ id (PK)              │          │  leetcode_reports    │
  │ username (UNIQUE)    │          ├──────────────────────┤
  │ real_name            │          │ id (PK)              │
  │ batch                │          │ batch                │
  │ added_at             │          │ report_json          │
  │ is_active            │          │ generated_at         │
  └──────────────────────┘          └──────────────────────┘

╔══════════════════════════════════════════════════════════════════════════════╗
║                          PHASE 2 (new)                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

                    ┌────────────────────────────┐
                    │           users            │
                    ├────────────────────────────┤
                    │ id (PK)                    │
                    │ email (UNIQUE)             │
                    │ password_hash_bcrypt       │
                    │ role                       │
                    │ is_active                  │
                    │ email_verified             │
                    │ last_login_at              │
                    │ failed_login_attempts      │
                    │ locked_until               │
                    │ created_at / updated_at    │
                    └─────────────┬──────────────┘
                                  │ 1
          ┌───────────────────────┼──────────────────────────────────┐
          │ N                     │ N                                │ N
          ▼                       ▼                                  ▼
  ┌──────────────────┐   ┌────────────────────┐           ┌────────────────────┐
  │  refresh_tokens  │   │     workflows      │           │  oauth_connections │
  ├──────────────────┤   ├────────────────────┤           ├────────────────────┤
  │ id (PK)          │   │ id (PK)            │           │ id (PK)            │
  │ user_id (FK)     │   │ user_id (FK)       │           │ user_id (FK)       │
  │ token_hash (UQ)  │   │ name               │           │ provider           │
  │ expires_at       │   │ description        │           │ provider_user_id   │
  │ revoked_at       │   │ natural_lang_req   │           │ access_token_enc   │
  │ device_info      │   │ current_version_id │           │ refresh_token_enc  │
  │ created_at       │   │ is_active          │           │ token_expires_at   │
  └──────────────────┘   │ is_template        │           │ scopes             │
                         │ is_public          │           │ is_active          │
                         │ tags / category    │           └────────────────────┘
                         │ total_runs         │
                         │ last_run_at/status │
                         └────────┬───────────┘
                                  │ 1
          ┌───────────────────────┼──────────────────────────────────┐
          │ N                     │ N                    │ N         │ N
          ▼                       ▼                      ▼           ▼
  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
  │workflow_versions │  │    schedules     │  │  wf_shares   │  │  wf_variables    │
  ├──────────────────┤  ├──────────────────┤  ├──────────────┤  ├──────────────────┤
  │ id (PK)          │  │ id (PK)          │  │ id (PK)      │  │ id (PK)          │
  │ workflow_id (FK) │  │ workflow_id (FK) │  │ workflow_id  │  │ workflow_id (FK) │
  │ version_number   │  │ user_id (FK)     │  │ owner_id     │  │ name             │
  │ definition_json  │  │ cron_expression  │  │ shared_with  │  │ value_json       │
  │ change_summary   │  │ timezone         │  │ share_token  │  │ is_secret        │
  │ created_by (FK)  │  │ is_active        │  │ permission   │  │ description      │
  │ is_current       │  │ next_run_at      │  │ expires_at   │  └──────────────────┘
  │ created_at       │  │ misfire_policy   │  │ is_active    │
  └──────────────────┘  └──────────────────┘  └──────────────┘
```

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                        MARKETPLACE CLUSTER                               │
  └──────────────────────────────────────────────────────────────────────────┘

  workflows (1) ──────────────────────────────────────────────── (1) workflow_marketplace
                                                                       │
                                                                       │ 1
                                                                       │
                                                          ┌────────────▼──────────────┐
                                                          │    marketplace_reviews    │
                                                          ├───────────────────────────┤
                                                          │ id (PK)                   │
                                                          │ marketplace_id (FK)       │
                                                          │ reviewer_id (FK) ── users │
                                                          │ rating (1-5)              │
                                                          │ review_text               │
                                                          │ created_at                │
                                                          └───────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────┐
  │                        SUPPORT TABLES                                    │
  └──────────────────────────────────────────────────────────────────────────┘

  users (1) ─── (N) secrets
  users (1) ─── (N) notifications
  users (1) ─── (N) workflow_history ─── (N) workflows

  workflows (1) ─── (N) execution_logs   [soft-ref via run_id → workflow_runs]
  workflows (1) ─── (N) workflow_history

  users (1) ─── (N) workflow_templates   [author_id, nullable]
  plugins  (standalone registry — no FK to users)
```

---

## Relationship Summary Table

| From Table              | To Table                | Type  | Via Column(s)                     |
|-------------------------|-------------------------|-------|-----------------------------------|
| users                   | refresh_tokens          | 1 : N | refresh_tokens.user_id            |
| users                   | workflows               | 1 : N | workflows.user_id                 |
| users                   | oauth_connections       | 1 : N | oauth_connections.user_id         |
| users                   | secrets                 | 1 : N | secrets.user_id                   |
| users                   | schedules               | 1 : N | schedules.user_id                 |
| users                   | notifications           | 1 : N | notifications.user_id             |
| users                   | workflow_history        | 1 : N | workflow_history.user_id          |
| users                   | marketplace_reviews     | 1 : N | marketplace_reviews.reviewer_id   |
| users                   | workflow_marketplace    | 1 : N | workflow_marketplace.user_id      |
| users                   | workflow_shares (owner) | 1 : N | workflow_shares.owner_id          |
| users                   | workflow_shares (recv)  | 1 : N | workflow_shares.shared_with_user_id |
| users                   | workflow_templates      | 1 : N | workflow_templates.author_id      |
| workflows               | workflow_versions       | 1 : N | workflow_versions.workflow_id     |
| workflows               | schedules               | 1 : N | schedules.workflow_id             |
| workflows               | workflow_marketplace    | 1 : 1 | workflow_marketplace.workflow_id  |
| workflows               | workflow_shares         | 1 : N | workflow_shares.workflow_id       |
| workflows               | workflow_variables      | 1 : N | workflow_variables.workflow_id    |
| workflows               | workflow_history        | 1 : N | workflow_history.workflow_id      |
| workflow_marketplace    | marketplace_reviews     | 1 : N | marketplace_reviews.marketplace_id|
| workflow_versions       | users (creator)         | N : 1 | workflow_versions.created_by      |
| execution_logs          | workflow_runs           | N : 1 | execution_logs.run_id (soft ref)  |
| scheduled_workflows     | workflow_runs           | 1 : N | workflow_runs.scheduled_workflow_id (soft ref) |

---

## Cardinality Notation Key

| Symbol | Meaning              |
|--------|----------------------|
| 1      | Exactly one          |
| N      | Zero or more         |
| 1 : N  | One-to-many          |
| 1 : 1  | One-to-one (unique)  |
| M : N  | Many-to-many (none in this schema — resolved via join tables) |

---

## Key Fields per Table

| Table                  | PK  | Unique Constraints                          | Important Indexes                          |
|------------------------|-----|---------------------------------------------|--------------------------------------------|
| users                  | id  | email                                       | role, is_active                            |
| refresh_tokens         | id  | token_hash                                  | user_id + expires_at                       |
| workflows              | id  | —                                           | user_id+is_active, category, is_public     |
| workflow_versions      | id  | workflow_id + version_number                | workflow_id + is_current                   |
| execution_logs         | id  | —                                           | run_id + step_index, status                |
| plugins                | id  | plugin_id                                   | is_enabled, is_builtin                     |
| oauth_connections      | id  | user_id + provider                          | provider, is_active                        |
| secrets                | id  | user_id + name                              | user_id + is_active                        |
| schedules              | id  | —                                           | is_active + next_run_at                    |
| notifications          | id  | —                                           | user_id + is_read, created_at              |
| workflow_templates     | id  | —                                           | category, is_featured, use_count           |
| workflow_marketplace   | id  | workflow_id                                 | is_approved, rating_avg, downloads         |
| marketplace_reviews    | id  | marketplace_id + reviewer_id                | rating                                     |
| workflow_shares        | id  | share_token                                 | workflow_id+is_active, expires_at          |
| workflow_variables     | id  | workflow_id + name                          | is_secret                                  |
| workflow_history       | id  | —                                           | workflow_id + created_at, action           |

---

## Design Decisions & Best Practices

### 1. Soft Deletes vs. Hard Deletes
Most tables use `is_active` flags rather than physical row deletion. This preserves audit trails and allows recovery. Hard deletes are only used when explicitly safe (e.g., cascading a user's refresh tokens on account deletion).

### 2. Encryption at Rest
All columns containing credentials, tokens, or PII carry the `_encrypted` suffix. The application layer (see `services/encryption.py`) handles Fernet symmetric encryption before persistence. The database never holds plaintext secrets.

### 3. Cascade Rules
- `users → [refresh_tokens, workflows, oauth_connections, secrets, schedules, notifications, marketplace, reviews, shares, history]`: **CASCADE DELETE** — removing a user removes all their data.
- `workflows → [versions, schedules, marketplace, shares, variables, history]`: **CASCADE DELETE**.
- `workflow_versions.created_by → users`: **SET NULL** — preserves version history even if the author is deleted.
- `workflow_templates.author_id → users`: **SET NULL** — templates survive author deletion.

### 4. Soft FK for execution_logs ↔ workflow_runs
`execution_logs.run_id` references `workflow_runs.id` without a database-level foreign key constraint. This decouples Phase 1 and Phase 2 models, allowing them to live in separate migration branches and avoiding circular import issues in SQLAlchemy. Application code enforces the integrity.

### 5. Versioning Strategy (workflow_versions)
- `version_number` is monotonically increasing per workflow and enforced by a unique constraint.
- Only one version can have `is_current = 1` per workflow (enforced at application layer; a partial unique index would enforce it at DB level in PostgreSQL).
- `workflows.current_version_id` is a denormalized pointer updated atomically with the `is_current` flag flip.

### 6. Marketplace Rating Denormalization
`workflow_marketplace.rating_avg` and `rating_count` are denormalized aggregates recomputed on each review insert/update. This trades write-time compute for fast read-time queries without a GROUP BY on the reviews table.

### 7. JSON Storage in SQLite
Tags, definitions, and action schemas are stored as `TEXT` containing valid JSON. SQLite does not have a native JSON type, but the `json_extract()` function (SQLite 3.9+) enables querying. In PostgreSQL, these columns should be migrated to `JSONB` for indexing and operators.

### 8. Boolean Storage
SQLite uses `INTEGER 0/1` for booleans. The SQLAlchemy models use `Boolean` which the dialect maps automatically. PostgreSQL uses native `BOOLEAN`. No application code change needed when migrating.

### 9. Timezone Handling
All timestamps are stored in UTC (ISO-8601 TEXT in SQLite; `TIMESTAMPTZ` in PostgreSQL). The `schedules.timezone` column holds the user's display timezone (IANA format) for cron scheduling, but execution and audit times are always UTC.

### 10. Index Strategy
- Every foreign key column has a single-column index to avoid full table scans on JOINs.
- Composite indexes are added where two columns are frequently queried together (e.g., `user_id + is_read` for the notification badge count, `is_active + next_run_at` for the scheduler poll).
- High-cardinality columns like `created_at` and `email` are indexed individually for range queries and lookups.

---

## PostgreSQL Migration Notes

When migrating from SQLite to PostgreSQL:

1. Replace `INTEGER` booleans with native `BOOLEAN`.
2. Replace `TEXT` timestamps with `TIMESTAMPTZ`.
3. Replace `TEXT` JSON columns with `JSONB` for GIN indexing on tag arrays.
4. Replace `AUTOINCREMENT` with `SERIAL` or `GENERATED ALWAYS AS IDENTITY`.
5. Add partial unique index: `CREATE UNIQUE INDEX ON workflow_versions (workflow_id) WHERE is_current = true;`
6. Enable `pg_trgm` extension and add GIN indexes on `name`, `title`, and `description` columns for full-text search.
7. Use `ON CONFLICT DO UPDATE` (upsert) instead of application-level insert-or-update patterns.
