# Current Released Features PRD (Atlas / voice-comm)

## 1. Document Purpose
This document is the consolidated product requirements specification for features that are currently released in this repository as of 2026-04-02.

It answers one question: what capabilities are already shipped and available to operators/users today.

## 2. Scope And Rules
- In scope: features implemented in code and exposed via CLI, UI, API, or documented runtime workflows.
- Out of scope: backlog ideas, partially drafted plans, and future-looking proposals not shipped in runtime surfaces.
- Status labels used:
  - `Released`: available in current codebase.
  - `Released (Beta)`: shipped behind a feature flag or explicitly labeled beta.
  - `Released (Experimental)`: shipped but explicitly labeled experimental.

## 3. Current Released Feature Catalog

### F1. Local Voice Loop (Core)
- Status: `Released`
- User value: local turn-based conversation with speech input/output.
- Delivered behavior:
  - Microphone turn recording.
  - Whisper transcription via OpenAI (`whisper-1`).
  - Assistant response generation.
  - OpenAI TTS first, with local `pyttsx3` fallback.
- Primary surfaces:
  - `voice_loop.py`
  - `README.md` ("Voice Comm", run/flags sections)

### F2. Atlas Desktop UI Session Runtime
- Status: `Released`
- User value: persistent desktop interface for voice + text turns with live streaming output.
- Delivered behavior:
  - Long-lived Codex session handling.
  - Push-to-talk + stop/new session controls.
  - Device selection and refresh.
  - Settings persistence.
- Primary surfaces:
  - `atlas_ui.py`
  - `README.md` ("Atlas UI")

### F3. Spotify OAuth + Playback Skill Suite
- Status: `Released`
- User value: Spotify playback and playlist actions from voice, UI controls, and task automation.
- Delivered behavior:
  - OAuth PKCE helper and encrypted token storage.
  - Command router for play/pause/next/devices/volume/status.
  - "Add current track to playlist".
  - Natural-language Spotify agent triggers.
  - Task Hub automation commands for Spotify actions.
- Primary surfaces:
  - `scripts/spotify_oauth.py`
  - `spotify_client.py`
  - `spotify_skill.py`
  - `spotify_agent_skill.py`
  - `plan/features/implemented/spotify-skill-prd.md`

### F4. Local Whisper Stack CLI
- Status: `Released`
- User value: local transcription path for offline/low-latency workflows.
- Delivered behavior:
  - Model download/bootstrap.
  - CPU/GPU local transcription modes.
  - JSON output option for automation.
- Primary surfaces:
  - `local_whisper.py`
  - `README.md` ("Local Whisper stack")

### F5. Memory Core Service (Postgres + FastAPI)
- Status: `Released`
- User value: durable, queryable memory backend independent of UI process restarts.
- Delivered behavior:
  - FastAPI service (`127.0.0.1:5147` default).
  - Postgres + pgvector-backed storage.
  - Health/stats/recent/search/promote/curator operations.
  - Windows service install path.
- Primary surfaces:
  - `memory_core/`
  - `scripts/setup_memory_service.ps1`
  - `scripts/memory_v2_migrate.py`
  - `README.md` ("Memory Core Service", "Memory-Core Service")

### F6. Memory Explorer UI + Memory Widget
- Status: `Released (Beta)`
- User value: operator observability and optional CRUD over memory data.
- Delivered behavior:
  - Service health panel in desktop UI.
  - Explorer window with filters/search/detail/pagination.
  - Optional CRUD, re-embed, curator run-once actions.
  - Operator token handling and source warnings.
- Primary surfaces:
  - `memory_explorer_panel.py`
  - `atlas_ui.py`
  - `plan/features/memory-core-observability.md`

### F7. Shared Task Hub Orchestration
- Status: `Released`
- User value: structured task lifecycle management across voice/UI/CLI.
- Delivered behavior:
  - Task repository, parser, ingest, scheduler, runner, delegation.
  - Dashboard UI and lifecycle controls.
  - Task ingest from voice/UI flows.
  - Task attachments support.
- Primary surfaces:
  - `tasks_repository.py`
  - `task_parser.py`
  - `task_ingest.py`
  - `task_scheduler.py`
  - `task_runner.py`
  - `task_delegation.py`
  - `task_dashboard.py`
  - `plan/features/implemented/shared-task-orchestration.md`

### F8. Always-On Wake + Global Hotkeys
- Status: `Released`
- User value: hands-free wake phrase flow and fast keyboard controls.
- Delivered behavior:
  - Wake mode controls and wake phrase settings.
  - Global hotkey bindings.
  - Wake state machine indicators and watchdog reset behavior.
  - Wake diagnostics logs.
- Primary surfaces:
  - `wake_engine.py`
  - `hotkey_manager.py`
  - `plan/features/implemented/always-on-wake.md`
  - `plan/features/implemented/always-on-wake-backlog.md`

### F9. Action Database + Heartbeat Automation
- Status: `Released`
- User value: periodic proactive check-ins and reusable operator actions.
- Delivered behavior:
  - SQLite action database + CRUD.
  - Scheduled action runner and heartbeat cadence controls.
  - Default built-in actions (briefing, Gmail, spawn sub-agent, etc.).
  - Follow-up link persistence and personal engagement guard hooks.
- Primary surfaces:
  - `action_db.py`
  - `action_scheduler.py`
  - `heartbeat_checkin.py`
  - `atlas_actions.py`
  - `personal_engagement.py`

### F10. Telegram Bridge (Multi-Endpoint)
- Status: `Released`
- User value: multi-bot Telegram ingress/egress with persona-aware routing.
- Delivered behavior:
  - Endpoint config with ACLs and mode controls.
  - Polling and webhook relay support.
  - Event logging and normalized payload logs.
  - Optional task-ingest integration.
- Primary surfaces:
  - `telegram_bridge.py`
  - `telegram_endpoints.py`
  - `config/telegram_endpoints.example.yaml`
  - `README.md` ("Telegram Bridge")

### F11. LAN Control Plane API
- Status: `Released (Experimental)`
- User value: LAN clients can issue Atlas commands and query state remotely.
- Delivered behavior:
  - Token-managed API authentication.
  - Status, message, history, actions, tasks, clipboard, and file-drop endpoints.
  - UI + CLI token lifecycle operations.
  - Local API metadata/help endpoint.
- Primary surfaces:
  - `control_plane/server.py`
  - `atlas_actions.py` (`api` command group)
  - `plan/features/implemented/lan-control-plane.md`
  - `README.md` ("LAN Control Plane API (Experimental)")

### F12. Playwright Co-Browsing Session Manager
- Status: `Released`
- User value: launch/list/kill browser sessions with persistent profiles.
- Delivered behavior:
  - Profile-routed session launch.
  - Session listing (running/all).
  - PID-based kill for stuck sessions.
  - Session logging to JSONL.
- Primary surfaces:
  - `playwright_sessions.py`
  - `README.md` ("Playwright co-browsing helper")

### F13. Gmail Tools Integration
- Status: `Released`
- User value: Gmail list/read/draft/send workflows from local CLI/UI workflows.
- Delivered behavior:
  - OAuth auth bootstrap.
  - Inbox query + message read.
  - Draft creation + guarded send flow.
- Primary surfaces:
  - `gmail_tools.py`
  - `README.md` ("Gmail Tools")

### F14. Markdown Conversation Rendering In Desktop UI
- Status: `Released`
- User value: improved readability of agent output with rich markdown formatting.
- Delivered behavior:
  - Markdown parsing/rendering in conversation pane.
  - Safe formatting subset for headings/lists/code/links/emphasis.
  - Plain-text compatibility for logs/exports.
- Primary surfaces:
  - `markdown_renderer.py`
  - `plan/features/implemented/markdown-conversation.md`

### F15. Tool Discovery Registry (Memory-Core Backed)
- Status: `Released`
- User value: runtime semantic discovery of tools and usage ranking feedback.
- Delivered behavior:
  - Tool register/search/preload/list/used operations.
  - Memory Core REST and CLI integration.
  - Registry scan and documented inventory generation.
- Primary surfaces:
  - `memory_core/service.py` (`/tools/*`)
  - `atlas_actions.py` (`memory tool-*`)
  - `plan/features/implemented/tool-registry-full-discovery-2026-03-06.md`

## 4. Non-Goals / Not Counted As Released
- Backlog items under `plan/features/backlog/`.
- Proposed-only architecture decisions not shipped in runtime codepaths.
- Placeholder plans without matching executable surface.

## 5. Traceability
This PRD is traceable to:
- `README.md` runtime capability sections.
- Implemented feature plans under `plan/features/implemented/`.
- Executable modules and command surfaces in the repository root and `memory_core/`.

## 6. Maintenance Rules
- When a shipped feature is added, this catalog must be updated in the same change.
- When a feature moves to beta/experimental or to GA, update only the status label and date in this document.
- If a feature is retired, keep an entry with status `Removed` and include removal date + replacement.
