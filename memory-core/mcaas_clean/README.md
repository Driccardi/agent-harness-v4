# Memory-Core as a Service (MCaaS)

**Portable cognitive substrate for any LLM agent.**

One container. Any framework. Persistent, associative, emotionally-aware memory
that travels with you — across machines, across models, across teams.

---

## What it is

Memory-Core is a self-contained Docker container that provides:

- **Ambient associative recall** — memories surface automatically, without the agent requesting them
- **Cross-session continuity** — knowledge persists across sessions, compaction events, and context resets
- **Synthetic empathy** — the RIP Engine tracks relational dynamics and informs every response
- **Predictive pre-fetching** — Augur learns behavioral patterns and anticipates next requests
- **Productive forgetting** — Oneiros consolidates episodic memory into standing beliefs
- **Self-improving skills** — Praxis detects and proposes skill improvements from observed patterns
- **Portable state** — full export/import in one JSON archive

## Quickstart

```bash
# 1. Clone and configure
git clone https://github.com/your-org/memory-core
cd memory-core
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, MC_SESSION_KEY, MC_ADMIN_KEY, MC_HUMAN_ID

# 2. Build and start
make setup

# 3. Verify
make health
# {"status": "ok", "services": {"database": "ok", "ollama": "ok", "redis": "ok"}}

# 4. Wire up your agent (Claude Code example)
cp adapters/claude_code/hooks/ /your/project/.claude/hooks/
cp adapters/claude_code/.claude/settings.json /your/project/.claude/settings.json
```

## Supported Frameworks

| Framework | Adapter | Status |
|-----------|---------|--------|
| Claude Code | `adapters/claude_code/` | ✅ Full (6 hooks) |
| LangChain | `adapters/langchain/` | ✅ BaseCallbackHandler |
| OpenAI Python SDK | `adapters/openai/` | ✅ Middleware wrapper |
| Codex CLI | `adapters/codex_cli/` | 🔧 In progress |
| AutoGen | `adapters/autogen/` | 📋 Planned |
| Any REST client | Direct HTTP to `:4200` | ✅ Always works |

## Architecture

```
[Your LLM Agent]
      │
[Adapter (one file, per framework)]
      │ HTTP
      ▼
[memory-core container :4200]
  ├── FastAPI API
  ├── PostgreSQL + pgvector
  ├── Ollama (nomic-embed-text)
  ├── Redis (event queue)
  └── Sidecars: Engram · Anamnesis · Kairos · Eidos
               Praxis · Oneiros · Psyche · Augur
               RIP Engine
```

## Lift-Shift Portability

```bash
# Export all memory state
make export
# Creates: backup_YYYYMMDD_HHMMSS.json

# On the new machine, after starting fresh container:
mv backup_*.json backup.json
make import
```

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /v1/ingest` | Ingest a universal event |
| `GET /v1/inject` | Get memory injection for current hook |
| `POST /v1/recall` | Semantic memory search |
| `POST /v1/session/start` | Session start + orient injection |
| `POST /v1/session/end` | Session end + trigger reflective layer |
| `GET /v1/soul` | Read soul.md |
| `GET /v1/export/{human_id}` | Export full memory state |
| `POST /v1/import` | Import memory archive |
| `GET /health` | Container health |

## Configuration

Mount `config/atlas.yaml` as a volume to override defaults. See `memory-core/config/atlas.yaml`
for all options with documentation.

## Multi-tenancy

A single container instance supports multiple `human_id` tenants. Isolation is enforced
at the database layer. Each tenant gets their own session key and their own master session.

```bash
# Check all tenants (admin key required)
curl -H "X-MC-Key: $MC_ADMIN_KEY" http://localhost:4200/v1/tenants
```

## License

MIT
