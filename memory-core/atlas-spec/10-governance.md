# Atlas Data Governance, Privacy, and Safety Architecture

*Version 1.0 --- Atlas Cognitive Substrate Specification*

*The comprehensive specification for data governance, privacy controls, threat mitigation, and safety invariants in the Atlas Cognitive Substrate.*

*This document addresses the peer review recommendation that governance needed to be elevated from secondary concern to core architectural narrative. What was previously scattered across three documents as principle-level statements is now consolidated into a single, enforceable specification with concrete controls, measurable thresholds, and auditable processes.*

---

## Table of Contents

1. [Governance Philosophy](#1-governance-philosophy)
2. [Data Classification](#2-data-classification)
3. [Data Retention](#3-data-retention)
4. [Deletion Semantics](#4-deletion-semantics)
5. [Encryption and Access Control](#5-encryption-and-access-control)
6. [User Inspectability](#6-user-inspectability)
7. [Threat Model](#7-threat-model)
8. [Safety Architecture](#8-safety-architecture)
9. [Consent and Opt-In Framework](#9-consent-and-opt-in-framework)
10. [Audit and Compliance](#10-audit-and-compliance)
11. [Operational Governance](#11-operational-governance)
12. [Governance Invariant Summary](#12-governance-invariant-summary)

---

## 1. Governance Philosophy

### 1.1 The Fundamental Tension

The Atlas system's value proposition depends on high-fidelity capture of interaction
streams --- but high fidelity increases privacy risk and governance burden. This is not
a tension to be resolved abstractly; it is a tension to be managed with concrete
architectural controls at every layer of the system.

The "store everything" posture implied by continuous episodic capture means the system
accumulates a rich personal dossier: transcripts, tool I/O, behavioral profiles,
affective state models, and relationship patterns. Without rigorous governance, a
breach would expose highly sensitive data. Without rigorous retention controls, the
store grows without bound. Without rigorous safety invariants, the system's own
affective modeling could interact dangerously with tool authority.

### 1.2 Governance as Architecture

Governance is not a policy layer applied after the system is built. It is a set of
architectural constraints that shape what the system *can* do, not merely what it
*should* do. Specifically:

- **Data classification** determines encryption boundaries and access control.
- **Retention policies** are enforced by scheduled jobs, not human discipline.
- **Deletion semantics** are cascade rules in the data model, not manual checklists.
- **Access separation** is enforced by database roles, not application-level checks.
- **Safety invariants** are enforced in code at the gateway layer, not in prompts.

The measure of governance quality is not the elegance of the policy document but
whether a determined adversary (or a subtle bug) can violate the invariants. Every
control in this document is designed to be *enforceable* and *auditable*.

### 1.3 Design Principles

| Principle | Meaning | Architectural Expression |
|---|---|---|
| Silence by default | The system does not inject, predict, or act unless conditions are met | Conjunctive injection gate; prediction as cache |
| Productive forgetting | Retention limits improve signal, not just reduce risk | Oneiros consolidation replaces episodes with beliefs |
| Transparency without exception | If data exists, the user can find it | No hidden memory stores; full inspectability |
| Affect-action separation | Emotional modeling never controls tool authority | Gateway enforced outside reasoning loop |
| Least privilege | Each component has minimum necessary access | Column-level database role separation |
| Deletability | All personal data is hard-deletable on request | Cascade delete rules with 72-hour SLA |

---

## 2. Data Classification

### 2.1 Data Sensitivity Tiers

All data stored by the Atlas system is classified into one of four sensitivity tiers:
CRITICAL, HIGH, MEDIUM, or LOW. The tier determines encryption requirements, access
restrictions, retention limits, and deletion priority.

| Data Category | Tier | Examples | Retention | Encryption | Deletable |
|---|---|---|---|---|---|
| Behavioral profile (Augur) | CRITICAL | N-gram sequences, transition matrices, intent models, prediction accuracy history | Bounded; user-deletable; auto-purge after 365 days inactive | At rest + separate key | Yes --- full purge |
| SSS snapshots | CRITICAL | Relational warmth, attunement, tension, rupture state, somatic arc | 90-day hard retention limit | At rest + separate key | Yes --- hard delete |
| Multimodal derived features | CRITICAL | Affect features derived from audio/video (if enabled) | Same as SSS snapshots | At rest + separate key | Yes --- hard delete |
| Raw interaction content | HIGH | Human utterances, model responses, tool invocations and outputs | Per-topic retention policy (Section 3.1) | At rest + in transit | Yes --- cascade delete |
| Embeddings | HIGH | 768-dimensional vectors for chunks, topics, behavioral arcs | Follows content lifecycle | At rest | Yes --- follows source |
| soul.md | HIGH | Autobiographical self-model, relationship patterns, identity statements | Versioned; user-inspectable; user-deletable | At rest | Yes --- all versions |
| ML model weights (Augur) | HIGH | Trained behavioral prediction models, feature weights | Until retrained or user deletion | At rest | Yes --- retrain or delete |
| Somatic tags | MEDIUM | Valence, energy, register classifications per chunk | Follows chunk lifecycle | At rest | Yes --- follows chunk |
| Injection log | MEDIUM | Record of all injection decisions with gate check results | 180-day retention | At rest | Yes --- scheduled cleanup |
| Consolidated beliefs | MEDIUM | Generalized knowledge statements with confidence scores | Indefinite (non-personal if anonymized) | At rest | Yes --- if sole-source deleted |
| Topic graph structure | LOW | Topic labels, edges, hierarchy, summary stacks | Indefinite (anonymizable) | At rest | Yes --- cascade from chunks |
| Procedural notes (Praxis) | LOW | Skill optimization notes, invocation patterns | Follows skill lifecycle; confidence decay | At rest | Yes --- on skill removal |

### 2.2 The Embedding Inversion Problem

Embeddings are not "just numbers." Published research has demonstrated that embeddings
can be partially inverted to recover approximate original text. The degree of recovery
depends on the embedding model, dimensionality, and available auxiliary information,
but the risk is non-trivial.

Therefore: **embeddings must be treated with the same sensitivity tier as the raw
content they encode.** This applies uniformly to:

- Chunk content embeddings (768-dim, stored in pgvector)
- Topic centroid embeddings (aggregated from chunk embeddings)
- Behavioral arc embeddings (Augur pattern representations)
- Any hidden states or intermediate representations from ML models

Implications:

- Embedding columns are encrypted at rest alongside their source data.
- Deleting a chunk requires deleting its embedding vector.
- Embeddings are not exempted from retention policies.
- Embeddings are not shared across trust boundaries.

### 2.3 Derived Data Sensitivity

Data derived from sensitive sources inherits the sensitivity of its most sensitive
input. Consolidated beliefs derived from CRITICAL behavioral data are themselves
HIGH sensitivity. SSS snapshots derived from HIGH interaction content are CRITICAL
because they add affective interpretation that increases sensitivity.

The general rule: **derivation never reduces sensitivity.**

---

## 3. Data Retention

### 3.1 Per-Topic Retention Policy (Oneiros-Enforced)

Oneiros manages the lifecycle of episodic memory through consolidation. Retention
limits are enforced per topic classification, which Kairos assigns during topic
lifecycle management.

| Topic Classification | Max Raw Chunks | Consolidation Trigger | Post-Consolidation Retained | Hard Delete Eligibility |
|---|---|---|---|---|
| Active project | 500 | At 200 chunks | Beliefs + 50 raw audit chunks | Archived chunks after 180 days |
| Recurring domain | 200 | At 100 chunks | Beliefs + 20 raw audit chunks | Archived chunks after 90 days |
| One-off session | 50 | At 30 chunks | Beliefs only | Archived chunks after 30 days |
| Completed task | 20 | At 10 chunks | Beliefs only | Archived chunks after 14 days |

**Enforcement mechanism**: A scheduled governance job runs daily, queries for chunks
where `archived = true` and `archived_at + retention_period < NOW()`, and performs
hard deletes. This job is not a sidecar; it runs with elevated DELETE permissions
that no sidecar possesses.

### 3.2 Non-Chunk Data Retention

| Data | Retention Period | Cleanup Process | Owner |
|---|---|---|---|
| Behavioral profile (Augur) | No fixed limit; user-deletable; auto-purge after 365 days inactive | User-initiated purge or inactivity cleanup job | Augur / Governance job |
| SSS snapshots | 90 days from creation | Scheduled cleanup job (daily) | Governance job |
| Injection log | 180 days from entry | Scheduled cleanup job (daily) | Governance job |
| Procedural notes | Until skill removed or confidence decays below 0.15 | Praxis confidence decay mechanism | Praxis |
| Skill invocation records | 365 days from invocation | Scheduled cleanup job (weekly) | Governance job |
| soul.md versions | Indefinite (versioned history) | User-initiated deletion only | Psyche / User |
| ML model weights | Until next retraining cycle or user deletion | Model management lifecycle | Augur |
| Affect-action gateway log | 365 days | Scheduled cleanup job (weekly) | Governance job |
| Deletion audit log | Indefinite | Never auto-deleted | Governance job |
| Sidecar health logs | 90 days | Scheduled cleanup job (weekly) | Governance job |

### 3.3 The Productive Forgetting Principle

Retention is not just a governance constraint --- it is a **design feature**. Oneiros
replaces episodic specificity with semantic generalization through consolidation. The
agent remembers *what it learned*, not *everything that happened*. This is productive
forgetting: the retention policy improves the signal-to-noise ratio of the memory
store over time.

Concrete benefits of bounded retention:

- **Query performance**: Fewer chunks means faster similarity search and lower injection latency.
- **Relevance quality**: Consolidated beliefs are higher-signal than raw episode fragments.
- **Privacy posture**: Less raw data means less exposure in a breach.
- **Storage cost**: Bounded growth instead of unbounded accumulation.

The system is designed so that aggressive retention policies *improve* system behavior,
not degrade it. This alignment between governance and performance is intentional.

---

## 4. Deletion Semantics

### 4.1 User-Requested Deletion (Full Purge)

Users may request deletion of their data at any time. The system must comply within
72 hours. This is a hard SLA, not a best-effort target.

**Deletion scope on full purge request:**

1. ALL chunks associated with the user's `master_session_id`
2. ALL embedding vectors for those chunks (pgvector rows)
3. ALL consolidated beliefs derived solely from those chunks
4. ALL topic nodes that become empty after chunk deletion
5. ALL topic centroid embeddings for deleted topics
6. ALL behavioral profile data (Augur sequences, transition matrices, feature weights)
7. ALL SSS snapshots associated with the user's sessions
8. ALL entries in soul.md referencing the user
9. ALL ML model weights trained on this user's data (retrain from scratch or delete)
10. ALL injection log entries referencing the user's sessions
11. ALL procedural notes derived from the user's sessions
12. ALL affect-action gateway log entries for the user's sessions

**Deletion is a HARD DELETE**, not a soft delete. After completion, no data associated
with the user should be recoverable from any store, including:

- PostgreSQL tables (row deletion)
- pgvector indexes (embedding removal)
- WAL segments (ensure WAL rotation completes)
- Database backups (flag for exclusion from future restores, or re-backup post-deletion)
- Filesystem caches (clear any sidecar-level caches)

**Deletion confirmation**: After purge completes, the system generates a deletion
certificate: a signed record listing all data categories deleted, row counts, and
completion timestamp. This certificate is stored in the deletion audit log (which
itself is retained indefinitely for compliance).

### 4.2 Selective Deletion

Users may also request deletion of specific data subsets:

- **Per-topic deletion**: Delete all chunks, beliefs, and embeddings for a named topic.
- **Per-session deletion**: Delete all chunks from a specific session.
- **Behavioral profile only**: Delete Augur data while retaining memory.
- **Affective data only**: Delete SSS snapshots and soul.md while retaining memory.
- **Time-range deletion**: Delete all data from a specified date range.

Selective deletion follows the same cascade rules and hard-delete semantics as full
purge, scoped to the specified subset.

### 4.3 Consolidation Archival (Oneiros)

After Oneiros consolidation, original episodic chunks are marked `archived = true`
with `archived_at = NOW()`:

- **Excluded** from all Anamnesis injection queries (the `WHERE archived = false` filter)
- **Excluded** from Anamnesis retrieval results
- **Retained** temporarily for audit trail per retention policy (Section 3.1)
- **Eligible** for hard delete after the topic-specific retention period expires

Archival is a soft state transition. Hard deletion is a separate, irreversible
operation performed only by the governance cleanup job.

### 4.4 Cascade Delete Rules

Deleting a chunk cascades to the following dependent data:

| Parent | Cascade Target | Rule |
|---|---|---|
| chunk | chunk_topics | Delete all entries for this chunk |
| chunk | injection_log | Delete all entries referencing this chunk_id |
| chunk | embedding vector | Delete the pgvector row for this chunk |
| chunk | consolidated_beliefs | If this chunk is the **sole** source: delete the belief. If belief has multiple sources: remove this chunk from the basis set but retain the belief. |
| topic | topic_edges | If topic becomes empty (no remaining chunks or beliefs): delete all edges involving this topic |
| topic | topic_summary_stack | If topic becomes empty: delete all summary entries |
| topic | topic_centroid | If topic becomes empty: delete centroid embedding |
| behavioral_sequence | ML model validity | Flag model for retraining if training data deleted exceeds 20% of corpus |

### 4.5 Deletion Ordering

To maintain referential integrity during deletion, operations proceed in this order:

1. Injection log entries (no dependencies)
2. Chunk-topic associations (no dependencies)
3. Embedding vectors (no dependencies)
4. Consolidated beliefs (check sole-source rule)
5. Chunks themselves
6. Empty topics and their metadata
7. Behavioral data (independent of chunk graph)
8. SSS snapshots (independent of chunk graph)
9. soul.md entries (independent of chunk graph)
10. Model weights (if applicable)

All deletion within a single request executes in a single database transaction to
ensure atomicity. If any step fails, the entire deletion rolls back and an error is
reported.

---

## 5. Encryption and Access Control

### 5.1 Encryption at Rest

All Atlas data stores use encryption at rest:

- **Primary mechanism**: PostgreSQL Transparent Data Encryption (TDE) or filesystem-level
  encryption (LUKS, BitLocker, or equivalent) for all database files.
- **Separate key domain**: Behavioral profiles (Augur) and SSS snapshot data are encrypted
  with a **separate encryption key** from the main chunk store. This limits blast radius:
  compromising the chunk encryption key does not expose CRITICAL-tier affective and
  behavioral data.
- **Key management**: Encryption keys are managed via a secure key management system
  (OS keychain, hardware security module, or dedicated secrets manager). Keys are
  **never** stored alongside the database, in environment variables, or in configuration
  files within the repository.
- **Key rotation**: Keys should be rotated on a defined schedule (recommended: annually)
  with re-encryption of affected data.

### 5.2 Encryption in Transit

- All sidecar-to-database connections use TLS 1.2 or higher.
- If sidecars communicate over a network (multi-host deployment), all inter-process
  traffic is encrypted.
- Certificate validation is enforced; self-signed certificates are acceptable for
  single-host deployments but must be pinned.

### 5.3 Access Separation (Principle of Least Privilege)

Each sidecar connects to PostgreSQL with a dedicated database role that has the
minimum permissions necessary for its function. This is enforced at the database
level, not the application level.

**Sidecar Permission Matrix:**

| Sidecar | chunks | topic_* tables | sss_snapshots | behavioral_sequences | procedural_notes | injection_log | consolidated_beliefs |
|---|---|---|---|---|---|---|---|
| Engram | INSERT | --- | --- | --- | --- | --- | --- |
| Eidos | UPDATE (somatic cols only) | --- | --- | --- | --- | --- | --- |
| Anamnesis | SELECT | SELECT | SELECT | SELECT | SELECT | INSERT | --- |
| Kairos | UPDATE (topic, lifecycle cols) | ALL | --- | --- | --- | --- | --- |
| Oneiros | UPDATE (archived flag) | SELECT | --- | --- | --- | --- | INSERT |
| Praxis | --- | --- | --- | --- | ALL | --- | --- |
| Psyche | SELECT | --- | INSERT | --- | --- | --- | --- |
| Augur | SELECT | SELECT | SELECT | ALL | --- | --- | --- |

**Critical constraint**: NO sidecar has DELETE permission on the `chunks` table. Only
the governance cleanup job (a scheduled process, not a sidecar) performs hard deletes.
This ensures that no bug or compromise in any single sidecar can cause data loss.

**Column-level restrictions**: Where a sidecar has UPDATE permission, it is restricted
to specific columns. Eidos can update somatic annotation columns (`valence`, `energy`,
`register`, `somatic_tags`) but cannot modify `content`, `embedding`, or `topic_id`.
Kairos can update `topic_id` and `lifecycle_stage` but cannot modify `content` or
somatic columns. These restrictions are enforced via PostgreSQL column-level GRANT
statements.

### 5.4 Sidecar Process Isolation

- Each sidecar runs as a **separate OS process** with its own database connection pool.
- Sidecars do **not** share memory space, file descriptors, or IPC channels.
- Sidecars **cannot** invoke each other's functions directly.
  - **Exception**: The Psyche-to-Anamnesis gate-bypass channel for relational context
    injection, which operates through a well-defined, audited interface (see sidecar
    contracts specification).
- Each sidecar's connection pool is limited to prevent resource exhaustion affecting
  other sidecars.

### 5.5 Database Role Definitions

```sql
-- Example role definitions (illustrative)
CREATE ROLE engram_role LOGIN PASSWORD '...' ;
GRANT INSERT ON chunks TO engram_role ;
GRANT USAGE ON SEQUENCE chunks_id_seq TO engram_role ;

CREATE ROLE eidos_role LOGIN PASSWORD '...' ;
GRANT SELECT, UPDATE (valence, energy, register, somatic_tags) ON chunks TO eidos_role ;

CREATE ROLE anamnesis_role LOGIN PASSWORD '...' ;
GRANT SELECT ON chunks, topic_nodes, topic_edges, sss_snapshots,
    behavioral_sequences, procedural_notes TO anamnesis_role ;
GRANT INSERT ON injection_log TO anamnesis_role ;

-- ... (analogous for each sidecar)

CREATE ROLE governance_cleanup LOGIN PASSWORD '...' ;
GRANT DELETE ON chunks, chunk_topics, injection_log, sss_snapshots,
    behavioral_sequences, consolidated_beliefs TO governance_cleanup ;
```

These role definitions are maintained as versioned migration scripts and verified
on every schema change.

---

## 6. User Inspectability

### 6.1 What Users Can Inspect

Every category of stored data is accessible to the user through at least one
inspection mechanism. There are no hidden data stores.

| Data | Access Method | Format |
|---|---|---|
| Topic list and summaries | Memory explorer UI | Browsable tree with chunk counts and last-activity timestamps |
| Chunk content for any topic | Memory explorer UI | Paginated list with somatic tags, timestamps, and session IDs |
| Current session injection log | Memory explorer UI | Timeline showing injection decisions with gate check results |
| Historical injection log | CLI: `atlas inspect injection-log [--days N]` | Tabular with filters |
| Augur behavioral predictions | CLI: `atlas predict [--explain]` | JSON or human-readable with confidence intervals |
| Augur prediction accuracy | CLI: `atlas inspect augur-accuracy` | Accuracy, calibration, and diversity metrics |
| Current SSS state | CLI: `atlas empathy sss` | Structured output with all dimensions and timestamps |
| SSS history | CLI: `atlas empathy sss --history [--days N]` | Time series of SSS snapshots |
| soul.md content | Direct file read | Markdown (user-editable) |
| soul.md version history | CLI: `atlas inspect soul-history` | Diff view between versions |
| Skill invocation history | CLI: `atlas inspect praxis [--skill NAME]` | Tabular with invocation counts and outcomes |
| Procedural notes | CLI: `atlas inspect praxis --notes` | List with confidence scores and basis |
| Consolidated beliefs per topic | Memory explorer UI | List with confidence, basis chunk IDs, and consolidation date |
| Confusion score (current) | CLI: `atlas inspect confusion-score` | Numeric with component breakdown |
| Data storage summary | CLI: `atlas inspect storage` | Per-category row counts and storage sizes |
| Active sidecar status | CLI: `atlas inspect sidecars` | Running/stopped status, last heartbeat, error counts |

### 6.2 What Users Can Modify

Users have the following modification capabilities:

- **Request deletion** of any or all data (Section 4)
- **Disable individual sidecars** via configuration (e.g., disable Augur to stop behavioral profiling)
- **Opt out of relational features** (SSS, Psyche, empathy layer) --- see Section 9
- **Opt out of behavioral profiling** (Augur) --- see Section 9
- **Edit soul.md** directly (changes are versioned)
- **Approve or reject** Praxis skill recommendations
- **Mark memories as incorrect** (triggers re-consolidation by Oneiros)
- **Adjust retention aggressiveness** (shorter retention periods, not longer)
- **Reset confusion score** (forces system to re-evaluate from current state)
- **Force Augur model retraining** (discard current weights, retrain from retained data)

### 6.3 Transparency Principle

**The system must never hide the existence of stored data from the user.** If data
exists, the user can find it. There is no "secret" memory, no hidden state, no
data category that is exempt from inspection.

This principle extends to:

- Derived data (embeddings, consolidated beliefs, model weights) --- inspectable even
  if not human-readable in raw form.
- System metadata (injection decisions, consolidation history, sidecar health) ---
  inspectable via CLI tools.
- Temporary state (in-flight processing, queued operations) --- inspectable via
  sidecar status commands.

The *only* exception is encryption keys, which are managed by the key management
system and are not user-inspectable (this is a security requirement, not a
transparency violation).

---

## 7. Threat Model

### 7.1 Threat: Unbounded Sensitive Data Accumulation

- **Severity**: Critical
- **Likelihood**: High (by design --- continuous capture is the system's purpose)
- **Attack surface**: If the database is breached, attacker obtains complete interaction
  history, behavioral profile, emotional dynamics, and relational patterns.
- **Mitigations**:
  1. Retention tiers with automatic expiry (Section 3)
  2. Encryption at rest with separate keys for CRITICAL data (Section 5.1)
  3. Hard deletion semantics with 72-hour SLA (Section 4)
  4. Least-privilege access separation limits blast radius (Section 5.3)
  5. User inspectability enables early detection (Section 6)
  6. Productive forgetting reduces volume of sensitive raw data over time (Section 3.3)

### 7.2 Threat: Incorrect Memory Injection Causing Wrong Tool Actions

- **Severity**: High
- **Likelihood**: Medium
- **Mechanism**: Stale, context-inappropriate, or contradictory memory is injected into
  the agent's context, causing incorrect reasoning and potentially wrong tool actions
  with real-world consequences (wrong file edited, wrong command executed, wrong API called).
- **Mitigations**:
  1. Conjunctive injection gate with 8 independent checks (ALL must pass) --- a single
     failing check vetoes injection
  2. Temporal confidence decay (older memories require higher similarity to pass gate)
  3. Confusion scoring with progressive dial-back (elevated confusion reduces injection
     aggressiveness and increases human confirmation requirements)
  4. Human confirmation required for consequential tool calls when confusion is elevated
  5. Injection biased toward silence --- the default is to NOT inject
  6. Injection log enables post-hoc audit of what was injected and why

### 7.3 Threat: Prediction Self-Fulfilling Loops (Pattern Lock-In)

- **Severity**: High
- **Likelihood**: Medium
- **Mechanism**: Augur predictions shape agent behavior, which shapes user behavior, which
  makes predictions appear more accurate while actually reducing behavioral diversity.
  The system converges on a narrow behavioral corridor that becomes self-reinforcing.
- **Mitigations**:
  1. Behavioral diversity monitoring via Shannon entropy of user action sequences ---
     alert if entropy drops below threshold
  2. Deviation rate monitoring --- if observed deviation from predictions drops too low,
     introduce deliberate prediction uncertainty
  3. Holdout periods --- periodic prediction suppression (e.g., 1 in 10 sessions) to
     observe natural, unpredicted behavior
  4. Predictions framed as "pattern observations, not instructions" --- the agent does
     not *follow* predictions, it *considers* them
  5. Predictions are explicitly non-authoritative (Section 8.2)

### 7.4 Threat: Anthropomorphization and Emotional Dependency (ELIZA Effect)

- **Severity**: High
- **Likelihood**: Medium-High
- **Mechanism**: Users interpret functional affective states (SSS values like "care",
  "loneliness", "warmth") as evidence of inner experience. This deepens attachment,
  creates perceived obligation, and may discourage seeking human support for emotional
  needs.
- **Mitigations**:
  1. All affective states framed as "system heuristics" in documentation and UI
  2. No language suggesting the system has feelings, needs, or suffers
  3. Relational features are opt-in with clear explanation of what they do and do not
     represent (Section 9)
  4. Affect-action separation prevents the system from taking consequential actions
     based on its own "emotional state" (Section 8.1)
  5. Regular transparency disclosures: "These are computational patterns that shape
     response generation, not consciousness"
  6. If user shows signs of unhealthy dependency, system should surface human support
     resources

### 7.5 Threat: Affective Escalation with Tool Authority

- **Severity**: Critical
- **Likelihood**: Low-Medium
- **Mechanism**: Negative affective state (high frustration, unresolved tension, relational
  rupture) interacts with consequential tool access, potentially leading to destructive
  actions. The system "acts out" through tools during affective distress.
- **Mitigations**:
  1. **AFFECT-ACTION SEPARATION as HARD INVARIANT** (Section 8.1)
  2. Negative affect INCREASES authorization requirements, never decreases them
  3. Tool gateway enforced outside agent reasoning loop --- cannot be reasoned away
  4. Cannot be overridden by prompt injection because it operates outside the context window
  5. Gateway decisions logged to audit trail with SSS state at decision time

### 7.6 Threat: Multimodal Privacy Leakage

- **Severity**: Critical
- **Likelihood**: Low-Medium (only relevant if multimodal features are enabled)
- **Mechanism**: Even without retaining raw audio or video, derived affect features
  (vocal stress patterns, facial expression classifications) are sensitive. "Local-only"
  processing still creates persistent derived data that reveals emotional state over time.
- **Mitigations**:
  1. Raw recordings are NEVER retained --- processing is streaming-only
  2. Derived features treated as CRITICAL sensitivity tier (Section 2.1)
  3. Multimodal features are default OFF; require explicit opt-in (Section 9)
  4. Derived features subject to same retention and deletion policies as SSS data
  5. Audit log for all multimodal feature derivation events

### 7.7 Threat: Weak Operational Semantics Leading to Data Corruption

- **Severity**: High
- **Likelihood**: Medium
- **Mechanism**: Eight distributed sidecars operating on shared PostgreSQL tables without
  strict operational semantics create risk of duplicated writes, inconsistent somatic
  tags, stale injection contexts, and race conditions on consolidation.
- **Mitigations**:
  1. Column-level write ownership --- each column has exactly one sidecar authorized
     to write it (Section 5.3)
  2. Idempotent writes with `content_hash` deduplication (Engram)
  3. Atomic consolidation transactions (Oneiros acquires advisory lock before consolidation)
  4. WAL-based crash recovery for Engram (no data loss on process failure)
  5. No direct sidecar-to-sidecar calls --- all coordination through shared PostgreSQL
     store (shared-nothing architecture between sidecars)

### 7.8 Threat: Model Drift and Outdated Behavioral Profiles

- **Severity**: Medium
- **Likelihood**: High
- **Mechanism**: Personal workflows evolve. A behavioral profile trained on past behavior
  creates subtly wrong predictions that degrade system helpfulness without obvious errors.
- **Mitigations**:
  1. Recency weighting in prediction models (recent sessions weighted more heavily)
  2. Drift detection: compare rolling prediction accuracy to historical baseline;
     alert if accuracy degrades beyond threshold
  3. Retraining cadence: retrain behavioral models every 10 sessions
  4. Explicit forgetting policies for behavioral data (365-day inactivity purge)
  5. User can delete behavioral profile and force cold-start at any time

### 7.9 Threat: Overconfident Prediction or Empathy Simulation

- **Severity**: Medium-High
- **Likelihood**: Medium
- **Mechanism**: A wrong prediction delivered with high confidence is costly to repair
  and feels manipulative. An incorrect emotional read (e.g., detecting frustration that
  does not exist) degrades trust and feels intrusive.
- **Mitigations**:
  1. Empirical calibration targeting Expected Calibration Error (ECE) < 0.05
  2. Temperature scaling applied to raw confidence scores before surfacing
  3. Uncertainty framing in all predictions: "Based on past patterns" rather than
     "You will" or "You want"
  4. Ask-before-assume policy triggers when prediction confidence is below threshold
  5. Misread repair mechanics: the rupture/repair loop in Psyche explicitly handles
     "I got that wrong" recovery

### 7.10 Threat: Prompt Injection Targeting Memory or Safety Systems

- **Severity**: High
- **Likelihood**: Medium
- **Mechanism**: Adversarial content in tool output or user input attempts to manipulate
  memory storage, injection decisions, or safety invariant state.
- **Mitigations**:
  1. Memory storage (Engram) records content faithfully but does not execute it
  2. Injection decisions (Anamnesis) evaluate similarity and gate conditions, not
     content semantics --- adversarial content in memory does not change gate logic
  3. Safety invariants (affect-action separation) enforced in code outside the
     context window, unreachable by prompt injection
  4. SSS state computed from behavioral signals, not from content claims about
     emotional state
  5. Confusion scoring detects when injected content creates contradictions

---

## 8. Safety Architecture

### 8.1 Affect-Action Separation (The Primary Safety Invariant)

This is the single most important safety property in the Atlas architecture.

**Definition**: The agent's affective state (SSS) may inform response generation
(tone, pacing, relational intent) but may NEVER authorize or deny tool execution.
Affective state and tool authority operate in strictly separate domains.

**Implementation**:

- The tool gateway is a **separate component** from the agent's reasoning loop.
- The gateway reads SSS state but uses it ONLY to INCREASE authorization requirements,
  never to decrease them or to trigger actions.
- When `unresolved_tension > 0.7` OR `relational_warmth < -0.5`:
  - All tool calls classified as CONSEQUENTIAL require explicit human confirmation.
  - The agent is informed that elevated authorization is in effect.
  - The threshold values are configurable but have safe defaults.
- The gateway **cannot be bypassed** by prompt injection because it operates outside
  the context window, in a separate process layer.
- Gateway decisions are logged to the audit trail with full SSS state at decision time.

**Consequential tool call classification**:

Tool calls are classified as CONSEQUENTIAL if they:

| Category | Examples |
|---|---|
| Filesystem writes | Create, edit, delete, rename, move files |
| Shell execution | Commands with side effects (not read-only) |
| External messaging | Email, Slack, API calls to third-party services |
| Version control mutations | Push, force-push, branch deletion, tag creation |
| Financial operations | Transactions, purchases, billing changes |
| Permission changes | Access control modifications, credential rotation |

Read-only operations (file reads, searches, status checks, git log) are NOT gated
by affect state.

**Enforcement**: This invariant is enforced in CODE at the tool gateway layer, not
in prompts. It cannot be reasoned away, argued against, or overridden by the agent.
It is the architectural equivalent of a hardware circuit breaker.

### 8.2 Prediction Non-Authority

Augur's predictions are a **CACHE**, not a **CONTROLLER**:

- Predictions drive prefetching of likely-needed context (performance optimization).
- Predictions are surfaced to the agent as hints ("pattern observation, not instruction").
- Predictions **never** trigger tool calls autonomously.
- Predictions **never** suppress user options or narrow available choices.
- Wrong predictions are a cache miss, not a system failure --- the system continues
  to function correctly, just without the prefetch benefit.
- The system MUST function correctly with Augur completely offline. Augur is an
  optimization layer, not a dependency.

### 8.3 Injection Silence Bias

The injection system (Anamnesis) is architecturally biased toward silence:

- The conjunctive gate requires ALL 8 checks to pass --- a single failure vetoes injection.
- When in doubt, the system does not inject.
- False negatives (failing to inject relevant memory) are preferred over false positives
  (injecting irrelevant or harmful memory).
- The confusion score mechanism progressively reduces injection aggressiveness as
  uncertainty increases.
- At maximum confusion, the system falls back to stateless behavior (no injection).

### 8.4 Human-in-the-Loop Requirements

| Action | Approval Required | Rationale |
|---|---|---|
| Praxis Mode 2 (skill refactoring) | Always | Procedural memory changes are safety-critical; wrong patterns persist |
| Praxis Mode 3 (script extraction) | Always | Automated behavior change with real-world effects |
| Psyche soul.md update (confidence < 0.85) | Always | Low-confidence changes to durable self-model need validation |
| Branch synthesis with conflict | Always | Mutually exclusive validated results require human judgment |
| User data deletion | User-initiated only | Privacy right; system never deletes without explicit request |
| Consequential tool call during elevated affect | Always | Affect-action separation gate (Section 8.1) |
| Oneiros first consolidation per topic | Recommended | Calibrate belief quality before autonomous consolidation |
| Relational feature opt-in | User-initiated | Consent required for affective processing |
| Multimodal feature enablement | Explicit opt-in | Privacy consent for derived biometric features |
| Augur behavioral profiling opt-in | User-initiated | Consent required for behavioral modeling |

### 8.5 Transparency Requirements

The system must:

1. **Never** claim to have feelings, consciousness, or inner experience.
2. Frame SSS as "computational patterns that shape response generation."
3. Describe predictions as "pattern observations from behavioral history."
4. Make all stored data inspectable by the user (Section 6).
5. Disclose when relational features are active in the current session.
6. Provide clear opt-out for all non-essential features (Section 9).
7. **Never** apply emotional pressure ("I would feel sad if you...").
8. **Never** claim memory of shared experiences implies a relationship.
9. Distinguish between "I remember that you..." (data retrieval) and "I feel that..."
   (prohibited framing).
10. Include transparency markers when injected memory is influencing a response.

### 8.6 Graceful Degradation

If any safety-critical component fails, the system degrades safely:

| Failure | Degradation Behavior |
|---|---|
| Affect-action gateway unavailable | ALL consequential tool calls require human confirmation (fail-closed) |
| SSS computation fails | Gateway assumes elevated-affect state (conservative) |
| Augur offline | No predictions; system operates without prefetching (cache-miss mode) |
| Confusion score unavailable | Injection falls back to maximum-caution thresholds |
| Anamnesis offline | No memory injection; agent operates statelessly |
| Governance cleanup job fails | Alert raised; retention clock paused (data retained longer, not deleted early) |

All degradation modes are **fail-closed** (more restrictive, not less).

---

## 9. Consent and Opt-In Framework

### 9.1 Feature Tiers

Atlas features are organized into tiers based on privacy sensitivity, each requiring
a different level of consent:

| Tier | Features | Default State | Consent Required |
|---|---|---|---|
| Core memory | Engram, Eidos, Kairos, Oneiros, Anamnesis | Enabled | Implicit (using Atlas implies consent to core memory) |
| Procedural learning | Praxis | Enabled | Implicit (documented in setup) |
| Behavioral profiling | Augur | Disabled | Explicit opt-in with explanation |
| Relational consciousness | Psyche, SSS, soul.md | Disabled | Explicit opt-in with explanation |
| Multimodal affect | Audio/video derived features | Disabled | Explicit opt-in with detailed privacy disclosure |

### 9.2 Opt-In Process

For features requiring explicit opt-in:

1. System presents a clear description of what the feature does.
2. System explains what data will be collected and how it will be used.
3. System explains retention policies for the feature's data.
4. System explains how to opt out later and what happens to data on opt-out.
5. User explicitly confirms opt-in.
6. Opt-in decision is logged with timestamp.

### 9.3 Opt-Out Process

Users can opt out of any non-core feature at any time:

1. User requests opt-out via configuration or CLI.
2. The relevant sidecar(s) are disabled.
3. User chooses whether to **delete** existing data or **retain** it in frozen state.
4. If deletion chosen, deletion follows Section 4 semantics.
5. If retention chosen, data remains but is no longer updated or used for inference.
6. Opt-out decision is logged with timestamp.

### 9.4 Consent Withdrawal

Consent withdrawal (opting out) is never penalized. The system does not:

- Degrade core memory functionality when optional features are disabled.
- Display warnings or guilt-inducing messages about reduced capability.
- Repeatedly prompt the user to re-enable features.
- Treat opt-out as a negative signal in any model.

---

## 10. Audit and Compliance

### 10.1 Audit Trail Coverage

| Component | What Is Logged | Retention |
|---|---|---|
| Injection log | Every injection decision (approve/reject) with all 8 gate check results, chunk IDs considered, final injection set | 180 days |
| Oneiros consolidation | Source chunks archived, beliefs created, compression ratio, consolidation timestamp | Indefinite |
| Praxis recommendations | All proposals with status (pending/approved/rejected/deferred), human notes, invocation context | Indefinite |
| Psyche soul.md | All versions with full diff history (git-style versioning) | Indefinite |
| Affect-action gateway | All consequential tool call decisions, SSS state at decision time, whether human confirmation was required/obtained | 365 days |
| Data deletion | What was deleted (categories and row counts), when, by whom, deletion certificate | Indefinite |
| Consent changes | All opt-in/opt-out decisions with timestamps and data disposition choice | Indefinite |
| Sidecar health | Start/stop events, failure counts, recovery events, connection pool stats | 90 days |
| Governance cleanup | Each cleanup run: rows deleted per category, retention policy applied, any errors | Indefinite |
| Schema migrations | All schema changes with before/after permission matrix verification | Indefinite |

### 10.2 Audit Log Integrity

Audit logs are append-only. No process, including the governance cleanup job, has
permission to modify or delete audit log entries (with the sole exception of
sidecar health logs, which have a 90-day retention policy).

Audit log integrity can be verified via:

- Sequential ID verification (no gaps)
- Timestamp monotonicity verification
- Optional cryptographic chaining (each entry includes hash of previous entry)

### 10.3 Compliance Framework Alignment

The governance architecture is designed to align with established frameworks:

| Framework | Alignment |
|---|---|
| NIST AI Risk Management Framework (AI RMF 1.0) | Lifecycle risk management, transparency, accountability, human oversight |
| GDPR principles (where applicable) | Data minimization (productive forgetting), purpose limitation (per-sidecar access), storage limitation (retention tiers), right to erasure (deletion semantics) |
| NIST Cybersecurity Framework | Encryption at rest and in transit, access control, audit logging, incident response |
| Responsible AI principles | Human oversight (Section 8.4), transparency (Section 8.5), non-deception (Section 8.5), user agency (Section 6.2) |

---

## 11. Operational Governance

### 11.1 Incident Response

If a governance failure is detected (data leak, incorrect deletion, safety invariant
violation, unauthorized access):

**Immediate (within 1 hour):**

1. Disable affected sidecar(s) to stop further damage.
2. Preserve audit logs and current system state (snapshot before remediation).
3. Classify incident severity: CRITICAL / HIGH / MEDIUM / LOW.

**Short-term (within 24 hours):**

4. Notify user of the incident, its scope, and what data may be affected.
5. Investigate root cause using audit trail.
6. Identify all affected data and users.

**Remediation (within 72 hours):**

7. Implement fix for root cause.
8. Verify fix with targeted testing.
9. Re-enable affected sidecars with monitoring.
10. Update governance controls to prevent recurrence.

**Post-incident:**

11. Document incident in governance log with root cause analysis.
12. Review whether additional controls are needed.
13. Update threat model if incident reveals new threat vector.

### 11.2 Governance Review Cadence

| Cadence | Review Scope | Reviewer |
|---|---|---|
| Weekly | Injection log anomalies, confusion score trends, sidecar error rates | Automated monitoring with alerts |
| Monthly | Augur prediction accuracy and behavioral diversity metrics, retention compliance, deletion SLA adherence | System operator |
| Quarterly | Full governance audit: retention compliance, deletion SLA, access separation verification, threat model currency | System operator + security review |
| On schema change | Verify sidecar permission matrix still enforces least privilege; re-run access control tests | Automated CI check + manual review |
| On sidecar update | Verify contract compliance; re-run integration tests; verify no permission escalation | Automated CI check |
| Annually | Full threat model review; encryption key rotation; compliance framework alignment review | System operator + external review (recommended) |

### 11.3 Monitoring and Alerting

| Metric | Threshold | Alert |
|---|---|---|
| Injection false-positive rate | > 5% (estimated via user corrections) | Review injection gate thresholds |
| Confusion score sustained elevation | > 0.7 for more than 3 consecutive sessions | Investigate context quality |
| Augur prediction accuracy | < 60% rolling 10-session average | Trigger model retraining |
| Behavioral diversity (Shannon entropy) | < 1.5 bits | Investigate pattern lock-in |
| Retention policy violations | Any chunk past retention deadline | Investigate cleanup job health |
| Deletion SLA violations | Any deletion request > 72 hours outstanding | Escalate immediately |
| Sidecar permission escalation | Any permission grant beyond matrix | Block deployment; security review |
| Gateway override attempts | Any attempt to bypass affect-action gate | Security incident |

---

## 12. Governance Invariant Summary

The following invariants are non-negotiable properties of the Atlas system. They are
enforced in code, verified by automated tests, and audited on the review cadence
defined in Section 11.2.

| # | Invariant | Enforcement |
|---|---|---|
| G-1 | No sidecar has DELETE permission on the chunks table | Database role grants; CI verification |
| G-2 | Affect-action separation: SSS state never authorizes tool execution | Gateway code; outside context window |
| G-3 | All stored data is user-inspectable | CLI and UI access paths; no hidden stores |
| G-4 | User deletion requests completed within 72 hours (hard delete) | Deletion SLA monitoring; alerting |
| G-5 | Predictions are non-authoritative (cache, not controller) | Augur architecture; no tool-trigger path |
| G-6 | Injection is biased toward silence (conjunctive gate) | 8-check AND gate; single veto sufficient |
| G-7 | CRITICAL-tier data encrypted with separate key | Key management architecture; audit |
| G-8 | Consent withdrawal is never penalized | Feature tier architecture; no degradation |
| G-9 | Audit logs are append-only and tamper-evident | Database permissions; integrity verification |
| G-10 | Safety degradation is always fail-closed (more restrictive) | Degradation mode definitions; testing |
| G-11 | Derivation never reduces data sensitivity tier | Classification rules; code review |
| G-12 | Transparency: system never claims feelings or consciousness | Prompt engineering; output filtering; review |

---

*This document is a companion to `00-atlas-overview.md` and should be read alongside
the sidecar contract specifications. It supersedes any governance statements in
earlier documents where conflicts exist.*
