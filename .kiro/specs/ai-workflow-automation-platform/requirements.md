# Requirements Document

## Introduction

The AI Workflow Automation Platform transforms how users create and manage automated workflows. Instead of manually configuring triggers, actions, API credentials, and error-handling logic — as required by tools like n8n, Zapier, and Make — users describe their automation in plain English and the platform acts as an AI Automation Engineer.

The platform **extends** the existing FastAPI backend (Groq/LLaMA AI interpreter, SQLite database, APScheduler, delivery channels, and LeetCode tracker) with a full React + TailwindCSS + React Flow frontend, a custom workflow execution engine, JWT authentication, a visual workflow editor, real-time execution monitoring, a plugin system for integrations, and failure analysis with improvement suggestions.

This document covers the complete Phase 1 scope: architecture, authentication, execution engine, frontend, API design, database schema, and folder structure.

---

## Glossary

- **Platform**: The AI Workflow Automation Platform described in this document.
- **User**: Any authenticated person interacting with the Platform.
- **Workflow**: A named, versioned sequence of Steps triggered by an event or schedule.
- **Step**: A single atomic action within a Workflow (e.g., fetch data, send email).
- **Workflow_Specification**: The structured JSON representation of a Workflow produced by the AI Interpreter before execution.
- **AI_Interpreter**: The existing Groq/LLaMA service (`services/ai.py`) that converts natural language into a `WorkflowInstruction`.
- **Clarification_Agent**: The conversational sub-module that asks follow-up questions when the AI_Interpreter cannot resolve intent with sufficient confidence.
- **Execution_Engine**: The Platform's own custom execution engine (replacing n8n dispatch) that runs Steps sequentially, manages retries, and records results.
- **Visual_Editor**: The React Flow–based frontend component that renders a Workflow graph and accepts drag-and-drop edits.
- **Plugin**: A self-contained integration module (e.g., Google Sheets, Slack, GitHub) loadable by the Execution_Engine at runtime.
- **Scheduler**: The APScheduler-backed service (`services/scheduler.py`) that triggers Workflows on cron or interval schedules.
- **WorkflowRun**: A persisted record of a single execution instance (already modelled in `models.py`).
- **ScheduledWorkflow**: A persisted record of a recurring Workflow with its schedule (already modelled in `models.py`).
- **JWT**: JSON Web Token used for user authentication.
- **API_Key**: A static secret used by server-to-server or programmatic callers (existing `security.py` mechanism).
- **Delivery_Channel**: An output destination for execution results — `dashboard`, `email`, or `slack`.
- **UserProfile**: Per-user encrypted configuration record (already modelled in `models.py`).
- **Confidence_Score**: A numeric value (0.0–1.0) produced by the AI_Interpreter indicating how well it understood the user's request.
- **Idempotency_Key**: A client-supplied token that prevents duplicate WorkflowRun creation on retried requests (already modelled in `models.py`).

---

## Requirements

### Requirement 1: Natural Language Workflow Creation

**User Story:** As a user (student, small business owner, teacher, HR manager, developer, freelancer, content creator), I want to describe my automation in plain English, so that I can create workflows without understanding APIs, triggers, or programming concepts.

#### Acceptance Criteria

1. WHEN a User submits a natural language request of 10–2 000 characters, THE AI_Interpreter SHALL produce a Workflow_Specification within 10 seconds.
2. WHEN the AI_Interpreter produces a Workflow_Specification with a Confidence_Score below 0.7, THE Clarification_Agent SHALL ask at least one targeted follow-up question before proceeding to generation.
3. WHEN the User answers a Clarification_Agent question, THE AI_Interpreter SHALL incorporate the answer and re-evaluate the Confidence_Score.
4. WHEN a request contains a prompt-injection pattern (as defined in `schemas.py`), THE Platform SHALL reject the request with HTTP 422 and return a descriptive error message — this rejection SHALL occur regardless of any other system state.
5. THE AI_Interpreter SHALL fall back to the rule-based interpreter (`_fallback_instruction`) when the Groq API is unreachable, returning a valid Workflow_Specification in all cases.
6. WHEN a User provides a request referencing a previously created Workflow by name, THE AI_Interpreter SHALL use that Workflow's structure as a starting template.

---

### Requirement 2: Workflow Specification Generation and Preview

**User Story:** As a user, I want to see a clear preview of what the AI plans to do before I approve execution, so that I can catch mistakes and understand every step.

#### Acceptance Criteria

1. WHEN a Workflow_Specification is produced, THE Platform SHALL render a Visual_Editor graph showing all Steps as nodes and their connections as directed edges.
2. THE Platform SHALL display a natural-language explanation for each Step node alongside its visual representation.
3. WHEN a User approves the Workflow_Specification in the Visual_Editor, THE Platform SHALL persist the Workflow and enqueue it for execution.
4. WHEN a User rejects the Workflow_Specification, THE Platform SHALL return to the natural language input with the prior request pre-filled for editing.
5. THE Workflow_Specification SHALL include, at minimum: `workflow_name`, `trigger`, `steps` (each with `name`, `action`, `params`), `channels`, and `output_format` — matching the existing `WorkflowInstruction` schema.
6. WHEN a Workflow_Specification is serialized to JSON and then deserialized, THE Platform SHALL produce an object equal to the original (round-trip property).

---

### Requirement 3: Visual Workflow Editor

**User Story:** As a developer or power user, I want to modify a generated workflow visually by dragging, dropping, and connecting nodes, so that I can fine-tune automation logic without writing code.

#### Acceptance Criteria

1. THE Visual_Editor SHALL render Workflow Steps as draggable nodes using React Flow.
2. WHEN a User drags a Step node to a new position, THE Visual_Editor SHALL update the node's layout without changing the Step's logical configuration.
3. WHEN a User adds a new Step node from the Step palette, THE Platform SHALL insert the Step into the Workflow_Specification at the designated position.
4. WHEN a User removes a Step node, THE Platform SHALL remove that Step from the Workflow_Specification and re-connect adjacent nodes.
5. WHEN a User edits a Step's parameters in the node inspector panel, THE Platform SHALL validate the parameters against the Step's plugin schema and display inline errors for invalid values — IF the validation mechanism itself fails to run, THE Platform SHALL still display an error message to the User.
6. THE Visual_Editor SHALL support undo (Ctrl+Z) and redo (Ctrl+Y) for the last 20 editing operations.
7. WHEN a User saves changes in the Visual_Editor, THE Platform SHALL persist the updated Workflow_Specification and increment the Workflow's version number — the version increment SHALL occur on each save attempt regardless of whether persistence succeeds.

---

### Requirement 4: Natural Language Workflow Modification

**User Story:** As a non-technical user, I want to modify an existing workflow by typing what I want to change in plain English, so that I don't have to use the visual editor.

#### Acceptance Criteria

1. WHEN a User provides a modification instruction (e.g., "also send the report to Slack"), THE AI_Interpreter SHALL apply the change to the existing Workflow_Specification and return an updated version.
3. WHEN a modification instruction is ambiguous, THE Clarification_Agent SHALL ask a follow-up question before applying the change — WHEN the clarified instruction would produce zero Steps, THE Platform SHALL then reject it with a descriptive error and preserve the original Workflow_Specification.
4. THE Platform SHALL display a diff view showing added, removed, and changed Steps between the original and modified Workflow_Specification.

---

### Requirement 5: Custom Workflow Execution Engine

**User Story:** As a platform operator, I want all workflows executed by the Platform's own engine (not n8n), so that execution behavior, retry logic, and error handling are under full control.

#### Acceptance Criteria

1. THE Execution_Engine SHALL execute Steps sequentially in the order defined by the Workflow_Specification.
2. WHEN a Step fails, THE Execution_Engine SHALL retry the Step up to 3 times with exponential backoff (initial delay 1 s, multiplier 2).
3. WHEN all retries for a Step are exhausted, THE Execution_Engine SHALL mark the WorkflowRun as `failed`, record the error, and proceed to failure reporting (Requirement 10).
4. THE Execution_Engine SHALL record a structured log entry for each Step execution, including: step name, action, start time, end time, status, and error message if applicable.
5. WHEN a WorkflowRun is submitted with an Idempotency_Key that already exists for the same user, THE Execution_Engine SHALL return the existing WorkflowRun without re-executing.
6. THE Execution_Engine SHALL complete execution of a Workflow with 10 or fewer Steps within 30 seconds under normal operating conditions.
7. WHEN the Execution_Engine is upgraded or restarted, WorkflowRuns with status `pending` or `running` SHALL be resumed or marked `failed` — they SHALL NOT remain in an indeterminate state.
8. FOR ALL valid Workflow_Specifications, executing a Workflow and then inspecting the resulting WorkflowRun SHALL produce a WorkflowRun whose `execution_status` is one of `pending`, `running`, `success`, or `failed` — no other values are permitted.

---

### Requirement 6: Execution Monitoring and Real-Time Status

**User Story:** As a user, I want to see the real-time status and logs of my running workflows, so that I know exactly what is happening and can detect failures immediately.

#### Acceptance Criteria

1. THE Platform SHALL expose a WebSocket or Server-Sent Events endpoint that pushes WorkflowRun status updates to connected frontend clients within 2 seconds of a status change.
2. WHEN a User opens the execution monitor for a WorkflowRun, THE Platform SHALL display the current status of each Step (pending, running, success, failed) updated in real time.
3. THE Platform SHALL retain structured execution logs for each WorkflowRun for a minimum of 30 days.
4. WHEN a User filters the execution history by date range, workflow name, or status, THE Platform SHALL return matching WorkflowRuns within 2 seconds for datasets up to 10 000 records — WHEN the dataset exceeds 10 000 records, THE Platform SHALL reject the filter request with an appropriate error rather than returning a slower response.
5. THE Platform SHALL display a human-readable summary of the execution output on the dashboard Delivery_Channel.

---

### Requirement 7: Scheduled Workflow Execution

**User Story:** As a teacher or HR manager, I want to schedule workflows to run automatically (e.g., daily at 9 AM, every Monday), so that I never have to manually trigger repetitive tasks.

#### Acceptance Criteria

1. WHEN a User creates a ScheduledWorkflow with a valid cron expression or preset interval, THE Scheduler SHALL register the job with APScheduler and persist the schedule.
2. WHEN a scheduled trigger fires, THE Scheduler SHALL create a new WorkflowRun linked to the ScheduledWorkflow via `scheduled_workflow_id` and submit it to the Execution_Engine.
3. WHEN a ScheduledWorkflow is paused by the User, THE Scheduler SHALL cancel the APScheduler job and set `is_active = 0` without deleting the record.
4. WHEN a ScheduledWorkflow is resumed, THE Scheduler SHALL re-register the job and set `is_active = 1`, using the original schedule.
5. THE Scheduler SHALL update `last_run_at`, `next_run_at`, `total_runs`, and `last_status` on the ScheduledWorkflow record after each triggered execution.
6. IF a scheduled trigger fires while the previous WorkflowRun for the same ScheduledWorkflow has status `running`, THEN THE Scheduler SHALL normally skip the new trigger and log a `skipped` event — IF the skip mechanism itself fails, THEN THE Scheduler SHALL allow the new trigger to proceed and create concurrent WorkflowRuns.
7. WHEN a User provides a human-readable schedule description (e.g., "every day at 9 AM"), THE Scheduler SHALL parse it into a valid cron expression and confirm the interpretation before saving.

---

### Requirement 8: JWT Authentication

**User Story:** As a user, I want to log in with my email and password and receive a JWT, so that my workflows and data are private and secure.

#### Acceptance Criteria

1. WHEN a User submits valid credentials to the login endpoint, THE Platform SHALL return a signed JWT with an expiry of 24 hours and a refresh token with an expiry of 7 days.
2. WHEN a request is made to a protected endpoint without a JWT or with an expired JWT, THE Platform SHALL return HTTP 401.
3. WHEN a refresh token is submitted to the token refresh endpoint before expiry, THE Platform SHALL return a new JWT without requiring re-authentication.
4. THE Platform SHALL store password hashes using bcrypt with a minimum cost factor of 12 — plaintext passwords SHALL NOT be stored.
5. WHEN a User logs out, THE Platform SHALL invalidate the refresh token so it cannot be used to obtain new JWTs.
6. THE Platform SHALL coexist with the existing API_Key authentication mechanism: requests may be authenticated by JWT (Bearer) OR API_Key header — both schemes SHALL be supported on all protected endpoints.
7. WHEN 5 consecutive failed login attempts are made for the same user identifier within 15 minutes, THE Platform SHALL lock the account for 15 minutes and return HTTP 429.

---

### Requirement 9: React Frontend with Visual Dashboard

**User Story:** As a user, I want a clean, responsive web interface built with React and TailwindCSS, so that I can manage my workflows from any device without needing the CLI or raw API.

#### Acceptance Criteria

1. THE Platform SHALL serve a React + TailwindCSS single-page application on the root path (`/`) that replaces the existing Jinja2 dashboard.
2. THE Platform SHALL preserve all existing Jinja2 dashboard routes (`/api/dashboard`, `/api/leetcode/dashboard`) and expose their data via JSON API endpoints so the React frontend can consume them.
3. THE React Frontend SHALL include the following views: Login/Register, Workflow Creator (natural language input + Visual_Editor), Workflow Library (list, search, filter), Execution Monitor (real-time run detail), Scheduled Workflows (CRUD), User Profile (settings, delivery channels), and LeetCode Tracker (migrated from Jinja2).
4. WHEN the viewport width is less than 768 px, THE React Frontend SHALL render a mobile-optimized layout with a collapsible sidebar.
5. THE React Frontend SHALL display a loading skeleton while awaiting API responses longer than 300 ms.
6. WHEN an API call returns an error, THE React Frontend SHALL display a user-friendly error message with a suggested action and SHALL NOT display raw stack traces or internal error details.

---

### Requirement 10: Failure Reporting and Improvement Suggestions

**User Story:** As a user, I want to understand why a workflow failed and receive concrete suggestions for fixing it, so that I can improve my automations without guessing.

#### Acceptance Criteria

1. WHEN a WorkflowRun reaches `failed` status, THE Platform SHALL generate a structured failure report containing: failed Step name, action type, error message, retry history, and timestamp.
2. WHEN a failure report is generated, THE AI_Interpreter SHALL analyze the failure context and produce at least one concrete improvement suggestion in natural language.
3. THE Platform SHALL expose the failure report and suggestions on the execution monitor view within 5 seconds of the WorkflowRun reaching `failed` status.
4. WHEN a User accepts an improvement suggestion, THE Platform SHALL apply it to the Workflow_Specification first, and only after the update is complete SHALL THE Platform open the Visual_Editor with the updated version for review.
5. THE Platform SHALL track the number of failures per Step action type across all WorkflowRuns and surface the top 3 most-failed actions in the User's dashboard.

---

### Requirement 11: Plugin System for Integrations

**User Story:** As a developer, I want to add new integrations (Google Sheets, GitHub, custom APIs) as plugins without modifying the core Execution_Engine, so that the Platform is extensible.

#### Acceptance Criteria

1. THE Execution_Engine SHALL load Plugin modules from a designated `plugins/` directory at startup without requiring changes to core engine code.
2. EACH Plugin SHALL declare: a unique `plugin_id` (snake_case, 3–64 chars), a human-readable `display_name`, a list of supported `actions`, and a JSON schema for each action's `params`.
3. WHEN the Execution_Engine encounters a Step whose `action` matches a loaded Plugin's supported action, THE Execution_Engine SHALL delegate execution to that Plugin.
4. WHEN a Plugin raises an unhandled exception during Step execution, THE Execution_Engine SHALL catch the exception, log it, mark the Step as `failed`, and apply the retry policy defined in Requirement 5 — it SHALL NOT crash the Execution_Engine process.
5. THE Platform SHALL expose a `GET /api/plugins` endpoint that returns the list of loaded Plugins with their `plugin_id`, `display_name`, and supported `actions`.
6. WHERE a Plugin declares credential requirements (e.g., OAuth tokens, API keys), THE Platform SHALL store those credentials encrypted in the `user_context_encrypted` field of UserProfile, using the existing encryption service (`services/encryption.py`).
7. THE Plugin interface SHALL define an `execute(step: WorkflowStep, context: dict) -> StepResult` contract that all Plugins MUST implement.

---

### Requirement 12: User Profile and Encrypted Credential Management

**User Story:** As a user, I want to store my API keys, email credentials, and Slack webhooks securely in my profile, so that my workflows can use them without exposing secrets in request text.

#### Acceptance Criteria

1. WHEN a User saves sensitive values (email password, SMTP credentials, Slack webhook, API keys) to their UserProfile, THE Platform SHALL encrypt each value at rest using the existing encryption service before persisting to the database.
2. WHEN a User retrieves their UserProfile, THE Platform SHALL return field values masked (e.g., `"smtp_pass": "••••••••"`) — decrypted values SHALL NOT be included in API responses.
3. WHEN the Execution_Engine requires credentials for a Step, THE Platform SHALL decrypt the relevant UserProfile fields in memory, use them for the Step, and discard them immediately after — decrypted values SHALL NOT be logged or persisted.
4. WHEN a User updates an encrypted field, THE Platform SHALL re-encrypt the new value and overwrite the previous ciphertext.
5. THE Platform SHALL validate SMTP credentials by performing pre-checks (format validation, required field presence) before saving — IF validation fails, THE Platform SHALL return a descriptive error; IF validation passes, THE Platform SHALL save the credentials silently without returning a success message.

---

### Requirement 13: API Design and Documentation

**User Story:** As a developer integrating with the Platform, I want a well-documented REST API with consistent error responses, so that I can build reliable integrations.

#### Acceptance Criteria

1. THE Platform SHALL expose all endpoints under a versioned prefix (`/api/v1/`) for new endpoints while preserving existing `/api/` routes for backward compatibility.
2. THE Platform SHALL serve an OpenAPI 3.0 specification at `/docs` (Swagger UI) and `/openapi.json`.
3. ALL API endpoints SHALL return errors in a consistent JSON structure: `{"error": "<code>", "message": "<human-readable>", "request_id": "<uuid>"}`.
4. THE Platform SHALL attach a unique `request_id` (UUID v4) to every request and include it in response headers (`X-Request-ID`) and structured log entries.
5. ALL write endpoints SHALL support idempotency via the `Idempotency-Key` request header, using the existing `IdempotencyRecord` model.
6. THE Platform SHALL enforce rate limiting of 60 requests per minute per authenticated user on workflow creation and execution endpoints, using the existing `rate_limit.py` mechanism.

---

### Requirement 14: Database Schema and Migration

**User Story:** As a platform operator, I want a well-structured, migratable database schema that supports all platform features and scales from SQLite to PostgreSQL, so that the data layer is robust and maintainable.

#### Acceptance Criteria

1. THE Platform SHALL extend the existing SQLite schema with new tables for: `users` (JWT auth), `workflow_definitions` (versioned workflow specs), `step_execution_logs` (per-step records), and `plugins` (plugin registry).
2. THE Platform SHALL manage all schema changes through Alembic migrations — manual `CREATE TABLE` statements in application code SHALL NOT be used for new tables.
3. WHEN the database is migrated from SQLite to PostgreSQL, THE Platform SHALL require no application-layer code changes beyond updating the `DATABASE_URL` environment variable.
4. ALL timestamp columns SHALL use timezone-aware UTC datetimes, consistent with the existing `_utcnow()` pattern in `models.py`.
5. THE Platform SHALL enforce foreign key constraints between `workflow_runs.scheduled_workflow_id` and `scheduled_workflows.id`, and between new `step_execution_logs.run_id` and `workflow_runs.id`.
6. WHEN a `users` record is deleted, THE Platform SHALL cascade-delete or nullify all related records (WorkflowRuns, ScheduledWorkflows, UserProfile) to prevent orphaned data.

---

### Requirement 15: Project Folder Structure and Architecture

**User Story:** As a developer joining the project, I want a clear, consistent folder structure that separates concerns across frontend, backend, plugins, and infrastructure, so that I can navigate and contribute without confusion.

#### Acceptance Criteria

1. THE Platform SHALL organize the codebase into top-level directories: `backend/` (existing FastAPI app), `frontend/` (new React app), `plugins/` (plugin modules), `scripts/` (existing utility scripts), `monitoring/` (existing observability stack), and `docs/` (architecture documentation).
2. THE backend SHALL follow the existing package structure: `app/routers/` for route handlers, `app/services/` for business logic, `app/models.py` for ORM models, and `app/schemas.py` for Pydantic contracts.
3. THE frontend SHALL follow the structure: `src/components/` (shared UI), `src/pages/` (route-level views), `src/hooks/` (custom React hooks), `src/api/` (API client functions), and `src/store/` (global state).
4. EACH Plugin SHALL be contained in a single directory under `plugins/<plugin_id>/` containing: `__init__.py`, `plugin.py` (implementing the Plugin interface), `schema.json` (params schema), and `README.md`.
5. THE Platform SHALL include a `docker-compose.yml` that starts all required services (backend, frontend, database) with a single `docker compose up` command.

---

### Requirement 16: LeetCode Tracker Migration and Extension

**User Story:** As a teacher or batch coordinator, I want the LeetCode tracker to be accessible from the new React frontend with the same features as the Jinja2 dashboard, so that the upgrade does not break existing workflows.

#### Acceptance Criteria

1. THE Platform SHALL expose all LeetCode tracker functionality (`/api/leetcode/`) as JSON API endpoints consumable by the React frontend.
2. THE React Frontend SHALL include a LeetCode Tracker page that replicates all features of the existing `leetcode.html` Jinja2 template.
3. WHEN the LeetCode execution path is triggered (keywords matching `_LEETCODE_KEYWORDS` in `execution.py`), THE Execution_Engine SHALL route the request to the LeetCode handler, consistent with the existing intent-detection logic — IF routing fails after keyword detection, THE Execution_Engine SHALL allow the request to proceed via whatever execution path the routing logic determines.
4. THE Platform SHALL retain the existing `LeetCodeStudent` and `LeetCodeReport` models without modification.

---

### Requirement 17: Delivery Channel Integration

**User Story:** As a user, I want execution results delivered to my chosen channels (dashboard, email, Slack), so that I receive notifications wherever I work.

#### Acceptance Criteria

1. WHEN a WorkflowRun completes and `channels` includes `email`, THE Platform SHALL send an email to the address stored in the User's UserProfile using the SMTP configuration from UserProfile.
2. WHEN a WorkflowRun completes and `channels` includes `slack`, THE Platform SHALL POST the result summary to the Slack webhook URL stored in UserProfile.
3. WHEN a WorkflowRun completes and `channels` includes `dashboard`, THE Platform SHALL make the result available on the React dashboard immediately.
4. IF an email delivery fails (SMTP error, unreachable server), THEN THE Platform SHALL set `delivery_status` to `failed`, log the error, and retry delivery up to 3 times with a 60-second interval.
5. IF a Slack delivery fails (webhook returns non-2xx), THEN THE Platform SHALL set `delivery_status` to `failed`, log the error, and retry delivery up to 3 times with a 60-second interval.
6. THE Platform SHALL update `delivery_status` on the WorkflowRun record to `delivered` only when all configured Delivery_Channels for that WorkflowRun have been successfully notified — the check SHALL apply abstractly to whichever channels are configured, without enumerating specific channel types in the condition.

---

### Requirement 18: Security and Input Validation

**User Story:** As a security-conscious operator, I want all inputs validated, secrets encrypted, and attack surfaces minimized, so that the Platform is safe to expose to external users.

#### Acceptance Criteria

1. THE Platform SHALL validate all incoming request bodies against Pydantic schemas before processing — unvalidated inputs SHALL NOT reach service or database layers.
2. THE Platform SHALL enforce HTTPS in production deployments — HTTP requests SHALL be redirected to HTTPS.
3. WHEN CORS is configured, THE Platform SHALL only allow origins explicitly listed in the `ALLOWED_ORIGINS` environment variable.
4. THE Platform SHALL include security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`) on all HTTP responses in production.
5. THE Platform SHALL sanitize natural language request text using the existing `_sanitize_text` and `_SAFE_TEXT_PATTERN` validators in `schemas.py` before passing to the AI_Interpreter.
6. ALL database queries SHALL use SQLAlchemy ORM parameterized queries — raw SQL string interpolation SHALL NOT be used.
