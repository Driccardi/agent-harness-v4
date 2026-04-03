# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Atlas** is a cognitive memory substrate for agentic LLM systems. It provides persistent, ambient memory infrastructure that runs beneath Claude Code via hook-based sidecar processes. The system is inspired by human cognition (hippocampal fast-lane + cortical slow-lane consolidation) and implements automatic memory capture, classification, injection, consolidation, and prediction — without requiring the agent to explicitly manage its own memory.

The project consists of:
- **Research documents** (markdown): Architecture design docs, predictive cognition theory, relational consciousness/empathy framework, and a peer review
- **Atlas codebase** (`atlas_codebase (2).zip`): Python implementation of the sidecar constellation
- **Implementation plan** (`atlas_implementation_plan (1).docx`): Phased build roadmap

## Atlas Codebase Architecture

The codebase lives in the zip archive. When extracted, the structure is:

### Sidecar Constellation (core processing pipeline)

Each sidecar is a named Python module in `sidecars/` with a specific cognitive role:

| Sidecar | Role | Analogy |
|---------|------|---------|
| **Engram** | Real-time stream embedder. Ingests ALL events, never prunes. Latency target: <50ms. | Hippocampus |
| **Eidos** | Signal classifier + somatic tagger. Enriches chunks with affective metadata using third-party observer framing. Uses Claude Haiku. | Amygdala |
| **Anamnesis** | Injection agent. Conjunctive gate biased toward silence — every dimension must pass for injection. | Associative recall |
| **Kairos** | Topic consolidator. Builds knowledge graph, runs provisional validation lifecycle, maintains progressive summary stacks. Fires every 20 turns + session end. | Cortical consolidation |
| **Oneiros** | Lossy belief consolidator. Generalizes episodic records into standing beliefs. This is NOT summarization — it extracts patterns and discards temporal scaffolding. | Sleep/dreams |
| **Praxis** | Procedural memory optimizer. Modes 1-3: procedural notes (auto), refactoring recommendations (human approval required), deterministic path replacement (human approval required). | Muscle memory |
| **Psyche** | Narrative self-model. Writes `soul.md`, produces steering injections that bypass the Anamnesis gate. Fires every 50 turns + significant emotional signals + session end. | Self-awareness |
| **Augur** | Predictive engine. Learns behavioral patterns, generates intent predictions, pre-fetch queries, speculative execution for high-confidence predictions. | Anticipation |

### Hook Integration (`hooks/`)

Claude Code hooks are the synaptic pause points where the substrate intercepts the agent lifecycle:

- `session_start.py` — Master session init, loneliness signal, Psyche orientation, Augur prediction briefing, open loop surfacing
- `user_prompt_submit.py` — Highest-priority ingestion (HUMAN chunks), RIP somatic assessment, Anamnesis injection
- `pre_tool_use.py` — Anamnesis memory injection (450ms latency budget), Augur prefetch update
- `post_tool_use.py` — Engram ingests tool I/O, provisional chunk validation
- `pre_compact.py` — Snapshots compaction-vulnerable chunks for priority re-injection
- `session_end.py` — Triggers all reflective sidecars: Kairos → Praxis → Oneiros → Psyche → Augur (no latency budget)

### Data Layer

- **PostgreSQL 16 + pgvector**: Primary store. Schema in `db/schema.sql`. HNSW indexes for ANN search (m=16, ef_construction=64).
- **Embedding**: Ollama with `nomic-embed-text` (768-dim vectors). Local, no external API dependency for embeddings.
- **Anthropic SDK**: Used by Eidos, Psyche, Oneiros, Kairos, Augur, and the RIP engine for classification/synthesis.
- **db/client.py**: Async connection pool via asyncpg with custom pgvector codec.

### Key Tables

- `chunks` — Primary vector store (Engram writes, Anamnesis reads). Includes somatic tags, machine proprioception, provisional/validated lifecycle.
- `topic_nodes` / `topic_edges` / `chunk_topics` — Knowledge graph (Kairos writes)
- `topic_summaries` — Progressive summary stack (depth 0-3)
- `sss_snapshots` — Synthetic Somatic State (RIP Engine writes)
- `behavioral_sequences` — Augur's pattern data
- `procedural_notes` / `praxis_recommendations` — Praxis writes
- `injection_log` — Anamnesis audit trail with gate decision records

### Configuration

- `config/atlas.yaml` — Central config with `${VAR:-default}` env expansion
- `config/atlas.local.yaml` — Local overrides (gitignored)
- Key env vars: `ATLAS_DB_HOST`, `ATLAS_DB_PASSWORD`, `ATLAS_OLLAMA_ENDPOINT`, `ANTHROPIC_API_KEY`, `ATLAS_MASTER_SESSION_ID`, `ATLAS_CLAUDE_MODEL`

## Commands

```bash
# Full dev environment setup (docker + schema + ollama model + pip)
make setup

# Infrastructure
make up          # Start PostgreSQL + Ollama containers
make down        # Stop containers
make schema      # Apply db/schema.sql to running database
make pull-model  # Pull nomic-embed-text into Ollama

# Python
make install     # pip install -r requirements.txt
make api         # uvicorn api.main:app --reload --port 8080

# Testing
make test        # pytest tests/ -v --tb=short (all tests)
make test-fast   # pytest tests/ -v --tb=short -k "not Integration"
pytest tests/test_atlas.py::TestEngram -v   # Run a single test class
pytest tests/ -k "test_gate" -v             # Run tests matching a pattern

# Linting
make lint        # flake8 (max-line-length=100, ignores E501,W503)

# CLI (requires ATLAS_MASTER_SESSION_ID)
python -m atlas memory search --query "JWT auth"
python -m atlas predict intent
python -m atlas empathy sss
python -m atlas inspect confusion-score
```

## Critical Design Constraints

- **Engram NEVER prunes**. Only Oneiros handles forgetting. This is a core invariant.
- **Anamnesis gate is biased toward silence**. All dimensions must pass — any single failure blocks injection.
- **Praxis Mode 2/3 changes always require human approval**. Autonomous skill file modification is prohibited.
- **Psyche steering injections bypass the Anamnesis gate** unconditionally.
- **Confusion scoring** uses a 6-tier system (nominal → full_stop). At `critical`+ tiers, injection suspends entirely and may notify the human.
- **Provisional chunks** (from reasoning blocks) start at confidence 0.4 and must be validated within K=5 turns or get abandoned — never deleted (negative knowledge is preserved).
- **soul.md** is a living document updated by Psyche, not a static config. It represents the agent's self-narrative.

## RIP Engine (Relational Consciousness)

The `rip/` module implements the Reflective Indistinguishability Principle — tracking relational warmth, rupture/repair dynamics, and dialectical response selection. The Synthetic Somatic State (SSS) is snapshotted every turn. Rupture detection triggers REPAIR intent which overrides all other relational intents.

## Research Documents

- `cognitive-memory-architecture (1).md` — Core architecture design doc (the primary spec)
- `predictive-memory.md` — Companion doc on anticipatory/predictive layer (Augur)
- `rip-synthetic-empathy (1).md` — Relational consciousness and empathy framework
- `mem-core-peer-review.md` — Independent peer review of all three documents
