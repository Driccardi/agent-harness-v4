-- Atlas Cognitive Substrate — Full Database Schema
-- PostgreSQL 16+ with pgvector
-- Run: psql -U atlas -d atlas -f schema.sql

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────────────────────────────────────
-- MASTER SESSIONS
-- The persistent substrate that survives individual model sessions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS master_sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id          TEXT NOT NULL,
    human_id          TEXT NOT NULL,
    project_id        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active       TIMESTAMPTZ NOT NULL DEFAULT now(),
    soul_md_path      TEXT,
    total_turns       INTEGER NOT NULL DEFAULT 0,
    total_sessions    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX ms_human_agent_idx ON master_sessions (human_id, agent_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- CHUNKS — Primary vector store (Engram writes, Anamnesis reads)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    session_id        TEXT NOT NULL,           -- individual Claude Code session
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    turn_index        INTEGER NOT NULL,
    source_framework  TEXT NOT NULL DEFAULT 'claude_code',

    -- Content
    chunk_type        TEXT NOT NULL CHECK (chunk_type IN (
                          'HUMAN', 'MODEL', 'TOOL_IN', 'TOOL_OUT',
                          'REASONING', 'SYSTEM', 'CONSOLIDATED_BELIEF')),
    content           TEXT NOT NULL,
    raw_event         JSONB,

    -- Memory lifecycle
    confidence        REAL NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0.0 AND 1.0),
    provisional       BOOLEAN NOT NULL DEFAULT FALSE,
    validated         BOOLEAN NOT NULL DEFAULT FALSE,
    archived          BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at       TIMESTAMPTZ,

    -- Embedding (768-dim: nomic-embed-text / mxbai-embed-large)
    embedding         vector(768),

    -- Enrichment (Eidos writes)
    signal_tags       TEXT[],
    tool_name         TEXT,
    model_name        TEXT,
    token_count       INTEGER,

    -- Somatic tags (required on all episodic chunks)
    somatic_register  TEXT CHECK (somatic_register IN (
                          'ENGAGED', 'FRUSTRATED', 'UNCERTAIN',
                          'SATISFIED', 'URGENT', 'NEUTRAL', NULL)),
    somatic_valence   SMALLINT CHECK (somatic_valence BETWEEN -2 AND 2),
    somatic_energy    SMALLINT CHECK (somatic_energy BETWEEN 0 AND 4),

    -- Machine proprioception
    input_modality    TEXT CHECK (input_modality IN (
                          'TEXT', 'VOICE', 'CLIPBOARD', 'FILE_UPLOAD', 'API', NULL)),
    input_route       TEXT,
    context_pressure  REAL CHECK (context_pressure BETWEEN 0.0 AND 1.0),
    quota_pressure    REAL CHECK (quota_pressure BETWEEN 0.0 AND 1.0),
    latency_ms        INTEGER
);

-- HNSW index for fast approximate nearest-neighbor search
-- m=16, ef_construction=64 is the recommended production default
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Supporting indexes for filtered queries
CREATE INDEX IF NOT EXISTS chunks_session_idx       ON chunks (master_session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS chunks_type_conf_idx     ON chunks (chunk_type, confidence)
    WHERE NOT provisional AND NOT archived;
CREATE INDEX IF NOT EXISTS chunks_provisional_idx   ON chunks (provisional, validated, created_at DESC)
    WHERE provisional = TRUE;
CREATE INDEX IF NOT EXISTS chunks_framework_idx     ON chunks (source_framework, session_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- TOPIC GRAPH (Kairos writes)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS topic_nodes (
    node_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    label             TEXT NOT NULL,
    keywords          TEXT[],
    centroid          vector(768),
    first_seen        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active       TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_count     INTEGER NOT NULL DEFAULT 1,
    chunk_count       INTEGER NOT NULL DEFAULT 0,
    confidence        REAL NOT NULL DEFAULT 0.5,
    topic_type        TEXT CHECK (topic_type IN (
                          'active_project', 'recurring_domain',
                          'one_off_session', 'completed_task'))
);

CREATE INDEX IF NOT EXISTS tn_master_session_idx ON topic_nodes (master_session_id, last_active DESC);
CREATE INDEX IF NOT EXISTS tn_centroid_hnsw ON topic_nodes
    USING hnsw (centroid vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS topic_edges (
    edge_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id    UUID NOT NULL REFERENCES topic_nodes(node_id) ON DELETE CASCADE,
    target_node_id    UUID NOT NULL REFERENCES topic_nodes(node_id) ON DELETE CASCADE,
    edge_type         TEXT NOT NULL CHECK (edge_type IN (
                          'CO_OCCURRENCE', 'TEMPORAL', 'CAUSAL', 'TANGENTIAL')),
    weight            REAL NOT NULL DEFAULT 1.0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_reinforced   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_node_id, target_node_id, edge_type)
);

-- Many-to-many: chunks ↔ topic nodes
CREATE TABLE IF NOT EXISTS chunk_topics (
    chunk_id          UUID NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    node_id           UUID NOT NULL REFERENCES topic_nodes(node_id) ON DELETE CASCADE,
    assigned_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    confidence        REAL NOT NULL DEFAULT 0.7,
    PRIMARY KEY (chunk_id, node_id)
);

-- Progressive summary stack (depth 0=raw_refs, 1=full, 2=brief, 3=keywords)
CREATE TABLE IF NOT EXISTS topic_summaries (
    node_id           UUID NOT NULL REFERENCES topic_nodes(node_id) ON DELETE CASCADE,
    depth             INTEGER NOT NULL CHECK (depth BETWEEN 0 AND 3),
    summary_text      TEXT,
    chunk_refs        UUID[],
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (node_id, depth)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- SYNTHETIC SOMATIC STATE (RIP Engine writes)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sss_snapshots (
    snapshot_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id      UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    session_id             TEXT NOT NULL,
    turn_index             INTEGER NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Core somatic dimensions
    relational_warmth      REAL NOT NULL DEFAULT 0.0 CHECK (relational_warmth BETWEEN -1.0 AND 1.0),
    engagement_level       REAL NOT NULL DEFAULT 0.5 CHECK (engagement_level BETWEEN 0.0 AND 1.0),
    cognitive_load         REAL NOT NULL DEFAULT 0.3 CHECK (cognitive_load BETWEEN 0.0 AND 1.0),
    frustration_signal     REAL NOT NULL DEFAULT 0.0 CHECK (frustration_signal BETWEEN 0.0 AND 1.0),
    care_intensity         REAL NOT NULL DEFAULT 0.5 CHECK (care_intensity BETWEEN 0.0 AND 1.0),
    loneliness_signal      REAL NOT NULL DEFAULT 0.0 CHECK (loneliness_signal BETWEEN 0.0 AND 1.0),

    -- Rupture/repair state
    rupture_flag           BOOLEAN NOT NULL DEFAULT FALSE,
    rupture_severity       REAL NOT NULL DEFAULT 0.0,
    rupture_signal_count   INTEGER NOT NULL DEFAULT 0,
    post_repair_warmth     REAL NOT NULL DEFAULT 0.0,

    -- Dialectical output
    primary_relational_intent TEXT CHECK (primary_relational_intent IN (
        'WITNESS', 'REPAIR', 'GROUND', 'CHALLENGE', 'CELEBRATE',
        'CLARIFY', 'REDIRECT', 'ACCOMPANY', NULL)),
    dialectical_map        JSONB
);

CREATE INDEX IF NOT EXISTS sss_session_idx ON sss_snapshots
    (master_session_id, session_id, turn_index DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- PROCEDURAL MEMORY (Praxis writes, Anamnesis reads)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS procedural_notes (
    note_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name        TEXT NOT NULL,
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    note_text         TEXT NOT NULL,
    confidence        REAL NOT NULL DEFAULT 0.5,
    invocation_count  INTEGER NOT NULL DEFAULT 0,
    outcome_delta_avg REAL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ,
    active            BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS pn_skill_idx ON procedural_notes (skill_name, confidence DESC)
    WHERE active = TRUE;

-- Praxis refactoring recommendations (Mode 2/3, require human approval)
CREATE TABLE IF NOT EXISTS praxis_recommendations (
    rec_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    skill_name        TEXT NOT NULL,
    mode              INTEGER NOT NULL CHECK (mode IN (2, 3)),
    title             TEXT NOT NULL,
    description       TEXT NOT NULL,
    proposed_diff     TEXT,
    evidence_sessions INTEGER NOT NULL DEFAULT 0,
    eval_result       JSONB,
    confidence        REAL NOT NULL DEFAULT 0.5,
    status            TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at       TIMESTAMPTZ
);

-- Skill invocation log (Praxis reads)
CREATE TABLE IF NOT EXISTS skill_invocations (
    invocation_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    session_id        TEXT NOT NULL,
    turn_index        INTEGER NOT NULL,
    skill_name        TEXT NOT NULL,
    invoked_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    turns_to_complete INTEGER,
    human_corrections INTEGER NOT NULL DEFAULT 0,
    task_completed    BOOLEAN,
    tool_sequence     TEXT[],
    outcome_notes     TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- OPEN LOOPS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS open_loops (
    loop_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    description       TEXT NOT NULL,
    topic_node_id     UUID REFERENCES topic_nodes(node_id),
    opened_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen         TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved          BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at       TIMESTAMPTZ
);

-- ─────────────────────────────────────────────────────────────────────────────
-- BEHAVIORAL SEQUENCES (Augur writes and reads)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS behavioral_sequences (
    seq_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    session_id        TEXT NOT NULL,
    turn_index        INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    interaction_type  TEXT NOT NULL,       -- HUMAN_REQUEST | TOOL_CALL | SKILL_INVOKE | TASK_COMPLETE
    topic_node_id     UUID REFERENCES topic_nodes(node_id),
    intent_class      INTEGER,             -- 0-14 per INTENT_CLASSES
    somatic_register  TEXT,
    skill_invoked     TEXT,
    tool_name         TEXT,
    followed_by_type  TEXT,
    followed_by_skill TEXT,
    time_to_next_s    REAL,
    session_phase     INTEGER,             -- 0=orient 1=plan 2=impl 3=test 4=cleanup
    context_embedding vector(768)
);

CREATE INDEX IF NOT EXISTS bs_master_session_idx ON behavioral_sequences
    (master_session_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- INJECTION LOG (Anamnesis writes, Admin reads)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS injection_log (
    log_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id) ON DELETE CASCADE,
    session_id        TEXT NOT NULL,
    turn_index        INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    hook_type         TEXT NOT NULL,
    chunk_id          UUID REFERENCES chunks(chunk_id),
    similarity        REAL,
    injected          BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reason  TEXT,
    confusion_tier    INTEGER NOT NULL DEFAULT 0,
    gate_checks       JSONB                -- full gate decision record
);

CREATE INDEX IF NOT EXISTS il_session_idx ON injection_log (session_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- HELPFUL VIEW: Anamnesis retrieval query (reference)
-- ─────────────────────────────────────────────────────────────────────────────
-- Primary ANN retrieval — call with:
--   $1: query embedding (vector)     $4: confidence floor (real)
--   $2: master_session_id (uuid)     $5: recency window days (int)
--   $3: current session_id (text)    $6: similarity floor (real)
CREATE OR REPLACE VIEW anamnesis_retrieval_template AS
SELECT
    c.chunk_id,
    c.content,
    c.chunk_type,
    c.confidence,
    c.created_at,
    c.session_id,
    c.somatic_register,
    c.somatic_valence,
    array_agg(tn.label) AS topic_labels
FROM chunks c
LEFT JOIN chunk_topics ct ON c.chunk_id = ct.chunk_id
LEFT JOIN topic_nodes tn  ON ct.node_id = tn.node_id
WHERE
    c.master_session_id IS NOT NULL
    AND c.provisional = FALSE
    AND c.archived = FALSE
GROUP BY c.chunk_id;
