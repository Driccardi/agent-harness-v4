# Kairos — Topic Consolidator

> *Greek: kairos (the opportune moment) — qualitative time, as opposed to chronos
> (quantitative time). In memory: the moment when raw fragments coalesce into
> structured understanding.*

---

## 1. Identity Card

| Field | Value |
|---|---|
| **Name** | Kairos |
| **Tier** | Reflective |
| **Role** | Semantic structure builder — organizing raw chunks into meaningful topic structures |
| **Trigger** | Every K turns (default 20), session end, compaction events |
| **Latency** | Unbounded (runs offline; the agent does not wait) |
| **Model** | Embedding model + generative LLM (13B+ recommended) |
| **Stateful** | Yes — maintains knowledge graph state across invocations |
| **Biological analog** | Cortical consolidation — slow extraction of semantic structure from hippocampal traces |

---

## 2. Purpose

Kairos is the slow-lane processor that builds semantic structure from raw fast-lane chunks. Where Engram captures everything without understanding, Kairos builds understanding without capturing. It clusters chunks, names topics, constructs the knowledge graph, maintains progressive summary stacks, manages the provisional chunk lifecycle, and signals downstream sidecars when topic corpora are ripe for deeper consolidation.

Without Kairos, the chunk store is a flat bag of embeddings — searchable by similarity but structurally opaque. With Kairos, it becomes a navigable knowledge graph with named topics, weighted relationships, and multi-resolution summaries that make retrieval faster, injection more precise, and the agent's accumulated knowledge legible to both humans and downstream sidecars.

---

## 3. Inputs

| Source | Data | Usage |
|---|---|---|
| `chunks` table | Recently embedded unclassified chunks (no `topic_ids`) | Primary clustering input |
| `chunks` table | Provisional chunks requiring lifecycle management | Validation/abandonment |
| `topic_nodes` | Existing graph nodes with centroids | Merge-vs-create decisions |
| `topic_edges` | Existing graph edges | Edge weight updates |
| `topic_summaries` | Current progressive summary stack per node | Delta updates |
| Hook signals | Compaction events from `pre_compact` hook | Priority trigger |
| Turn counter | Turns since last Kairos run | Primary trigger (every K turns) |

---

## 4. Processing Pipeline

Kairos processes in discrete batches. Each batch runs the following steps in order.

### 4.1 Chunk Collection

Gather all chunks lacking topic assignment since the last successful batch, plus all provisional chunks awaiting lifecycle evaluation. If zero unclassified chunks exist, skip to step 4.6 — there may still be provisional chunks requiring attention.

### 4.2 Clustering (HDBSCAN)

Cluster collected chunks using HDBSCAN with `min_cluster_size=3`, cosine metric, and Excess of Mass selection. HDBSCAN is preferred because it handles variable-density clusters, discovers the number of topics rather than requiring pre-specification, labels noise explicitly (rather than forcing chunks into ill-fitting clusters), and supports soft clustering for many-to-many topic membership.

Noise-labeled chunks are deferred to the next batch. Chunks remaining noise across 3 consecutive batches are force-assigned to the nearest cluster at confidence 0.4.

### 4.3 Topic Naming

For each new cluster, Kairos sends the 3–5 centroid-nearest chunks to a naming
model that produces:

- a **topic label** (maximum 5 words, noun phrase)
- **3–7 keywords**
- a **confidence score**
- an optional **duplicate-of** hint if the proposed label is too close to an
  existing topic label

The default naming path uses a **local fast instruct model**. This is the
preferred baseline because topic naming is frequent infrastructure work: it
benefits more from privacy, determinism, low cost, and operational reliability
than from frontier-level reasoning depth. The task is narrow — infer the shared
theme of a cluster and emit a short, stable label — which is well within the
capabilities of a good local model when the prompt is tightly constrained.

Kairos then validates the local result against simple acceptance rules:

- label must be a noun phrase of 5 words or fewer
- label must not be overly generic (`implementation_notes`, `project_work`,
  `misc`, etc.)
- label must not duplicate or near-duplicate an existing topic label
- keywords must add discrimination, not merely repeat the label
- confidence must meet the configured threshold

If the local model fails these checks, Kairos retries once locally with a more
constraining prompt. If the second attempt is still low-confidence, duplicate,
or too generic, Kairos may **escalate to a remote frontier model in fast mode**
for disambiguation.

Remote escalation is therefore an **exception path**, not the default. It is
reserved for clusters that are semantically muddy, cross-domain, unusually
important, or difficult to distinguish from existing nodes. This preserves the
quality benefits of frontier models without making routine topic naming depend
on external APIs, quota, or network availability.

Fallback on total failure: `unnamed_cluster_{timestamp}`.

### 4.4 Knowledge Graph Merge-or-Create

Compare each cluster centroid against existing node centroids. If similarity > 0.80, merge into the existing node (updating centroid via EMA: 0.7 existing / 0.3 new). Otherwise, create a new node. The threshold is deliberately high — false merges (collapsing distinct topics) are harder to undo than false splits (which can be merged later).

### 4.5 Edge Construction

Build or update edges between topic nodes using three signal types:

- **Co-occurrence:** Two topics share chunks from the same turn or session. Weight increments by 1.0 per co-occurring turn.
- **Temporal proximity:** Two topics appear within 20 turns of each other. Weight increments by 0.3.
- **Tangential:** A provisional chunk validated in one topic references content from another — the serendipitous cross-domain links that make memory useful beyond explicit lookup.

Edge types: `CO_OCCURRENCE`, `TEMPORAL`, `CAUSAL`, `TANGENTIAL`.

### 4.6 Progressive Summary Stack

For each modified topic node, update the four-depth summary stack:

| Depth | Content | Budget | Method |
|---|---|---|---|
| 3 | Keywords | ~20 tokens | Direct extraction (no LLM) |
| 2 | Brief summary | <50 words | LLM from centroid chunks |
| 1 | Full summary | <200 words | LLM from recent chunks (max 50) |
| 0 | Raw chunk IDs | N/A | Append pointers |

Summaries are incremental when <5 new chunks have been added; full regeneration otherwise. Summaries use present tense as standing knowledge, not past tense as events.

### 4.7 Provisional Chunk Lifecycle

This step runs even with no new unclassified chunks. It evaluates validation or abandonment of provisional chunks based on observed signals.

**Strong validation** (confidence -> 0.85, provisional -> FALSE):
- Tool call input semantically matches the provisional chunk (similarity > 0.85)
- Model's response text references the provisional chunk's content
- Model explicitly builds on the provisional idea

**Weak validation** (confidence -> 0.65, remains provisional; 3 weak signals = promotion):
- Subsequent turns stay in the provisional chunk's topic domain
- Short time to next action (suggests confident convergence)

**Abandonment** (confidence -> 0.1, excluded from retrieval):
- Contradicting tool call or correction issued
- Reasoning thread pivots to a different approach
- K turns (default 5) pass with no validation signal

Abandoned chunks are never deleted — they are retained at depth 0 as audit trail. Abandoned chunks containing genuine negative knowledge (a constraint that ruled out an approach) are detected by the LLM and promoted as validated constraint knowledge at confidence 0.75, reframed as "approach X does not work because of constraint Y."

### 4.8 Deferred Chunk Assignment

Chunks stored without topic assignment from previous batches are revisited using
the updated graph. Deferred assignment is a normal part of Kairos's operation,
not an error state: chunks remain semantically searchable by embedding even when
they do not yet belong to any topic node.

Deferred chunks are processed with the following policy:

- If similarity to any node centroid exceeds `0.75`, assign the chunk to that
  node normally.
- If a chunk remains unassigned across 3 consecutive batches but has a plausible
  nearest node, Kairos may **force-assign** it at low confidence (`0.40`).
  This is a pragmatic fallback for weakly classifiable but still topically
  useful chunks.
- If no node exceeds the **orphan floor** (`0.50`) after 3 consecutive batches,
  mark the chunk as an **orphan** rather than forcing assignment.

This distinction is important:

- **Deferred** means "not yet classified, still awaiting assignment."
- **Orphan** means "repeatedly unassigned, but still valid and searchable."
- **Abandoned** remains reserved for invalidated provisional reasoning chunks.
- **Archived** remains a downstream retention decision owned by Oneiros.

Orphaned chunks are not deleted, not decayed, and not treated as failures. They
remain in the chunk store with `topic_ids = []`, excluded from topic-graph
statistics but still available for direct semantic retrieval. They are also
eligible for future reassignment if:

- a new topic node is created that better matches them,
- graph structure shifts enough to raise similarity above threshold, or
- multiple similar orphaned chunks accumulate and justify formation of a new
  topic node in a later consolidation pass.

The governing principle is conservative: **false topical assignment is worse
than temporary isolation**. A lonely but valid chunk is preferable to polluting
an existing topic with a weak semantic fit.

### 4.9 Oneiros Trigger

Evaluate each modified topic node. If chunk count exceeds the corpus threshold (default 100), enqueue an Oneiros trigger signal. This is the handoff from Kairos (topic structure) to Oneiros (lossy generalization).

---

## 5. Topic Routing Strategy (Layered Classification)

A cascade of increasingly expensive classifiers, used in priority order:

| Layer | Method | Cost | Coverage |
|---|---|---|---|
| 1 | Structural heuristics (file paths -> topics) | Free, instant | ~60% of tool events |
| 2 | Embedding similarity against graph node centroids | One vector comparison, <5ms | Most recurring topics |
| 3 | LLM classification for novel content | One LLM call, <500ms local | Novel content only |
| 4 | Deferred assignment (stored unclassified, assigned next batch) | Zero | Remainder |

Chunks are searchable by embedding similarity even without topic assignment. Deferred classification is acceptable — the slow lane handles everything the fast lane skipped.

---

## 6. Outputs

| Target | Operation | Content |
|---|---|---|
| `topic_nodes` | UPSERT | New/updated nodes with labels, keywords, centroids |
| `topic_edges` | UPSERT | New/updated edges with types and weights |
| `chunk_topics` | INSERT | Many-to-many chunk-to-node assignments |
| `topic_summaries` | UPSERT | Progressive summary stack at depths 0-3 |
| `chunks` | UPDATE | `topic_ids`, `validated`, `confidence` (lifecycle fields only) |
| Oneiros trigger queue | ENQUEUE | Topic node IDs exceeding corpus threshold |

---

## 7. Data Contracts

**Reads:** `chunks` (unclassified + provisional), `topic_nodes`, `topic_edges`, `topic_summaries`.

**Writes:** `topic_nodes`, `topic_edges`, `chunk_topics`, `topic_summaries` (sole writer). `chunks` (UPDATE only: `topic_ids`, `validated`, `confidence`).

**Column ownership on `chunks`:** `topic_ids` (sole writer), `validated` (shared with Eidos), `confidence` (shared — Engram sets initial, Kairos updates). All other chunk columns are read-only for Kairos.

**Downstream signals:** Oneiros trigger queue (topic corpus size). Anamnesis benefits indirectly from topic assignments and summaries improving retrieval quality.

---

## 8. Operational Semantics

**Batch boundaries** do not align with turn or session boundaries. A batch is "all unclassified chunks since the last successful batch, plus provisional chunks requiring lifecycle evaluation."

**Idempotency.** All writes are idempotent. UPSERT semantics on topic tables; ON CONFLICT DO NOTHING on chunk_topics. Mid-batch crash recovery: next batch reprocesses the same chunks with identical results.

**Concurrency.** Single instance per master session, enforced via PostgreSQL advisory lock on `hashtext(master_session_id::text)`. If lock is not acquired, the invocation exits cleanly.

**Failure recovery:**

| Failure | Recovery |
|---|---|
| Crash mid-clustering | Next batch reprocesses all unclassified chunks |
| LLM unavailable | Fallback label: `unnamed_cluster_{timestamp}` |
| Database write failure | Exponential backoff, 3 attempts, then skip batch |
| All-noise clustering | Lower min_cluster_size by 1, retry once; if still noise, defer batch |

---

## 9. Evaluation Metrics

| Metric | Target |
|---|---|
| Topic assignment coverage | >85% of chunks assigned within 2 batches |
| Topic label quality | Human-judged relevance >80% |
| Summary accuracy | Key facts preserved across depth levels |
| Provisional lifecycle accuracy | >90% correct validation/abandonment |
| Merge precision | <5% false merges |
| Edge coherence | >75% of edges judged meaningful |
| Batch completion time | <120s for batches of <500 chunks |
| KG query latency | <20ms for chunk + topic join queries |

---

## 10. Configuration

```yaml
kairos:
  enabled: true
  consolidation_interval_turns: 20
  trigger_on_session_end: true
  trigger_on_compaction: true
  clustering_method: hdbscan
  min_cluster_size: 3
  min_samples: 1
  noise_retry_threshold: 3
  topic_merge_threshold: 0.80
  centroid_weight_existing: 0.7
  centroid_weight_new: 0.3
  deferred_assignment_threshold: 0.75
  orphan_similarity_floor: 0.5
  max_topic_label_words: 5
  centroid_sample_size: 5
  summary_depths: [0, 1, 2, 3]
  summary_incremental_threshold: 5
  summary_max_source_chunks: 50
  provisional_timeout_turns: 5
  strong_validation_confidence: 0.85
  weak_validation_confidence: 0.65
  weak_signals_to_promote: 3
  abandonment_confidence: 0.1
  negative_knowledge_confidence: 0.75
  oneiros_corpus_threshold: 100
  batch_retry_attempts: 3
  advisory_lock: true
```

---

## 11. Sidecar Interactions

**Upstream:** Engram (produces raw chunks), Eidos (enriches chunks with somatic tags before Kairos processes them).

**Downstream:** Anamnesis (reads topic assignments and summaries for retrieval precision), Oneiros (receives trigger signals, reads organized topic corpus for lossy generalization), Psyche (reads graph topology for self-narrative), Augur (reads topic activity patterns for intent prediction).

**Kairos-Oneiros boundary:** Kairos organizes and summarizes (lossless — all source chunks preserved). Oneiros generalizes and prunes (lossy — episodic scaffolding discarded). After Oneiros consolidates a topic, the archived episodic chunks are no longer Kairos's concern.

---

## 12. Design Rationale

**Why batch, not streaming.** Clustering requires N chunks to identify structure. Batch processing produces stable topic assignments; per-chunk processing causes thrashing.

**Why HDBSCAN.** Handles variable-density clusters, noise, and unknown cluster count. K-means requires pre-specifying k. DBSCAN requires a fixed epsilon. Agglomerative clustering lacks soft-clustering probabilities.

**Why the merge threshold is high (0.80).** False merges collapse distinct topics into confused centroids and misleading summaries. False splits are naturally correctable in subsequent batches or by human review.

**Why provisional lifecycle lives in Kairos.** Provisional validation runs at the same cadence as topic assignment. Validated chunks need immediate topic assignment. Negative-knowledge reframing requires topic context. A separate sidecar adds coordination overhead for no benefit.

---

## 13. Implementation Notes

**Phase 3 deliverables:** `topic_consolidator.py` (orchestrator), `knowledge_graph.py` (PostgreSQL-backed KG ops), `clustering.py` (HDBSCAN wrapper), `summarizer.py` (summary stack builder), `provisional.py` (lifecycle engine), `topic_router.py` (layered classification).

**Hardware at 8GB VRAM:** Run embedding on CPU to free VRAM for generative model. **At 16GB:** Both models fit; Kairos gets generative model exclusively during consolidation windows. Recommended: `deepseek-r1-14b` or `qwen2.5-14b-instruct` for provisional lifecycle reasoning.

**Success criteria:** Topic graph coherent after 5 sessions. Progressive summaries correctly abstracted. Provisional promotion/decay working. Cross-session topic continuity detectable. KG join queries <20ms.
