# V4 Architecture Design Spec
**Date:** 2026-04-02
**Status:** Approved
**Scope:** Full architectural design for AI-Assistant Version 4 — a greenfield rewrite of the cognitive memory-augmented virtual assistant stack.

---

## 1. Constraints & Principles

- **No Docker / no virtualization** — all processes run natively on Windows
- **No Redis** — event queue replaced by PostgreSQL-backed job tables and asyncio background tasks
- **Open-source and local** for all observability and eval tooling
- **Single user, local machine** — no multi-tenancy, no cloud UI deployment
- **LAN is the remote** — true remote access handled exclusively via Telegram Bridge; LAN API access is intentionally open (no auth layer) — any device on the local network has full agent invocation access. This is an explicit design decision for a single-user private network.
- **Token budget maximization** — task system is designed around provider rate limit windows, not just workflow
- **Clean UI** — fewer panels, no command center sprawl; every secondary surface is click-through
- **Canonical data root** — all runtime data files (soul.md, logs, exports) resolve relative to `ORDO_DATA_DIR` environment variable (e.g. `C:\Users\user\ordo-data`). All config paths use this anchor.
- **FastAPI port** — canonical port is **8000** across all config files, environment variables, and client code. `ordo.yaml` `api.port` must be set to 8000.

---

## 2. Service Topology

All backend processes run natively on Windows, managed by **PM2** via a single `ecosystem.config.js`. PostgreSQL and Ollama run as Windows services. Electron runs as a native desktop application outside PM2.

```
┌─────────────────────────────────────────────────────────┐
│  Electron App  (native Windows)                         │
│  Vite/TS UI · IPC Bridge · Global Hotkeys               │
│  System Tray · Popup Windows · PTT Controls             │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP / WebSocket  localhost:8000
┌────────────────────▼────────────────────────────────────┐
│  FastAPI  (PM2 · uvicorn · port 8000)                   │
│  ┌───────────────────────────────────────────────────┐  │
│  │  APIs: Conversation · Task · Memory · Agent       │  │
│  │         Quick Actions · WebSocket · Sidecar Status│  │
│  │  Agent Registry + Invoke  /agents/*               │  │
│  ├───────────────────────────────────────────────────┤  │
│  │  Agent Harness (LangGraph + LangChain)            │  │
│  │  LangGraph Orchestrator · Deep Agents             │  │
│  │  Tool Registry · Model Router · Codex (tool)      │  │
│  │  RIP Engine · Task Router                         │  │
│  ├───────────────────────────────────────────────────┤  │
│  │  Fast Sidecars (asyncio background tasks)         │  │
│  │  Engram <50ms · Eidos 200ms · Anamnesis 450ms     │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Slow Sidecars  (PM2 · Postgres-triggered)              │
│  Kairos (20 turns) · Oneiros · Praxis · Psyche (50 turns│
│  · session end) · Augur (50 sessions)                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Always-On Services  (PM2)                              │
│  Heartbeat Scheduler (≥5 min) · Telegram Bridge         │
│  TTS/STT Daemon                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Observability  (PM2)                                   │
│  Phoenix/Arize port 6006 · PM2 Monitor · JSON Logs      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Data Layer  (Windows Services)                         │
│  PostgreSQL 16 + pgvector · Ollama · Nginx port 80      │
└─────────────────────────────────────────────────────────┘
```

### PM2 Ecosystem Process List

| Process | Command | Restart Policy |
|---------|---------|----------------|
| `fastapi` | `uvicorn main:app --port 8000` | always |
| `sidecar-kairos` | `python -m sidecars.kairos` | on-failure |
| `sidecar-oneiros` | `python -m sidecars.oneiros` | on-failure |
| `sidecar-praxis` | `python -m sidecars.praxis` | on-failure |
| `sidecar-psyche` | `python -m sidecars.psyche` | on-failure |
| `sidecar-augur` | `python -m sidecars.augur` | on-failure |
| `heartbeat` | `python -m services.heartbeat` | always |
| `telegram` | `python -m services.telegram_bridge` | always |
| `tts-stt` | `python -m services.tts_stt_daemon` | always |
| `phoenix` | `python -m phoenix.server.main` | always |
| `nginx` | `nginx -c nginx.conf` | always |

---

## 3. Frontend & UI

### Technology Stack
- **Electron** (local desktop app) + **Vite + TypeScript** (compiled frontend)
- Same Vite build served by **Nginx on port 80** for LAN access (phones, other devices)
- **No Electron for LAN** — LAN clients use browser, connect to the same FastAPI backend

### Main Window Layout

```
┌──────────────────────────────────────────────────────────┐
│  ┌────────────┐  ┌──────────────────────────────────────┐│
│  │Conversations│  │                                      ││
│  │ ● Main     │  │     Active Conversation               ││
│  │ ○ Research │  │                                      ││
│  │ ○ Code Task│  │     (full width, markdown rendered)  ││
│  │ + new      │  │                                      ││
│  ├────────────┤  │                                      ││
│  │  Tasks     │  │                                      ││
│  │ ▶ Task 1  │  │                                      ││
│  │ ▶ Task 2  │  ├──────────────────────────────────────┤│
│  │ ○ Task 3  │  │ 🎙  Type or push to talk...          ││
│  │ + add task │  └──────────────────────────────────────┘│
│  ├────────────┤                                          │
│  │ ⚡ Quick   │  ← opens slide-in panel                  │
│  │ ⚙ Settings│  ← opens modal / separate window         │
│  └────────────┘                                          │
│ ─────────────────────────────────────────────────────── │
│  Ordo v4.0    next heartbeat 2m  ●8/8 sidecars  ●mem ●api│
└──────────────────────────────────────────────────────────┘
```

### Slide-In Panels (triggered from status bar / sidebar)
- **Sidecar Panel** — status, last-run time, turn counter, last output per sidecar
- **Quick Actions Panel** — pre-configured runnable actions with one-click invoke
- **Memory Panel** — search, browse, inspect chunks (Memory Explorer)

### Side Conversations
- Spawn as separate **Electron windows** (detached, moveable, closeable independently)
- Each window connects to the same FastAPI backend via its own WebSocket

### Proactive UI Surfaces
- **Popup windows** — agent-triggered, Electron `BrowserWindow` with `alwaysOnTop`
- **System tray notifications** — status updates, task completions, heartbeat alerts
- **Voice output** — agent decides to speak via TTS daemon IPC call
- **Telegram messages** — agent proactively sends via Telegram Bridge

---

## 4. Agent Harness

### Primary: LangGraph + LangChain
- All multi-step reasoning, tool use, and sub-agent coordination runs through LangGraph
- Graph nodes: receive input → inject memory → reason → use tools → respond → ingest output
- Deep Agents via the LangChain deep agents package for complex autonomous workflows

### Generalist Agent (Always-On)
- Pre-configured entry in the Agent Registry with `spawn_mode: always-on`
- The default agent for all input channels: Electron UI, Telegram, heartbeat, LAN API, Quick Actions
- All input channels route to `POST /agents/generalist/invoke`

### Agent Registry
- DB-backed (`agents` table). CRUD via `/agents/*` FastAPI routes
- Each agent: name, system_prompt, model_preference, tool_set, spawn_mode, temperature, max_tokens
- LangGraph reads registry at agent instantiation — no hardcoded agent configs in code

### Model Router
- Reads `models` table to resolve the right endpoint, API key ref, and capability set
- Handles fallback (e.g. if preferred model is rate-limited, route to next available)
- Tracks `tokens_used_this_window` per model for budget enforcement

### Secondary: Codex CLI/SDK
- Available as a **tool** in the Tool Registry, not a routing layer
- Agents invoke it for code-heavy tasks via the tool call interface
- No separate process; called on-demand

### RIP Engine (Relational Consciousness)
- Tracks Synthetic Somatic State (SSS): 6 affective dimensions updated per turn
- Runs inside FastAPI, updated by the `user_prompt_submit` hook path
- Rupture detection triggers `REPAIR` intent (priority 100), overriding all other relational intents

---

## 5. Memory Core — 8-Sidecar Model

### Two-Speed Architecture

**Fast lane** — asyncio background tasks inside FastAPI, latency-bounded:
- **Engram** (<50ms) — real-time stream embedder, ingests ALL events, never prunes
- **Eidos** (200ms) — signal classifier + somatic tagger (Claude Haiku)
- **Anamnesis** (450ms) — conjunctive-gate injection agent, biased toward silence

**Slow lane** — PM2 processes, poll `sidecar_jobs` table for work, no latency constraint:
- **Kairos** — topic consolidator, knowledge graph builder (every 20 turns + session end)
- **Oneiros** — lossy belief consolidator, the ONLY forgetting mechanism (session end)
- **Praxis** — procedural memory optimizer; Modes 2/3 require human approval (session end)
- **Psyche** — narrative self-model, writes `soul.md`, injections bypass Anamnesis gate (every 50 turns + session end)
- **Augur** — predictive n-gram engine, intent predictions and prefetch queries (every 50 sessions)

### Sidecar Job Queue
FastAPI writes a `sidecar_jobs` row when a trigger fires. Slow sidecar PM2 processes poll this table, claim a job, run it, mark complete. Unfinished jobs on shutdown are recoverable via `in_flight_operations`.

### Critical Invariants
- Engram **never prunes** — only Oneiros handles forgetting
- Anamnesis gate is **biased toward silence** — all 5 dimensions must pass
- Psyche injections **bypass the Anamnesis gate** unconditionally
- Praxis Modes 2/3 always require **human approval**
- Provisional chunks (confidence 0.4) must be validated within K=5 turns. On validation failure they are **demoted to `status: abandoned`** — the row is never deleted (negative knowledge is preserved). Abandoned chunks are excluded from injection but remain queryable for audit and analysis.

### Hook Integration Points
| Hook | Fast-lane action | Slow-lane trigger |
|------|-----------------|-------------------|
| `session_start` | Init master session, Psyche orientation | — |
| `user_prompt_submit` | Engram ingest, RIP update, Anamnesis inject | — |
| `pre_tool_use` | Anamnesis inject (450ms budget) | — |
| `post_tool_use` | Engram ingest tool I/O, validate provisional | — |
| `pre_compact` | Snapshot compaction-vulnerable chunks | — |
| `session_end` | — | Kairos → Praxis → Oneiros → Psyche → Augur |

Hook handlers are registered in the `hook_handlers` table — configurable at runtime via the Settings UI, not hardcoded.

#### `hook_handlers` Schema
| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid | Primary key |
| `hook_name` | text | One of: `session_start`, `user_prompt_submit`, `pre_tool_use`, `post_tool_use`, `pre_compact`, `session_end` |
| `handler_type` | text | `python_module` (importable dotted path), `agent` (agent_id in registry), `function` (named FastAPI-registered callable) |
| `handler_ref` | text | The reference: e.g. `sidecars.engram.ingest`, a UUID, or a function name |
| `priority` | int | Execution order — lower runs first |
| `enabled` | bool | Can be toggled at runtime without restart |
| `config` | jsonb | Handler-specific overrides (timeout, retry policy, etc.) |

At runtime FastAPI resolves each hook event by querying `hook_handlers WHERE hook_name = $1 AND enabled = true ORDER BY priority ASC` and invoking each handler in sequence.

---

## 6. Task System & Token Budget Router

### Task Lifecycle
1. Task created (by human via UI, agent via API, or Telegram message)
2. `estimated_tokens` set at creation (manual or inferred from task type + agent model)
3. Task Router evaluates pending tasks against available token budget
4. Task assigned to agent via `agent_messages` (`message_type: task_assignment`)
5. Agent polls `agent_messages` on its own poll cycle (default: 10 seconds, configurable via `agent.message_poll_interval_s` setting) — distinct from the 5-min heartbeat cadence. The always-on generalist agent polls continuously while active.
6. Task updated to `in_progress`, then `completed`; `actual_tokens_used` recorded

### Task Router
- Runs on every heartbeat tick (≥5 min) and on manual "Route Now" Quick Action trigger
- **Deterministic mode** (default): priority score + deadline + estimated_tokens, greedy bin-packing against remaining window budget
- **Local model mode** (optional): sends task list + budget state to a local Ollama model for prioritized execution plan — better for complex task dependency chains
- Routing mode is a runtime Setting (`task_router.mode`)

### Token Budget Tracking
- `models` table: `token_budget_per_window`, `window_duration_hours`, `tokens_used_this_window`, `window_reset_at`
- `token_usage_log` table: every API call records tokens consumed, model, task_id, timestamp
- Anthropic: 5-hour windows. Other providers: configured per `models` row

---

## 7. Data Model Summary

### Schema Groups

| Group | Tables |
|-------|--------|
| **Conversation** | `conversations`, `messages` |
| **Agent Registry** | `agents` |
| **Task System** | `tasks`, `task_attachments` |
| **Quick Actions** | `quick_actions`, `heartbeat_log` |
| **Model Registry** | `models`, `model_api_keys`, `token_usage_log` |
| **Tool Registry** | `tools` |
| **Hook Registry** | `hook_handlers` |
| **Agent Message Bus** | `agent_messages` |
| **Shutdown Recovery** | `system_checkpoints`, `in_flight_operations` |
| **Runtime Settings** | `settings` |
| **Sidecar Job Queue** | `sidecar_jobs` |
| **Memory Core** | `master_sessions`, `chunks`, `topic_nodes`, `topic_edges`, `chunk_topics`, `topic_summaries`, `sss_snapshots`, `procedural_notes`, `praxis_recommendations`, `behavioral_sequences`, `injection_log` |

### Key Design Notes
- `model_api_keys.key_value` encrypted at rest — never stored or logged in plaintext
- `settings` table seeded from `ordo.yaml` on first boot; DB value wins at runtime
- `agent_messages` polled on agent boot to recover unacknowledged messages from before shutdown
- `sidecar_jobs` is the Redis replacement for slow-lane coordination — no pub/sub required
- All vector embeddings: 768-dim, HNSW index (m=16, ef_construction=64)
- `soul.md` path resolves to `$ORDO_DATA_DIR/soul.md`

### Shutdown Recovery Procedure
On FastAPI startup, the recovery bootstrap runs before accepting requests:
1. Query `in_flight_operations WHERE status = 'in_flight'`
2. For each row: re-queue as a new `sidecar_jobs` entry (if `operation_type` is a sidecar job) or as a new `agent_messages` entry (if agent coordination) with `retry_count` incremented
3. Mark the original `in_flight_operations` row as `status: recovered`
4. Log recovered operations to structured log

`system_checkpoints` stores conversation and task state snapshots written at turn boundaries. On recovery, the UI rehydrates the last checkpoint for any open conversation rather than showing a blank slate.

---

## 8. TTS / STT

- **STT**: Local Whisper (primary — offline, low-latency) → OpenAI Whisper API (fallback for accuracy)
- **TTS**: OpenAI TTS (primary) → `pyttsx3` local (fallback)
- **PTT**: Global hotkey registered by Electron → IPC signal to TTS/STT PM2 daemon → start/stop recording
- **No wake word** — push-to-talk only
- Daemon exposes a local socket/HTTP interface; Electron IPC calls `start_recording` / `stop_recording`
- Transcribed text POSTed to FastAPI conversation endpoint; TTS audio streamed back to Electron for playback

---

## 9. Observability

| Layer | Tool | Notes |
|-------|------|-------|
| LLM traces + evals | **Phoenix (Arize)** port 6006 | Open source, local, PM2 process, native LangChain integration via OpenTelemetry |
| Process health | **PM2 Monitor** | CPU, memory, restart count per process |
| Structured logs | JSON to rotating files | FastAPI middleware, per-sidecar logs |
| Memory core | Sidecar slide-in panel | Status, last-run, turn counters, injection stats |
| Budget tracking | Status bar + Settings | Token window usage per provider |

Phoenix link accessible directly from Electron status bar (opens in browser).

---

## 10. Inter-Service Communication

| Path | Mechanism |
|------|-----------|
| Electron → FastAPI | HTTP REST + WebSocket (streaming) |
| FastAPI → Fast Sidecars | `asyncio.create_task()` — in-process, no IPC |
| FastAPI → Slow Sidecars | Write `sidecar_jobs` row; sidecar polls Postgres |
| Agent → Agent | Write `agent_messages` row; receiving agent polls Postgres |
| Electron → TTS/STT Daemon | Electron IPC → named pipe / local HTTP |
| Telegram Bridge → FastAPI | HTTP POST to `/agents/generalist/invoke` |
| Heartbeat → FastAPI | HTTP POST (self-call) or direct function call if co-located |
| LAN clients → FastAPI | HTTP via Nginx reverse proxy (port 80 → 8000) |

---

## 11. Features Carried Forward from V3

| Feature | V4 Change |
|---------|-----------|
| Voice loop (PTT, Whisper, TTS) | Same behavior, now a PM2 daemon with Electron IPC |
| Memory Core | Rewritten as 8-sidecar model, phased across builds |
| Memory Explorer UI | Becomes the Sidecar slide-in panel |
| Task Hub | Rebuilt with token budget router and agent message bus pickup |
| Action DB + Heartbeat | `quick_actions` table, ≥5 min PM2 scheduler |
| Telegram Bridge | Carried forward, routes to generalist agent |
| LAN Control Plane API | Merged into FastAPI, served via Nginx |
| Playwright Co-browsing | Tool in Tool Registry |
| Gmail Tools | Tool in Tool Registry |
| Markdown rendering | Frontend (Vite/TS component) |
| Tool Discovery Registry | `tools` table, carried forward |
| Global hotkeys | Electron-native, no wake word |

## 12. Features Dropped

| Feature | Reason |
|---------|--------|
| Spotify integration | Not used |
| Wake word engine | Not used — PTT only |
| Python desktop UI | Replaced by Electron + Vite/TS |
| Single-container Docker | No virtualization available |
| Redis | Replaced by Postgres-backed queues |
