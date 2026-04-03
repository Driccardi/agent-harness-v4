# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI-Assistant Version 4** is a greenfield rewrite of a cognitive memory-augmented virtual assistant stack. The core infrastructure is **Memory-Core as a Service (MCaaS)** — a containerized, persistent memory substrate that runs beneath Claude Code via hook-based sidecar processes. It is inspired by human cognitive architecture (hippocampal fast-lane ingestion + cortical slow-lane consolidation) and handles memory capture, classification, injection, consolidation, and prediction automatically.

Remote git: `https://github.com/Driccardi/agent-harness-v4.git`

### Subsystems

| Subsystem | Location | Role |
|-----------|----------|------|
| **Memory-Core API** | `memory-core/mcaas_clean/memory-core/` | FastAPI REST service on port 4200 |
| **Sidecar constellation** | `memory-core/mcaas_clean/memory-core/sidecars/` | 8 cognitive processing workers |
| **Hook integration** | `memory-core/mcaas_clean/memory-core/hooks/` | Claude Code lifecycle intercepts |
| **Adapters** | `memory-core/mcaas_clean/adapters/` | Claude Code, LangChain, OpenAI integrations |
| **Client SDK + CLI** | `memory-core/mcaas_clean/client/` | `MemoryCoreClient` async SDK + `mc` CLI |
| **Ordo Spec** | `memory-core/ordo-spec/` | Canonical architecture specifications |
| **Released features PRD** | `current-released-features-prd.md` | What is currently shipped |

---

## Commands

All commands run from `memory-core/mcaas_clean/`:

```bash
# First-time setup (builds image, starts container, initializes volumes)
make setup

# Docker lifecycle
make build         # Build Docker image
make up            # Start container
make down          # Stop container
make status        # Show all internal service statuses (postgres, redis, ollama, sidecars, api)
make health        # Check container health endpoint
make logs          # Tail all container logs
make logs-api      # API logs only
make logs-engram   # Engram worker logs only
make shell         # Open shell inside the container

# Testing
make test          # pytest tests/ -v --tb=short
make test-e2e      # End-to-end integration tests (requires running container)

# Single test
pytest tests/test_mcaas.py::TestEngram -v
pytest tests/ -k "test_gate" -v

# Linting
make lint          # flake8 --max-line-length=100

# Memory state
make export        # Export full memory state to backup.json
make import        # Import from backup.json
make export-stats  # Show statistics without downloading

# Reflective pipeline (normally fires at session_end)
make reflective    # Manually trigger: Kairos → Praxis → Oneiros → Psyche → Augur

# Maintenance
make upgrade       # Pull latest image, preserve volumes
make clean         # Remove containers, preserve volumes
make clean-all     # Remove containers + volumes (destructive)
```

### CLI (`mc`)

```bash
# Requires MC_SESSION_KEY env var
mc search --query "JWT auth"
mc soul                        # Print current soul.md
mc sss                         # Print Synthetic Somatic State
mc rupture-check               # Check relational rupture status
mc predict intent              # Print Augur intent predictions
mc topics                      # List knowledge graph topics
mc health                      # API health check
```

### Required Environment Variables

Copy `.env.example` to `.env` in `memory-core/mcaas_clean/memory-core/`:

```
ANTHROPIC_API_KEY=...          # Required — used by Eidos, Psyche, Oneiros, Kairos, Augur, RIP
MC_SESSION_KEY=...             # Client auth key
MC_ADMIN_KEY=...               # Admin operations key
MC_HUMAN_ID=...                # Persistent human identity
MC_AGENT_ID=...                # Persistent agent identity
MC_BASE_URL=http://localhost:4200
```

---

## Architecture

### Deployment Model

Everything runs in a **single Docker container** managed by Supervisor:

1. PostgreSQL 16 + pgvector (priority 10)
2. Redis (priority 10)
3. Ollama with `nomic-embed-text` (priority 20)
4. Engram worker + Eidos worker (priority 30)
5. Reflective scheduler (priority 40)
6. Uvicorn / FastAPI API on port 4200 (priority 50)

### The Eight-Sidecar Constellation

| Sidecar | Cognitive Analog | Key Behavior |
|---------|-----------------|--------------|
| **Engram** | Hippocampus | Real-time stream embedder. Ingests ALL events. Never prunes. Latency target: <50ms. |
| **Eidos** | Amygdala | Classifies signals, attaches somatic tags. Uses Claude Haiku. 200ms timeout. |
| **Anamnesis** | Associative recall | Injection agent. Conjunctive gate — all dimensions must pass. Biased toward silence. |
| **Kairos** | Cortical consolidation | Builds knowledge graph + progressive summary stack. Fires every 20 turns + session end. |
| **Oneiros** | Sleep/dreams | Lossy belief consolidation. **This is the ONLY forgetting mechanism.** Generalizes episodes into standing beliefs, discards temporal scaffolding. |
| **Praxis** | Muscle memory | Procedural memory optimizer. Modes 1-3 (auto, requires-approval, requires-approval). |
| **Psyche** | Self-awareness | Writes `soul.md`. Its injections bypass the Anamnesis gate unconditionally. Fires every 50 turns + emotional signals + session end. |
| **Augur** | Anticipation | Learns behavioral n-gram patterns, generates intent predictions and prefetch queries. Retrains every 50 sessions. |

### Hook Intercept Points

Six Claude Code hook files connect the agent lifecycle to the sidecar pipeline:

| Hook | Role |
|------|------|
| `session_start.py` | Init master session, inject orientation + Augur prediction briefing |
| `user_prompt_submit.py` | Ingest HUMAN chunk (priority 1.0), run RIP somatic assessment, trigger Anamnesis injection |
| `pre_tool_use.py` | Anamnesis injection (450ms latency budget), Augur prefetch update |
| `post_tool_use.py` | Ingest tool I/O, validate provisional chunks |
| `pre_compact.py` | Snapshot compaction-vulnerable chunks for priority re-injection |
| `session_end.py` | Fire full reflective pipeline (no latency budget): Kairos → Praxis → Oneiros → Psyche → Augur |

### Memory Flow (Two-Speed Model)

- **Fast lane (Engram):** Synchronous, every event, <50ms, no filtering — complete record
- **Slow lane (reflective sidecars):** Async, scheduled or session-end, no latency constraint — consolidation, generalization, prediction, self-narrative

### Anamnesis Conjunctive Gate

Injection is blocked if ANY of these fail:
1. Similarity threshold (base: 0.78, age-penalized)
2. In-context redundancy check (threshold: 0.92)
3. Net-new content assessment (threshold: 0.88)
4. Recency bias (within last 5 turns)
5. Topic diversity quota (max 3 per topic per 10-turn window)

### Confusion Scoring (6 Tiers)

Composite score from contradiction rate, reasoning inflation, tool repetition, hedge frequency:

| Tier | Score | Effect |
|------|-------|--------|
| nominal | ≤0.30 | Normal (3 injections/turn max) |
| elevated | ≤0.45 | +0.05 similarity threshold offset |
| warning | ≤0.60 | 2 injections/turn max |
| high | ≤0.75 | 1 injection/turn, system-only |
| critical | ≤0.90 | Injection suspended |
| full_stop | >0.90 | Suspended + notify human |

### Data Layer

- **PostgreSQL 16 + pgvector**: Primary vector store. HNSW index (m=16, ef_construction=64). 768-dim embeddings.
- **Redis**: Event queue between hooks and workers.
- **Ollama + nomic-embed-text**: Local embeddings — no external API dependency.
- **Anthropic SDK**: Claude Haiku for Eidos classification; Claude Sonnet/Opus for Kairos, Oneiros, Psyche, Augur synthesis.

Key tables: `chunks`, `master_sessions`, `topic_nodes`, `topic_edges`, `chunk_topics`, `topic_summaries`, `sss_snapshots`, `behavioral_sequences`, `procedural_notes`, `praxis_recommendations`, `injection_log`.

### RIP Engine (Relational Consciousness)

`rip/engine.py` implements the Reflective Indistinguishability Principle. It tracks a **Synthetic Somatic State (SSS)** — six affective dimensions updated every turn — and selects relational intents via a priority ordering (REPAIR: 100, GROUND: 90, WITNESS: 80, …). Rupture detection overrides all other intents until repair is confirmed.

### Multi-Framework Adapter Pattern

All framework adapters translate native hook payloads to a `UniversalEvent` schema and POST to `http://localhost:4200/v1/ingest`. The `EventType` enum covers: `HUMAN_TURN`, `MODEL_TURN`, `MODEL_REASONING`, `TOOL_USE`, `TOOL_RESULT`, `SKILL_INVOKE`, `SKILL_RESULT`, `SYSTEM_MESSAGE`, `SESSION_START`, `SESSION_END`, `HUMAN_CORRECTION`.

---

## Critical Design Constraints

- **Engram NEVER prunes.** Only Oneiros handles forgetting. Violating this breaks the complete-record invariant.
- **Anamnesis gate is biased toward silence.** All gate dimensions must pass — a single failure blocks injection. Do not add "helpful" bypasses.
- **Praxis Modes 2 and 3 always require human approval.** Autonomous skill file modification is prohibited.
- **Psyche steering injections bypass the Anamnesis gate unconditionally** — they carry the self-narrative and must not be filtered.
- **Provisional chunks** (REASONING events, confidence 0.4) must be validated within K=5 turns or be abandoned — never deleted. Negative knowledge is preserved.
- **soul.md** is a living document written by Psyche. Treat it as runtime state, not static config.
- **Configuration precedence:** `ordo.yaml` → `ordo.local.yaml` (gitignored) → env vars. Always use env vars for secrets.

---

## Key Specification Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Master spec | `memory-core/ordo-spec/00-ordo-overview.md` | Authoritative architecture reference |
| Sidecar specs | `memory-core/ordo-spec/01-engram.md` … `08-augur.md` | Per-sidecar contracts |
| Shared contracts | `memory-core/ordo-spec/09-contracts.md` | `UniversalEvent`, `InjectionBlock`, shared schemas |
| Governance | `memory-core/ordo-spec/10-governance.md` | Data governance, privacy, threat model |
| Agent instructions | `memory-core/mcaas_clean/AGENTS.md` | How any LLM agent must behave with memory-core |
| Released features | `current-released-features-prd.md` | What is currently shipped (voice loop, desktop UI, Spotify, LAN control, task hub, etc.) |
