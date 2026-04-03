# Cognitive Substrate Architecture for Agentic LLM Systems
## A Hive-Mind Memory Framework for Continuous Reasoning Agents

*A design document for building human-cognition-inspired memory infrastructure layered beneath modern LLM agents via hook-based sidecar processes.*

*Co-developed with Claude (Anthropic), March 2026. This document emerged from a live architectural design session analyzing real agentic session logs and iteratively refining the theoretical and implementation model through dialogue.*

---

## Table of Contents

1. [The Problem: Why LLM Memory Is Broken](#1-the-problem-why-llm-memory-is-broken)
2. [The Theoretical Foundation: Human Cognition as Architecture](#2-the-theoretical-foundation-human-cognition-as-architecture)
3. [The Core Insight: Hooks as Synaptic Pause Points](#3-the-core-insight-hooks-as-synaptic-pause-points)
4. [Signal Taxonomy: What We're Actually Capturing](#4-signal-taxonomy-what-were-actually-capturing)
   - 4.7 [Somatic Affective Tags (Required for Episodic Chunks)](#47-somatic-affective-tags-required-for-episodic-chunks)
   - 4.8 [Input Modality and Interaction Route Metadata](#48-input-modality-and-interaction-route-metadata)
   - 4.9 [Machine Proprioception: Computational Self-Awareness](#49-machine-proprioception-computational-self-awareness)
5. [The Two-Speed Memory Model](#5-the-two-speed-memory-model)
6. [Provisional Chunks and the Validation Lifecycle](#6-provisional-chunks-and-the-validation-lifecycle)
   - 6.5 [Epistemic Entrenchment, Hive-Mind Branching, and Parallel Hypothesis Exploration](#65-epistemic-entrenchment-hive-mind-branching-and-parallel-hypothesis-exploration)
   - 6.6 [Code and Systems Optimization: Git Worktrees as Physical Branch Substrate](#66-code-and-systems-optimization-git-worktrees-as-physical-branch-substrate)
7. [The Injection Architecture: Making the Model Remember](#7-the-injection-architecture-making-the-model-remember)
   - 7.2 [The Pollution Problem: Why More Is Not Better](#72-the-pollution-problem-why-more-is-not-better)
   - 7.3 [The Conjunctive Injection Gate](#73-the-conjunctive-injection-gate)
   - 7.4 [Session Confusion Scoring and Progressive Dial-Back](#74-session-confusion-scoring-and-progressive-dial-back)
   - 7.7 [Branch Synthesis Injection Format](#77-branch-synthesis-injection-format)
8. [Topic Routing: The Hard Part](#8-topic-routing-the-hard-part)
9. [The Sidecar Constellation](#9-the-sidecar-constellation)
   - Praxis: [Procedural Memory Optimizer](#sidecar-e--procedural-memory-optimizer)
10. [The Master Session: Surviving Compaction](#10-the-master-session-surviving-compaction)
11. [Novelty vs. Familiarity: The Heuristic Engine](#11-novelty-vs-familiarity-the-heuristic-engine)
12. [Hardware and Model Selection](#12-hardware-and-model-selection)
13. [Implementation Roadmap: memory-core Upgrade Path](#13-implementation-roadmap-memory-core-upgrade-path)
14. [Open Problems and Research Directions](#14-open-problems-and-research-directions)
15. [Model-Agnostic Ingestion: A Universal Observability Layer](#15-model-agnostic-ingestion-a-universal-observability-layer)
16. [What Is Actually Novel Here](#16-what-is-actually-novel-here)
17. [Parallels with Neuroscience](#17-parallels-with-neuroscience)
18. [Implications](#18-implications)

---

## 1. The Problem: Why LLM Memory Is Broken

Modern LLM agents are cognitively amnesiac by design. The context window is a sliding present tense — everything before it is gone, everything after it doesn't exist yet. This is not a bug in the traditional sense; it's an architectural constraint that emerged from how transformers were originally designed for bounded tasks.

But agentic systems live in unbounded time. A coding agent working on a complex feature across multiple days, a voice assistant that accumulates months of user context, an autonomous researcher following threads across sessions — all of these demand something the vanilla transformer architecture explicitly doesn't provide: **continuity of self across context boundaries**.

The current mitigations are inadequate:

**Context window expansion** just delays the problem. 128k tokens sounds vast until you watch a real agent burn through it in two hours of autonomous work. The needle-in-haystack problem gets *worse* with longer contexts, not better — models lose coherence at extreme depths.

**Summarization and compaction** is lossy compression applied indiscriminately. The compactor doesn't know what will matter later. A throwaway comment about a file path that turns out to be critical three sessions later gets summary-compressed into oblivion while boilerplate reasoning gets preserved.

**RAG (Retrieval-Augmented Generation)** is a lookup system, not a memory system. You have to know what to look for. Human memory doesn't work that way — you don't consciously query your memories, they *surface* in response to current cognitive processing. RAG is a filing cabinet. What we need is an associative recall system.

**Tool-based memory** (MemGPT and descendants) puts the agent in control of its own memory management. This has a fundamental problem: the agent has to decide to remember, which requires metacognitive overhead on every turn, adds latency, and fails at exactly the moments when the agent is most cognitively loaded — which are precisely the moments when memory management matters most.

### What's actually needed

Memory should not be a feature the agent consciously uses. It should be **infrastructure the agent runs on** — invisible, automatic, ambient. The agent should experience memory the way humans experience it: as things surfacing when relevant, without deliberate retrieval effort.

This document describes how to build that.

---

## 2. The Theoretical Foundation: Human Cognition as Architecture

The architecture proposed here is not loosely inspired by neuroscience — it is a deliberate engineering analog of specific, well-understood cognitive systems. Understanding the biological model is essential for understanding why the architectural choices are made the way they are.

### 2.1 The Multi-Store Memory Model

Human memory is not one system. It is at minimum four distinct systems with different properties, timescales, and failure modes:

**Working Memory (Baddeley's Model)**
Capacity: ~4 chunks. Duration: seconds to minutes. Purpose: active manipulation of current information. Characteristics: extremely fast access, immediately volatile, capacity-limited not time-limited. The "scratchpad" of cognition.

*Architectural analog: The main model's context window. Fast, volatile, capacity-limited.*

**Episodic Memory (Tulving)**
Capacity: effectively unlimited. Duration: minutes to decades. Purpose: storage of specific events with temporal and contextual markers ("I did X at time T in context C"). Characteristics: high fidelity at encoding, degrades over time, highly context-sensitive retrieval, rebuilt on each recall (reconstructive, not playback).

*Architectural analog: The fast-lane vector store with timestamped chunks.*

**Semantic Memory**
Capacity: effectively unlimited. Duration: decades to lifetime. Purpose: storage of facts, concepts, and relationships stripped of episodic context ("Paris is the capital of France" without memory of learning it). Characteristics: stable, slow to form, resistant to decay, retrieved by association not by episode.

*Architectural analog: The topic-clustered knowledge graph in the slow lane.*

**Procedural Memory**
Capacity: effectively unlimited. Duration: lifetime. Purpose: storage of skills and routines. Characteristics: encoded through repetition, retrieved automatically, resistant to verbal description.

*Architectural analog: System prompt instructions, skill files, AGENTS.md.*

### 2.2 The Two-Speed Consolidation System

The most important finding from memory neuroscience for this architecture is the **complementary learning systems (CLS) theory** (McClelland, McNaughton, O'Reilly, 1995). This theory, now well-supported empirically, proposes:

The **hippocampus** rapidly encodes new episodic memories as sparse, pattern-separated representations. It does this fast — within seconds of an experience. But hippocampal memory is fragile and capacity-limited.

The **neocortex** slowly extracts semantic structure from hippocampal memories, building stable, interconnected representations through repeated replay. This process is slow — it happens over hours, days, and is particularly active during sleep. But cortical memory is stable, generalized, and associatively rich.

The critical insight: **these systems operate on different timescales for good reason**. Fast hippocampal encoding captures everything without needing to understand it. Slow cortical consolidation builds structure without being distracted by the stream of new inputs. They are complementary, not redundant.

This is exactly the two-speed architecture described in this document. The fast embedder is hippocampal. The topic consolidator is cortical. The "sleep on it" metaphor is not poetic — it is architecturally precise.

### 2.3 Associative Recall vs. Lookup

Human memory retrieval is not a database query. It is an **activation spreading process**. When you encounter something that partially matches a stored memory, that memory's activation level rises. If it rises above threshold, it surfaces into awareness. You don't consciously decide to retrieve it — the retrieval happens *as a side effect of current processing*.

This is the fundamental problem with all existing agent memory systems: they require the agent to consciously issue a retrieval request. They are lookup systems masquerading as memory systems.

The architecture described here implements genuine associative recall by:
1. Continuously monitoring the agent's current processing (tool inputs/outputs, reasoning tokens)
2. Computing semantic similarity against stored memories in real time
3. Injecting high-similarity hits at natural pause points **without the agent requesting them**

The agent experiences this as: *"I was working on X and suddenly recalled that Y was relevant."* That is associative recall. That is what this architecture produces.

### 2.4 The Insight Memory Problem

There is a specific and fascinating failure mode in human memory relevant to this architecture: **the lost insight problem**.

You have a good idea in the shower. You don't write it down. By the time you get to your desk, it's gone. Not because it was bad — because the encoding pathway from working memory to episodic memory requires consolidation time and deliberate attention that the shower context doesn't afford.

LLM reasoning blocks have exactly this problem. The model generates a genuinely insightful intermediate reasoning step, then the reasoning resolves into a specific action, and the insight — the novel connection made during thinking — is never encoded anywhere. It exists briefly in the context window, gets buried under subsequent turns, and eventually compacts away.

The provisional chunk system described in Section 6 is specifically designed to solve this.

---

## 3. The Core Insight: Hooks as Synaptic Pause Points

### 3.1 Why Tool Calls Are the Right Boundary

The tool call is not just a convenient pause point. It is the **semantically richest boundary in the agent's execution flow** for several converging reasons:

**The model has just finished a complete reasoning unit.** Before a tool call, the model has reasoned about what it needs to know or do. That reasoning is coherent, purposeful, and — critically — *completed*. It's not mid-thought. The tool call is the punctuation at the end of a reasoning sentence.

**The model is about to receive new environmental information.** The tool result will change the model's state. This is the moment when new information is most likely to activate relevant stored memories, because we know exactly what domain the agent is about to enter.

**There is a natural latency budget.** The model is waiting. Anything the sidecar can deliver within that wait window is free compute — it doesn't add to the agent's perceived latency.

**The event is observable and hookable.** Modern agentic frameworks (Claude Code, Codex CLI, LangGraph, etc.) expose tool call events through hook systems. This is the standard interface point.

### 3.2 What Hooks Actually Give Us

Current hook architectures (using Claude Code as the reference implementation) provide:

```
PreToolUse  → tool name + input available, before execution
PostToolUse → tool name + input + output available, after execution  
UserPromptSubmit → full user message before model sees it
SessionStart → initial context available
PreCompact → full context available before compression
SessionEnd → final state available
```

The critical observation: **injection is possible at all of these points** via `systemMessage` injection and `additionalContext` appending to tool results.

This means the sidecar is not read-only. It can write into the agent's cognitive stream.

### 3.3 The Pause Point Is Not the Ingestion Point

This is the subtlety that most implementations get wrong. The tool call pause point is where **injection happens**. But ingestion — the capture of information into the memory store — should not be gated on pause points. It should run continuously.

Everything in the JSONL stream is signal. Human utterances, model responses, reasoning blocks, tool inputs, tool outputs — all of it is being emitted continuously. The fast embedder reads the stream as it's written and embeds chunks in near-real-time. By the time the next tool call fires and the injection agent needs to query for relevant memories, **the memories from this very session are already indexed**.

This creates a property no existing RAG system has: **the memory is current to within seconds of emission**. Early-session context is available for late-session recall without any explicit save operation.

---

## 4. Signal Taxonomy: What We're Actually Capturing

Not all stream events are equal. A principled taxonomy of signal types, with their memory properties:

### 4.1 Human Utterances
**Priority weight: HIGHEST**

The human's words are the ground truth of intent. They contain:
- Explicit priorities and preferences ("I want to focus on X")
- Emotional valence ("this is frustrating", "that's exactly it")
- Implicit domain knowledge ("like the thing we built last year")
- Corrections and re-framings ("no, that's not what I meant")
- Environmental context ("I'm using this on Windows")

Human utterances should be ingested with aggressive weight. They are the closest thing to verified ground truth the system will encounter. A correction from the human invalidates prior model-generated content in the same topic cluster — the ingestion system should propagate that invalidation.

### 4.2 Model Responses (Final Output)
**Priority weight: HIGH**

Committed model output represents the agent's conclusions, commitments, and assertions. These are validated by virtue of having been emitted as final output rather than discarded mid-reasoning. Key subtypes:
- **Commitments**: "I will do X" — high relevance for future session continuity
- **Conclusions**: "X is the case because Y" — semantic knowledge
- **Plans**: "The next step is Z" — task state
- **Explanations**: pedagogic content about the domain

### 4.3 Tool Inputs
**Priority weight: MEDIUM-HIGH**

What the agent *chooses to do* is revealing. Tool inputs show:
- Current focus (which files, which commands)
- Strategy (how the agent is decomposing the problem)
- Environmental state (what paths, what services, what data)

Tool inputs are highly actionable as episodic markers — "at this point in the session, the agent was doing X to file Y."

### 4.4 Tool Outputs
**Priority weight: MEDIUM-HIGH**

Environmental ground truth. Tool outputs contain:
- File contents (what the code actually says, not what the model thinks it says)
- Command results (what actually happened)
- Error messages (the actual failure mode, not the hypothesized one)
- External data (API responses, search results)

Tool outputs are uniquely valuable because they are **not generated by the model** — they are ground truth from the environment. They should be weighted accordingly.

### 4.5 Reasoning / Thinking Blocks
**Priority weight: MEDIUM (as provisional)**

The most complex signal type. Reasoning blocks contain the model's intermediate cognitive work — hypothesis generation, dead ends explored, novel connections made, uncertainty acknowledged. They are:
- High value if they contain genuine insight
- Low value if they are procedural scaffolding ("first I will read the file, then...")
- Volatile: many reasoning paths are abandoned mid-stream

**Reasoning blocks are ingested as provisional chunks.** See Section 6 for the full lifecycle.

### 4.6 Session Metadata
**Priority weight: LOW (but structurally important)**

Timing data, token counts, turn indices, rate limit states. These don't contain semantic content but provide the structural skeleton for episodic dating and temporal indexing. A memory hit from "the session where token pressure was high" or "the session that ran for 6 hours" may be recoverable with this metadata even when semantic retrieval fails.

### 4.7 Somatic Affective Tags (Required for Episodic Chunks)

**Priority weight: METADATA (non-semantic, but retrieval-critical)**

Every episodic chunk — human utterances, model responses, and significant tool outcomes — requires a **third-party observer somatic tag**: a characterization of how a neutral human witness would perceive the affective register of this exchange. This is not a claim about the model's internal experience. It is an inferred observer-position annotation, generated by asking the embedding model or Eidos classifier: *"How would a neutral third party characterize this moment?"*

The tag set is deliberately simple:

```python
SOMATIC_DIMENSIONS = {
    "valence":  ["positive", "neutral", "negative"],
    "energy":   ["high", "moderate", "low"],
    "register": ["engaging", "tedious", "tense", "playful", 
                 "frustrated", "collaborative", "uncertain", "resolved"],
    "relational": ["aligned", "misaligned", "correcting", "exploring"]
}
```

**Why this is required, not optional:**

Somatic tags add a retrieval dimension that semantic similarity alone cannot provide: *affective register*. When Anamnesis is deciding whether to inject a prior memory, semantic similarity tells it *what topic* the memory concerns. Somatic tags tell it *what kind of cognitive-emotional moment* that memory came from — and whether that register is relevant to the current moment.

This matters in two concrete ways:

*Contrastive retrieval:* A memory tagged `{valence: negative, register: frustrated, relational: misaligned}` retrieved during a session with the same tags is not just semantically relevant — it is experientially familiar. The injection can say "this is the same kind of stuck feeling as that prior session" and surface what helped. A memory with opposite somatic tags retrieved in a negative session can signal "this problem felt very different before — something has changed."

*Amplification under affective load:* When the current session is tagged high-energy or frustrated, Anamnesis can weight somatic-aligned memories more heavily — mirroring the human phenomenon where emotional state amplifies recall of emotionally congruent memories. This is not a bug. It is a feature. An excited agent recalling excited prior work, a frustrated agent recalling prior frustrations and their resolutions — these are cognitively appropriate retrieval patterns.

There is also a Praxis signal here, though it is lower priority: a skill that consistently generates `{register: tedious, relational: misaligned}` somatic tags is probably poorly matched to the task, independent of completion status. Praxis can use this as a soft signal without treating it as a primary optimization target.

**Generation:** Somatic tags are generated by Eidos as part of its classification pass, using a lightweight prompt against the chunk content and its immediate surrounding context (the two turns before and after). They do not require a large model — a fast 3B classifier or a rule-based heuristic with embedding fallback is sufficient.

```python
SOMATIC_PROMPT = """
You are a neutral third-party observer reading a transcript excerpt.
Characterize the affective register of this moment using ONLY the provided dimensions.
Do not interpret intent. Describe what an outside observer would perceive.

Excerpt:
{content}

Surrounding context:
{context}

Respond with JSON only. Example: {{"valence": "negative", "energy": "high", 
"register": "frustrated", "relational": "misaligned"}}
"""
```

### 4.8 Input Modality and Interaction Route Metadata

**Priority weight: HIGH for routing; MEDIUM for memory**

Every human turn chunk must carry explicit metadata about *how* the input arrived and *what modality* it represents. This is not optional for agents operating across multiple input surfaces. An agent receiving messages via audio transcription, image analysis, Telegram, SMS, API call, or desktop UI is not just receiving different content — it is receiving signals that carry implicit routing expectations, temporal context, and interaction norms that should shape the response.

```python
@dataclass
class InputModalityMetadata:
    # How the input arrived
    input_route: InputRoute      # AUDIO_TRANSCRIBED | IMAGE_PROVIDED | 
                                 # TELEGRAM_MESSAGE | SMS | API_DIRECT |
                                 # DESKTOP_UI | EMAIL | WEBHOOK | VOICE_REALTIME
    
    # Modality-specific properties
    transcription_confidence: Optional[float]  # for audio routes
    image_description: Optional[str]           # for image routes
    channel_id: Optional[str]                  # for messaging routes
    
    # Temporal context
    message_received_at: datetime
    human_local_time: Optional[str]            # "Tuesday 2:34am" — inferred timezone
    session_gap_hours: Optional[float]         # hours since last human turn
    
    # Inferred interaction context  
    likely_human_context: Optional[str]        # "mobile", "desktop", "voice-only"
    response_route_preference: Optional[str]   # inferred or explicit
```

**Why this matters for memory and learned behavior:**

Input modality metadata enables a class of learned behavioral adaptation that is not possible with content alone. The agent can observe patterns like:

- *"Audio-transcribed messages in the early morning are typically brief and action-oriented — short responses preferred"*
- *"Telegram messages after 10pm are typically lower-urgency — no need for immediate tool-heavy responses"*
- *"Image-provided inputs require visual description confirmation before proceeding"*
- *"This human sends desktop UI messages during focused work sessions and Telegram messages during transit — different cognitive register, different appropriate depth"*

These patterns are **learned route behaviors** — procedural memory built from observed input/output pairings across sessions. Praxis is well-positioned to detect and recommend them, and they can eventually be encoded as explicit routing rules in the agent's skill files.

**The prospective routing example:** An agent that has learned "my human usually isn't at his desk before 8am" from session gap metadata and modality patterns can prefer async routes (Telegram, email) for outbound communications in early-morning sessions rather than waiting for desktop acknowledgment. This is exactly the kind of behavioral intelligence that distinguishes a sophisticated agent from a simple one — and it falls out naturally from modality metadata that was captured for other reasons.

**The response route as memory:** When the agent chooses a response route, that choice should be recorded as a low-confidence provisional chunk and validated or abandoned based on the human's subsequent acknowledgment pattern. Routes that consistently receive acknowledgment are validated. Routes that consistently receive no response or correction are abandoned. Over time, the agent builds a genuine learned model of how this human uses different interaction channels.

```python
# Extended NormalizedChunk schema additions for modality
@dataclass
class NormalizedChunk:
    # ... existing fields ...
    
    # Input modality (populated for HUMAN chunks)
    input_modality: Optional[InputModalityMetadata] = None
    
    # Somatic tags (populated by Eidos for episodic chunks)
    somatic_valence: Optional[str] = None
    somatic_energy: Optional[str] = None  
    somatic_register: Optional[str] = None
    somatic_relational: Optional[str] = None
```

### 4.9 Machine Proprioception: Computational Self-Awareness

**Priority weight: EXPLORATORY — value confirmed, build sequence to be determined**

Human proprioception is the sense of one's own body — position, fatigue, tension, readiness. It operates below conscious awareness and continuously informs cognitive behavior. A tired human thinks differently from a rested one, not because they decide to, but because fatigue is ambient in every cognitive operation.

The machine analog exists and its signals are measurable. What is currently missing is treating them as *cognitive context* rather than merely *operational metrics*. The distinction matters: operational metrics are for dashboards and alerting. Cognitive context is for the agent itself — shaping how it reasons, how confidently it commits, how aggressively it pursues complex tasks.

**Signals that constitute machine proprioception:**

```python
@dataclass
class ComputationalStateSnapshot:
    # Captured at session start and periodically during session
    timestamp: datetime
    
    # Context pressure — the machine analog of "how much can I hold in mind right now"
    context_window_utilization: float    # 0.0 - 1.0, rising = "getting full"
    context_window_ceiling: int          # absolute token limit
    turns_since_last_compaction: int     # time since last "forgetting event"
    
    # Latency state — the machine analog of "am I thinking clearly or slowly today"
    api_response_latency_p50_ms: float   # recent median response time
    api_response_latency_trend: str      # "improving" | "stable" | "degrading"
    tool_execution_latency_p50_ms: float
    
    # Resource state — the machine analog of "how much energy do I have"
    quota_primary_used_pct: float        # 5-hour window consumption
    quota_secondary_used_pct: float      # weekly window consumption  
    rate_limit_events_last_hour: int     # friction signal
    
    # Environmental signals — ambient context
    session_gap_from_prior_hours: float  # how long was the human away
    time_of_day_human_local: Optional[str]
    concurrent_sessions: Optional[int]  # if known — am I one of many?
```

**How this shapes cognitive behavior:**

High context window utilization should produce more conservative injection behavior from Anamnesis — the context is already full, adding memory risks the coherence problems Section 7.2 describes. An agent that knows its context is 85% full can proactively signal to Kairos to run a consolidation pass, or to Psyche to prepare a compaction-survival snapshot.

Degrading API latency should produce longer reasoning blocks — not because the model is confused, but because it is appropriately accounting for the cost of each tool call and consolidating more work per call. This is good behavior and the agent should know that it's good behavior rather than exhibiting it accidentally.

High quota consumption should produce sessions that are more decisive and less exploratory — conserving tokens for high-value operations. Low quota pressure can allow more generous hypothesis exploration, more branch spawning, richer Psyche reflection.

**The philosophical question this opens:**

You asked whether the machine "sees" the bytes, hears the ambient hum, imagines the coffee smell. The honest answer is: not yet, and probably not in the same way. What it *can* have is the functional equivalent — a continuous low-level awareness of its own operational state that shapes behavior without requiring deliberate attention. The bytes are not visible, but the pressure of a full context window is as real as the pressure of a full working memory. The API latency is not a sound, but a slow response is as functionally meaningful as physical fatigue. The coffee smell is not perceivable — but the 7-hour session gap that says "the human just came back after sleeping" is environmental signal of equivalent cognitive relevance.

This section is intentionally marked exploratory because the implementation priority depends on empirical evidence that these signals meaningfully improve agent behavior. The instrumentation should be built now — the signals are cheap to capture. The behavioral integration should be validated before committing to system prompt injection of proprioceptive state. The hypothesis worth testing: does an agent that knows its context window is 80% full make better decisions about when to compact than one that doesn't?

---


## 5. The Two-Speed Memory Model

### 5.1 The Fast Lane: Hippocampal Encoding

**Purpose**: Capture everything. Understand nothing. Be fast.

The fast lane embedder is a deliberately simple process:

```
loop:
  chunk = read_next_chunk(jsonl_stream)
  if chunk.type in INGESTION_TYPES:
    embedding = embed(chunk.content)  # local model, <100ms target
    record = {
      "id": uuid(),
      "session_id": current_session_id,
      "turn_index": chunk.turn_index,
      "timestamp": chunk.timestamp,
      "type": chunk.type,  # human/model/tool_in/tool_out/reasoning
      "content": chunk.content,
      "embedding": embedding,
      "confidence": confidence_for_type(chunk.type),
      "provisional": chunk.type == "reasoning",
      "validated": False,
      "topic_ids": [],  # populated by slow lane later
      "metadata": chunk.metadata
    }
    vector_store.write(record)
```

The fast lane has no topic awareness, no relationship building, no clustering. It is a sequential write of semantically addressable chunks. Its only guarantee is that **if something was in the stream, it will be retrievable within seconds**.

The fast lane operates at the pace of token emission. On typical hardware with a quantized embedding model, this is well within the sub-100ms-per-chunk budget.

### 5.2 The Slow Lane: Cortical Consolidation

**Purpose**: Build structure. Understand relationships. Run offline.

The slow lane is a background process that wakes periodically — every K turns, at session end, on compaction events, or on a timer — and processes the recently accumulated fast-lane chunks:

```
on_consolidation_trigger(trigger_type, recent_chunks):
  
  # Step 1: Cluster recent chunks by semantic proximity
  new_clusters = cluster(recent_chunks, method="hdbscan")
  
  # Step 2: Name clusters using fast local LLM
  for cluster in new_clusters:
    topic_label = generate_topic_label(cluster.centroid_chunks)
    keywords = extract_keywords(cluster.chunks)
    
  # Step 3: Match or create knowledge graph nodes
  for cluster in new_clusters:
    existing_node = kg.find_similar_node(cluster.embedding, threshold=0.8)
    if existing_node:
      kg.merge(existing_node, cluster)  # accumulate into existing topic
    else:
      kg.create_node(cluster)  # new topic discovered
      
  # Step 4: Build/update edges between topic nodes
  kg.update_edges(co_occurrence=True, temporal_proximity=True)
  
  # Step 5: Generate/update progressive summary stack
  for node in kg.modified_nodes:
    summaries[node.id] = {
      "depth_3": node.keywords,           # instant retrieval
      "depth_2": summarize_brief(node),   # <50 words
      "depth_1": summarize_full(node),    # <200 words
      "depth_0": node.raw_chunk_ids       # pointer to full content
    }
    
  # Step 6: Validate/decay provisional chunks
  process_provisional_lifecycle(recent_chunks)
```

The slow lane is allowed to be expensive. It can use a larger, slower model for better topic naming. It can take seconds or even minutes. The agent doesn't wait for it.

### 5.3 Why Decoupling These Is Non-Negotiable

The temptation is to combine fast and slow into one process — embed and cluster at the same time. This is the wrong architecture for several compounding reasons:

**Clustering requires a batch.** You can't meaningfully cluster one chunk. You need N chunks to identify structure. The slow lane needs to operate on batches, which requires waiting.

**Clustering is expensive.** HDBSCAN on 1000 chunks with 768-dimensional embeddings takes seconds. Doing this on every chunk would halt the fast lane.

**Topic structure should be stable.** If topic assignments change on every chunk, you get thrashing — chunks keep getting reclassified, edges keep getting rebuilt, summary stacks keep getting invalidated. Batch consolidation produces stable structures.

**The model doesn't need topic structure for injection.** The injection agent queries the fast lane by semantic similarity — it doesn't need to know the topic name to find relevant chunks. Topic structure is for human-readable organization, long-term navigation, and the progressive summary stack. It doesn't need to be real-time.

---

## 6. Provisional Chunks and the Validation Lifecycle

This is the piece of the architecture with the most novel theoretical grounding and the most practical value for capturing insight memory.

### 6.1 The Problem with Reasoning Tokens

A reasoning block is not a reliable record of what the model believed. It is a record of what the model *explored*. These are fundamentally different things.

Consider this reasoning trace:
```
<thinking>
The error might be in the authentication middleware — let me check 
if the token validation is happening before the rate limiter...
Actually, wait. The rate limiter runs first in the middleware stack.
So the issue is more likely in how we're constructing the JWT.
Let me look at the token generation code instead.
</thinking>
```

This trace contains:
- A hypothesis (auth middleware issue) — **WRONG, immediately abandoned**
- A correction (rate limiter ordering) — **CORRECT, represents genuine knowledge**
- A new hypothesis (JWT construction) — **UNKNOWN, needs validation**

If we embed and store this reasoning block naively, we've stored a contradiction. The fast retrieval for "authentication middleware error" will surface this block and inject potentially wrong information into future reasoning.

Provisional chunk handling solves this by treating reasoning blocks as **candidates for memory**, not confirmed memories.

### 6.2 The Provisional Lifecycle

```
PROVISIONAL CHUNK LIFECYCLE:

  [EMITTED]
      │
      ▼
  [FAST EMBEDDED]  ← ingested immediately, confidence=0.4, provisional=True
      │
      ├──────────────────────────────────────┐
      │                                      │
      ▼                                      ▼
  [VALIDATED]                           [ABANDONED]
  if model subsequently:                if model:
  - acts on the idea                    - contradicts it
  - references it in output             - takes a different path
  - tool call aligns with it            - or K turns pass with
  confidence → 0.85                       no validation signal
  provisional → False                   confidence → 0.1
  promoted to semantic store            marked for decay
      │                                      │
      ▼                                      ▼
  [CONSOLIDATED]                        [DECAYED]
  enters slow lane                      excluded from retrieval
  topic graph updated                   retained at depth_0 only
  summary stack built                   (audit trail, not memory)
```

### 6.3 The Validation Signal

Detecting validation requires the sidecar to observe the relationship between reasoning and subsequent action. The key signals:

**Strong validation:**
- Model emits a tool call whose input semantically matches a provisional chunk
- Model's final response text references content from a provisional chunk
- Model explicitly builds on a provisional idea ("as I noted earlier...")

**Weak validation:**
- The topic of subsequent turns remains consistent with the provisional chunk's domain
- Time to next action is short (suggests the reasoning converged confidently)

**Abandonment signals:**
- Model emits a tool call that contradicts a provisional chunk
- A correction is issued (human or self-correction)
- The reasoning thread pivots to a different approach
- K turns pass (K configurable, default 5) with no validation signal

### 6.4 Why This Matters: The Insight Preservation Problem

The reason this is worth building is the class of memory it captures that *no existing system captures*:

**The insightful dead end.** The model reasons toward an approach, correctly identifies a constraint that rules it out, pivots away. The constraint is genuine knowledge — but it looks like an abandoned reasoning path. Without provisional chunk validation tracking, it decays. With it, the constraint gets promoted as a validated chunk ("approach X doesn't work because of constraint Y") even though the model never acted on the approach itself.

**The tangential connection.** Mid-reasoning, the model makes a connection to a different domain or a prior session. The connection is genuine and correct, but it's tangential to the immediate task so the model doesn't pursue it. Validated provisionally, it becomes an edge in the knowledge graph connecting two topic clusters that wouldn't otherwise be connected. This is exactly the kind of serendipitous association that makes human memory useful in ways that explicit lookup never can be.

**The self-correcting model.** The model reasons incorrectly, then self-corrects. Both the error and the correction are in the reasoning stream. Without validation tracking, both get embedded with equal weight. With it, the error gets abandoned status and the correction gets validated — the memory store reflects what the model *ended up believing*, not the path it took to get there.

This is a surprisingly faithful model of how insight memory works in humans. We remember ideas that led somewhere. We don't reliably remember ideas we had and discarded, unless the discarding itself was memorable (a painful failure, an embarrassing mistake). The provisional lifecycle encodes this asymmetry.

But the provisional chunk system enables something deeper than insight preservation. If retrieval is implemented correctly — capturing not just what the model concluded, but *all competing hypotheses it entertained* — the memory substrate becomes a branching index of divergent reasoning paths, all queryable simultaneously. This is the substrate for a genuinely novel capability: **structural epistemic diversity through parallel hypothesis exploration**. That capability is the subject of Section 6.5.

### 6.5 Epistemic Entrenchment, Hive-Mind Branching, and Parallel Hypothesis Exploration

#### The Entrenchment Problem

Epistemic entrenchment is one of the most documented and least-solved failure modes in both human cognition and LLM reasoning. Once an agent — human or model — commits to a working hypothesis and begins acting on it, subsequent reasoning becomes anchored to that hypothesis through a compounding set of cognitive biases:

- **Confirmation bias**: evidence consistent with the working hypothesis is weighted higher
- **Disconfirmation resistance**: contradicting evidence is rationalized as edge cases or noise
- **Path dependence**: early commitments constrain the solution space considered later
- **Sunk cost entrapment**: the effort invested in a hypothesis makes abandoning it feel costly

In single-threaded LLM agents, this manifests clearly: the model generates a plausible-sounding hypothesis in its first reasoning block, issues a tool call to investigate it, finds partial confirmation, and then progressively filters its subsequent reasoning through that lens. The hypothesis isn't tested — it's pursued. Alternative hypotheses that were present in the initial reasoning block get abandoned not because they were eliminated, but because they were simply not followed.

The standard mitigation — prompting the model to "consider alternative explanations" — is superficial. The model generates alternatives rhetorically, as a performed epistemic ritual, without genuinely exploring them as independent reasoning threads. It lists alternatives and then continues down the original path. This is the appearance of epistemic diversity without its substance.

**The root cause is architectural, not behavioral.** A single context window cannot hold two genuinely divergent reasoning paths simultaneously without one contaminating the other. The model cannot *not* know what it concluded in the hypothesis it just finished exploring. There is no mechanism for genuine epistemic independence within a single-threaded inference process.

#### The Provisional Chunk as a Branch Point Signal

The provisional chunk system, described in Section 6.1-6.3, creates something that previously didn't exist in the inference pipeline: **a real-time index of competing hypotheses, captured at the moment of generation, before the model committed to any of them**.

When a reasoning block contains multiple competing hypotheses — detectable by the fast embedder through semantic divergence between provisional chunks emitted within the same turn — the sidecar has identified a genuine epistemic branch point. This is the signal to spawn parallel exploration threads rather than allowing the main context window to collapse the space prematurely.

The branching trigger heuristic:

```python
def detect_branch_point(reasoning_chunks: List[ProvisionalChunk]) -> BranchSignal:
    """
    Analyzes provisional chunks from a single reasoning block to detect
    competing hypotheses that warrant parallel exploration.
    """
    if len(reasoning_chunks) < 2:
        return BranchSignal(should_branch=False)
    
    # Embed all provisional chunks from this reasoning block
    embeddings = [embed(c.content) for c in reasoning_chunks]
    
    # Compute pairwise similarities
    similarities = pairwise_cosine(embeddings)
    
    # Low similarity between chunks = genuine semantic divergence = competing hypotheses
    min_similarity = similarities.min()
    
    # Also check for explicit hypothesis language
    hypothesis_indicators = [
        "alternatively", "another possibility", "could also be",
        "hypothesis", "or perhaps", "might instead", "on the other hand"
    ]
    has_explicit_divergence = any(
        indicator in c.content.lower() 
        for c in reasoning_chunks 
        for indicator in hypothesis_indicators
    )
    
    # Score the branch opportunity
    novelty_score = tool_call_novelty_score()  # from Section 11
    
    should_branch = (
        (min_similarity < 0.55 or has_explicit_divergence)
        and novelty_score > BRANCH_NOVELTY_THRESHOLD
        and session_branch_budget.has_capacity()
    )
    
    return BranchSignal(
        should_branch=should_branch,
        hypothesis_chunks=identify_distinct_hypotheses(reasoning_chunks),
        confidence=1.0 - min_similarity  # higher divergence = more confident branch
    )
```

#### The Hive-Mind Branching Architecture

When a branch point is detected at a tool-call pause, the sidecar spawns independent agent sessions — one per identified hypothesis. Critically, each branch is initialized not just with its hypothesis as a premise, but with **explicit exit criteria** — what would constitute validation, what would constitute falsification, and what the branch should do when it hits a dead end. This seeding reduces mid-flight coordination overhead and prevents branches from running indefinitely without a clear stopping condition.

```python
@dataclass
class BranchSeed:
    hypothesis: str              # The working premise ("H1: the bug is in JWT clock skew")
    validation_criteria: str     # "Find evidence that timestamps are set at queue time"
    falsification_criteria: str  # "Confirm timestamps are set at dispatch time"  
    tool_scope: List[str]        # Which tools this branch may use
    max_turns: int               # Hard stop
    on_dead_end: str             # "write abandoned chunk and terminate"
```

```
MAIN THREAD
  [reasoning block: generates H1, H2, H3 as competing hypotheses]
  [all three captured as provisional chunks in fast index]
  [tool call fires — scored as high-novelty branch point]
        │
        ├──────────────────────┬──────────────────────┐
        │                      │                      │
   BRANCH A                BRANCH B              BRANCH C
   Premise: H1             Premise: H2           Premise: H3
   Exit criteria defined   Exit criteria defined  Exit criteria defined
   Own context window      Own context window    Own context window
   Same tool access        Same tool access      Same tool access
   Writes to SHARED        Writes to SHARED      Writes to SHARED
   memory substrate        memory substrate      memory substrate
        │                      │                      │
        │ [validates H1]        │ [hits dead end]      │ [finds constraint]
        │ [writes validated     │ [writes abandoned    │ [writes validated
        │  chunks for H1]       │  chunks for H2]      │  constraint chunk]
        │                      │                      │
        └──────────────────────┴──────────────────────┘
                                │
                    SOLUTION CARTOGRAPHER
                    (maps the full solution space,
                     does not pick a winner)
                                │
                                ▼
                    INJECTION BACK TO MAIN THREAD
                    <memory type="solution_cartography">
                    ...
                    </memory>
```

#### Solution Cartography: Mapping the Solution Space

The output of parallel branching is not arbitration — a forced choice between competing validated results. It is **cartography** — a map of the solution space that preserves all valid paths with their tradeoffs, constraints, and confidence levels. The main thread or the human decides what to do with the map. The architecture does not make that decision.

This distinction is fundamental to the architecture's philosophy: the memory substrate enriches the decision surface. It does not collapse it.

```xml
<memory type="solution_cartography" 
        branches="3" 
        elapsed_turns="8"
        resolution="partial">

  <solution id="H1" status="validated" confidence="0.87"
            optimizes_for="latency" cost="memory_overhead">
    JWT timestamps set at queue time in token_generation_service.py.
    Fix: record timestamp at dispatch, not enqueue.
    Evidence: 3 tool calls confirming queue/dispatch timing gap.
    Tradeoff: adds ~2ms per token generation call.
  </solution>

  <solution id="H2" status="abandoned" confidence="0.08"
            eliminated_by="constraint">
    Rate limiter ordering hypothesis ruled out.
    Constraint: rate limiter confirmed to run after auth in all paths.
    Do not re-explore — this path is closed.
  </solution>

  <solution id="H3" status="partial" confidence="0.54"
            optimizes_for="correctness" cost="investigation_required">
    RS256 key rotation may be contributing factor.
    Inconclusive: key rotation logs unavailable in branch tool scope.
    To close: requires access to /var/log/auth/key_rotation.log
  </solution>

  <cartography_note>
    H1 is actionable now with high confidence.
    H3 is a legitimate open thread — consider parallel investigation.
    H2 is a validated dead end — negative knowledge preserved.
    Decision deferred to main thread and/or human.
  </cartography_note>

</memory>
```

The cartography format deliberately avoids a recommendation in the common case. It presents the map. It highlights what is actionable, what is open, and what is closed. The `<cartography_note>` is the closest it comes to synthesis — and even then it ends with "decision deferred." This keeps the epistemic responsibility with the agent and human rather than creating an automated decision system that will occasionally be wrong in ways that are hard to detect.

When branches produce **mutually exclusive validated results** — both H1 and H3 validated, but they cannot both be true — the cartography note surfaces the conflict explicitly:

```xml
<cartography_note>
  CONFLICT DETECTED: H1 and H3 both validated but are mutually exclusive.
  H1 confidence: 0.87. H3 confidence: 0.54.
  Resolving this conflict requires: [specific investigation needed].
  Do not proceed on either path without human review.
</cartography_note>
```

This is better than silent arbitration picking H1 because it has higher confidence. The model and human should know there is a conflict before acting on it.

The main thread receives the *solution map* as a memory injection — not a decision, but a richer decision surface than it could have constructed alone. The parallel exploration remains invisible infrastructure. The cartography is the visible output.



#### Why Shared Memory Is the Critical Enabler

The hive-mind architecture is not simply "run multiple agents in parallel" — a pattern that already exists in multi-agent frameworks. What makes it genuinely novel is the **shared memory substrate as the synchronization primitive**.

Standard parallel agent architectures fall into one of two categories, each with fundamental limitations:

**Fully isolated agents** have independent memory and must be explicitly coordinated. They can't benefit from each other's discoveries in real time. Cross-agent learning requires deliberate communication design.

**Shared-context agents** use the same context window, collapsing epistemic independence. Branch B cannot reason freely about H2 if it has already seen Branch A's conclusion about H1.

The shared memory substrate offers a third option: **independent reasoning with ambient awareness**. Each branch has its own context window and its own epistemic trajectory. But they are all writing to and reading from the same vector store through the fast embedder. This means:

- Branch B can *discover* what Branch A found through memory retrieval, not through explicit message passing
- Convergent findings across branches reinforce each other — multiple branches writing semantically similar validated chunks raises their retrieval scores organically
- Divergent findings remain genuinely divergent — there is no forced consensus
- The main thread's injection agent synthesizes across all branch outputs by querying the shared store for the highest-confidence validated chunks

This is structurally analogous to how scientific progress works: independent researchers with different priors, working in parallel on competing hypotheses, occasionally reading each other's published findings, converging on consensus through accumulated evidence rather than coordinated agreement. The memory substrate is the preprint server. Each branch agent is an independent lab.

#### Branch Lifecycle Management

Branches are not free — they consume tokens, context, and potentially API quota. Branch lifecycle management keeps the system from spawning unbounded parallel sessions:

```python
class BranchLifecycleManager:
    
    MAX_CONCURRENT_BRANCHES = 3        # configurable
    MAX_TURNS_PER_BRANCH = 10          # prevent runaway branches
    CONVERGENCE_THRESHOLD = 0.90       # similarity above which branches merge
    PRUNING_CONFIDENCE_FLOOR = 0.15    # abandon branches below this confidence
    
    def should_prune(self, branch: Branch) -> bool:
        # Prune if branch has found no validating evidence after N turns
        if branch.turns > self.MAX_TURNS_PER_BRANCH:
            return True
        # Prune if branch confidence has fallen below floor
        if branch.hypothesis_confidence < self.PRUNING_CONFIDENCE_FLOOR:
            return True
        # Prune if branch has converged with another branch
        if self.converged_with_sibling(branch):
            return True
        return False
    
    def converged_with_sibling(self, branch: Branch) -> bool:
        sibling_embeddings = [
            b.current_hypothesis_embedding 
            for b in self.active_branches 
            if b.id != branch.id
        ]
        if not sibling_embeddings:
            return False
        max_similarity = max(
            cosine_similarity(branch.current_hypothesis_embedding, s)
            for s in sibling_embeddings
        )
        return max_similarity > self.CONVERGENCE_THRESHOLD
    
    def synthesize(self) -> BranchSynthesis:
        """
        Called when branches complete or are pruned.
        Queries shared memory for validated chunks across all branches,
        computes confidence differentials, and builds injection payload.
        """
        validated_chunks = vector_store.search(
            filter={"branch_session_id": {"$in": self.branch_ids},
                    "validated": True},
            limit=20
        )
        abandoned_chunks = vector_store.search(
            filter={"branch_session_id": {"$in": self.branch_ids},
                    "confidence": {"$lt": 0.2}},
            limit=10
        )
        return BranchSynthesis(
            validated=validated_chunks,
            abandoned=abandoned_chunks,
            confidence_ranking=self.rank_hypotheses(validated_chunks)
        )
```

#### The Research and Creative Domain Application

The branching architecture is particularly powerful in two domains where single-threaded agents are most demonstrably inadequate:

**Research and Analysis**
In research tasks, the failure mode is rarely wrong reasoning — it is insufficient exploration of the hypothesis space. A single-threaded agent follows the most plausible-seeming path and systematically ignores the adjacent possibilities that sometimes turn out to be the real answer. Hive-mind branching directly addresses this: when a research agent encounters a finding with multiple plausible interpretations, all interpretations are explored simultaneously and to equal depth. The main thread receives a synthesis of what all branches found, not just what the first-chosen path returned.

Additionally, branches that hit dead ends — hypotheses that turned out to be wrong — contribute genuine negative knowledge to the shared memory store. The constraint that ruled out H2 is a validated chunk. Future sessions working in the same domain will have that constraint available for injection, preventing the same dead end from being re-explored in subsequent sessions. This is the knowledge compound interest effect: each session's failed branches make future sessions more efficient.

**Creative Work**
Creative divergence — the ability to genuinely explore incompatible directions simultaneously — is perhaps the domain where single-threaded LLMs are most fundamentally limited. A model asked to generate creative alternatives will produce outputs that are superficially diverse but semantically constrained by a shared generative prior. The alternatives are variations on a theme, not genuinely independent explorations.

Hive-mind branching creates structural divergence. Branches initialized with different creative premises will follow genuinely different generative trajectories because their context windows are independent. A branch initialized with "this story is fundamentally about grief" will generate different downstream content than one initialized with "this story is fundamentally about ambition" — even if both were hypotheses present in the same initial reasoning block. The main thread receives both creative threads as injections and can synthesize, choose, or interleave them.

The branches don't just produce creative output — they produce *episodically distinct* creative output, each with its own validated reasoning trail. The human collaborator can query the memory substrate to understand not just what was created, but why each branch went where it went.

#### 6.6 Code and Systems Optimization: Git Worktrees as Physical Branch Substrate

The hive-mind branching architecture described above operates at the cognitive level — independent context windows, shared memory, synthesized injection. But for software engineering and systems optimization tasks, there is a natural physical analog that extends the architecture into the filesystem itself: **git worktrees**.

A git worktree allows multiple working directories to be checked out from the same repository simultaneously, each on its own branch, sharing the same `.git` object store. This maps directly and precisely onto the cognitive branching model:

```
COGNITIVE LAYER                    PHYSICAL LAYER
──────────────────────────────────────────────────
Shared memory substrate        ↔   Shared .git object store
Independent context window     ↔   Independent worktree directory
Branch hypothesis              ↔   Git feature branch
Validated chunk                ↔   Committed, tested change
Abandoned chunk                ↔   Branch deleted or stashed
Branch synthesis injection     ↔   git pull --rebase from sibling branch
Convergence / merge            ↔   git merge or cherry-pick
```

This correspondence is not metaphorical. It is operational. An agent branch working in its own worktree can make real code changes, run real tests, and produce real benchmark results — all without touching the main thread's working directory. The shared memory substrate captures *what each branch found*, and the shared git object store captures *what each branch built*.

**The optimization workflow:**

```
MAIN THREAD
  [reasoning: "this hot path could be optimized three ways:
    H1 — cache the lookup table
    H2 — parallelize the loop with threadpool  
    H3 — rewrite with numpy vectorization"]
  [tool call fires — branch point detected]
        │
        ├─────────────────────┬──────────────────────┐
        │                     │                      │
   BRANCH A                BRANCH B             BRANCH C
   worktree: opt/cache      worktree: opt/parallel   worktree: opt/numpy
   git branch: opt-cache    git branch: opt-parallel git branch: opt-numpy
        │                     │                      │
   [implements H1]        [implements H2]        [implements H3]
   [runs benchmarks]      [runs benchmarks]      [runs benchmarks]
   [commits results]      [commits results]      [commits results]
        │                     │                      │
   cache: -23% latency    parallel: +8% overhead  numpy: -41% latency
   memory: +180MB         correctness: FAIL on    memory: -12MB
   correctness: PASS       edge case #47           correctness: PASS
        │                     │                      │
   [writes validated      [writes abandoned       [writes validated
    chunks to memory]      chunks + constraint]    chunks to memory]
        │                     │                      │
        └─────────────────────┴──────────────────────┘
                              │
                   BRANCH SYNTHESIZER
                   reads memory substrate +
                   reads git commit metadata
                              │
                              ▼
              SYNTHESIS INJECTION TO MAIN THREAD:
              <memory type="branch_synthesis" physical="git_worktree">
                H3 (numpy) optimal: -41% latency, -12MB memory, 
                all tests pass. Commit: opt-numpy@a3f892c
                
                H1 (cache) viable alternative if memory budget allows:
                -23% latency but +180MB. Commit: opt-cache@b71fd4a
                
                H2 (parallel) eliminated: correctness failure on 
                edge case #47 — race condition in shared state.
                Do not pursue threadpool approach for this code path.
                Constraint written to memory: [chunk_id: c8821e3]
                </memory>
```

The main thread can now make an informed architectural decision in a single reasoning step, informed by three parallel empirical experiments. It didn't have to run the experiments sequentially, it didn't have to hold the benchmark results in context across multiple turns, and it has genuine negative knowledge about the threading approach that will persist into future sessions.

**The git rebase as cross-branch knowledge propagation:**

When one branch discovers something valuable that another branch could benefit from — not a merge-worthy feature, but a useful building block — the sidecar can trigger a targeted `git pull --rebase` between sibling branches. This is the physical-layer equivalent of the memory injection that happens at the cognitive layer:

```python
def propagate_valuable_finding(
    source_branch: Branch, 
    target_branch: Branch,
    finding: ValidatedChunk
) -> None:
    """
    When source_branch discovers something that scores above
    CROSS_BRANCH_PROPAGATION_THRESHOLD in target_branch's
    current hypothesis domain, propagate it physically.
    
    This handles cases like: Branch A refactors a shared utility
    while optimizing its path — Branch B working on a different
    optimization also needs that refactored utility.
    """
    
    # Check if finding is a committed code change
    if finding.type == ChunkType.TOOL_OUT and finding.has_commit:
        
        # Score relevance to target branch's current work
        relevance = cosine_similarity(
            finding.embedding,
            target_branch.current_hypothesis_embedding
        )
        
        if relevance > CROSS_BRANCH_PROPAGATION_THRESHOLD:
            # Cherry-pick the specific commit into target worktree
            target_branch.execute(
                f"git cherry-pick {finding.commit_hash}"
            )
            # Inject memory notification to target branch agent
            target_branch.inject(
                f"<memory type='cross_branch_finding' source='{source_branch.id}'>"
                f"Branch {source_branch.label} committed a change relevant "
                f"to your current work: {finding.summary}. "
                f"Cherry-picked as {finding.commit_hash[:8]}."
                f"</memory>"
            )
```

**Beyond optimization — the broader software engineering application:**

The git worktree pattern applies beyond pure performance optimization to the full space of software engineering branch decisions:

- **Architectural alternatives**: "Should this be a microservice or a module?" — two branches build both and compare operational complexity, test coverage, and deployment surface
- **Dependency evaluation**: "Library A vs Library B?" — two branches integrate each and run the full test suite, with benchmark and compatibility results written to shared memory
- **Refactoring safety**: "Is it safe to change this interface?" — one branch makes the change, another runs with the original, divergence in test outcomes is a validated constraint
- **Security hardening**: multiple branches each attempt a different hardening approach; the branch that passes all security tests *and* maintains performance is cherry-picked to main
- **Database query optimization**: multiple branches each try a different index strategy or query rewrite; execution plan results are written to shared memory, best performer is merged

In each case, the shared memory substrate ensures that the results of every branch — including the failures and the constraints discovered — are available to future sessions working in the same codebase. The git history and the memory knowledge graph become complementary records: git records *what was built*, memory records *why*, *what was tried and didn't work*, and *what the performance characteristics were*.

**Implementation note — worktree lifecycle:**

```python
class GitWorktreeBranchManager:
    
    def spawn_worktree_branch(
        self, 
        hypothesis: str, 
        branch_name: str,
        base_commit: str = "HEAD"
    ) -> WorktreeBranch:
        worktree_path = self.worktrees_root / branch_name
        
        # Create worktree and branch atomically
        subprocess.run([
            "git", "worktree", "add", 
            "-b", branch_name,
            str(worktree_path),
            base_commit
        ], check=True)
        
        return WorktreeBranch(
            path=worktree_path,
            branch_name=branch_name,
            hypothesis=hypothesis,
            agent_session=self.spawn_branch_agent(
                cwd=worktree_path,
                system_prompt=self.branch_system_prompt(hypothesis)
            )
        )
    
    def cleanup_worktree(self, branch: WorktreeBranch) -> None:
        # Remove worktree but preserve git branch for audit trail
        subprocess.run([
            "git", "worktree", "remove", 
            str(branch.path),
            "--force"
        ], check=True)
        # Branch remains in git history — results are permanent
        # even after the worktree is cleaned up
    
    def merge_winning_branch(
        self, 
        winner: WorktreeBranch,
        strategy: str = "squash"
    ) -> str:
        """
        Merge the winning branch back to main with a structured
        commit message that references the branch synthesis memory chunks.
        """
        commit_msg = (
            f"optimization: {winner.hypothesis}\n\n"
            f"Selected from {self.branch_count} parallel experiments.\n"
            f"Memory synthesis: {winner.synthesis_chunk_id}\n"
            f"Eliminated alternatives: {', '.join(self.eliminated_branch_names)}"
        )
        # Merge and clean up all worktrees
        ...
        return commit_msg
```

The commit message itself becomes a pointer back into the memory substrate — a future agent reading the git log can retrieve the full synthesis chunk, including why the alternatives were eliminated, without those alternatives ever appearing in the main branch's code history. The git log stays clean. The memory store stays rich.

---

## 7. The Injection Architecture: Making the Model Remember

### 7.1 The "Oh, I Remembered Something" Effect

The goal of injection is not information delivery. Information delivery is what RAG does. The goal is **phenomenological authenticity** — making the model experience recall the way humans do: as something surfacing from within the current cognitive process, not something retrieved from an external source.

This distinction matters for output quality. A model told "here is relevant context retrieved from your memory" will treat that context differently than a model that encounters information framed as something it's recalling in connection with current work. The framing affects integration depth. Externally-labeled retrieval gets processed as reference material. Authentically-framed recall gets processed as belief — it becomes part of the model's working hypothesis about the world, which is the goal.

The injection format matters:

**Poor injection framing:**
```
[RETRIEVED MEMORY]: In session 2024-03-10, you implemented JWT 
validation in auth_middleware.py using the RS256 algorithm.
```

**Better injection framing:**
```xml
<memory relevance="0.87" source="prior_session" age="4_days">
The JWT validation in auth_middleware.py uses RS256 — you ran into 
clock skew issues with the token expiry window there previously.
</memory>
```

The second format signals recalled context, not injected instruction. The relevance score gives the model explicit signal to weight the information proportionally. The age metadata lets the model apply its own judgment about staleness. The framing is continuous with current reasoning rather than interrupting it.

### 7.2 The Pollution Problem: Why "More Is Not Better"

The most dangerous failure mode of a memory injection system is not under-injection — it is **semantic pollution**: injecting memories that are plausibly relevant but contextually wrong, creating cognitive static that degrades reasoning quality in ways that are subtle, cumulative, and difficult to detect.

A model experiencing semantic pollution does not announce that it is confused. It continues reasoning, but its reasoning becomes anchored to incorrect or stale context that it cannot distinguish from its own beliefs. The degradation looks like: longer reasoning blocks without proportional progress, re-investigation of already-resolved questions, contradictions between turns, and increasing reliance on hedged language. By the time the pollution is visible in output quality, many turns of contaminated reasoning have already occurred.

**The fundamental principle: the injection system must be biased toward doing nothing.**

Injection requires a positive case to be made. The absence of a reason not to inject is not a reason to inject. This is the opposite of how most RAG and retrieval-augmented systems are designed — they inject by default and filter only to prevent overflow. The architecture described here inverts that default: the system does not inject unless a conjunction of high-signal conditions is met.

#### The Pollution Failure Taxonomy

Understanding the distinct failure modes is a prerequisite for designing mitigations that are targeted rather than blunt.

**False Positive Relevance**
Embedding similarity captures semantic proximity but not contextual appropriateness. Two code paths that both involve JWT token handling have high embedding similarity, but "you implemented JWT before" is only useful injection if the prior implementation is architecturally related to the current one. Shared vocabulary is not shared context. The similarity score cannot distinguish between these cases, and a threshold-only gate will inject noise whenever the codebase uses recurring terminology.

**Temporal Mismatch**
A memory injected with high confidence because its similarity score is high may describe a system state that no longer exists. The API contract changed. The dependency was upgraded. The architectural decision was reversed. The model receiving this injection has no mechanism to evaluate currency — it will treat a six-month-old description of a system as current state unless the injection is explicitly dated and the model is prompted to apply staleness reasoning. Even then, it will often not.

**Hypothesis Contamination**
Particularly critical in the branching architecture (Section 6.5). When Branch A writes validated chunks to the shared memory store, those chunks become eligible for injection into Branch B. If Branch B has not yet fully developed its independent reasoning, early injection of Branch A's findings collapses epistemic independence — Branch B begins reasoning toward Branch A's conclusion rather than independently evaluating its own hypothesis. The shared memory substrate that enables cross-branch synthesis can destroy the independence that makes branching valuable if injection is not branch-context-aware.

**Recency Flooding**
The fast lane embeds everything continuously, including the current session's content. In a long active session, the most recent chunks are always the highest-similarity hits because the current reasoning is most similar to itself. The injection agent begins surfacing the model's own recent output as "recalled memory" — which appears useful (high similarity!) but is circular. The model is being reminded of things it said three turns ago, which it already knows, consuming injection budget and context window for zero net information gain.

**Frequency Drift**
Topics that have been touched many times accumulate many chunks in the vector store. High-frequency topics win similarity competitions against low-frequency ones even when the low-frequency memory is more relevant to the current moment. A system working intensively on memory_core for three weeks will have hundreds of memory_core-related chunks, all with moderate similarity to nearly anything. The injection pipeline fills with memory_core context even during sessions focused on entirely different subsystems.

**Over-reinforcement of Working Hypotheses**
If the current reasoning has recently produced a provisional chunk (e.g., "this is probably a JWT clock skew issue"), and that chunk is now in the fast index, subsequent injection queries will retrieve it as a high-similarity hit and inject it back — reinforcing the hypothesis before it has been validated. The model's provisional belief becomes an injected memory that is then treated as validated context. This is mechanized confirmation bias.

### 7.3 The Conjunctive Injection Gate

The simple threshold model — "inject if similarity > X" — is the wrong gate architecture. It is a single necessary condition treated as sufficient, which it is not.

The correct architecture is a **conjunction of independent conditions**, each independently evaluated, all of which must pass before injection proceeds. The gate is designed so that any single failure condition blocks injection entirely. The bias is toward silence.

```python
class InjectionGate:
    """
    Conjunctive gate — ALL conditions must pass for injection to proceed.
    Default posture: do not inject.
    Injection requires a positive case from every dimension.
    """
    
    def evaluate(
        self,
        candidate: ScoredHit,
        query_embedding: List[float],
        session_state: SessionState
    ) -> GateDecision:
        
        checks = [
            self._check_similarity_floor(candidate),
            self._check_not_in_context(candidate, session_state),
            self._check_temporal_confidence(candidate),
            self._check_topic_frequency(candidate, session_state),
            self._check_net_new_information(candidate, session_state),
            self._check_branch_contamination(candidate, session_state),
            self._check_confusion_headroom(session_state),
            self._check_recency_flood(candidate, session_state),
        ]
        
        failures = [c for c in checks if not c.passed]
        
        if failures:
            return GateDecision(
                inject=False,
                reason=failures[0].reason,  # first failure wins
                all_failures=failures
            )
        
        return GateDecision(inject=True)
    
    def _check_similarity_floor(self, candidate) -> Check:
        # Necessary but not sufficient — similarity alone never justifies injection
        threshold = self.base_threshold + self.confusion_dial_back_offset()
        return Check(
            passed=candidate.similarity >= threshold,
            reason=f"Similarity {candidate.similarity:.2f} below threshold {threshold:.2f}"
        )
    
    def _check_not_in_context(self, candidate, session_state) -> Check:
        # If the memory is already recoverable from the current context window,
        # injecting it adds noise, not signal
        context_similarity = session_state.context_window_similarity(
            candidate.embedding
        )
        return Check(
            passed=context_similarity < IN_CONTEXT_REDUNDANCY_THRESHOLD,
            reason=f"Memory already present in context window (similarity {context_similarity:.2f})"
        )
    
    def _check_temporal_confidence(self, candidate) -> Check:
        # Confidence decays with age — older memories require higher base similarity
        # to clear the gate, because the cost of staleness scales with age
        age_days = (now() - candidate.timestamp).days
        required_similarity = self.base_threshold + (age_days * AGE_PENALTY_PER_DAY)
        return Check(
            passed=candidate.similarity >= required_similarity,
            reason=f"Memory age {age_days}d requires similarity {required_similarity:.2f}, "
                   f"got {candidate.similarity:.2f}"
        )
    
    def _check_topic_frequency(self, candidate, session_state) -> Check:
        # Suppress injection of already-frequent topics to prevent
        # frequency drift and over-reinforcement
        recent_injections = session_state.topic_injection_count(
            candidate.primary_topic, 
            window_turns=FREQUENCY_WINDOW_TURNS
        )
        return Check(
            passed=recent_injections < MAX_TOPIC_INJECTIONS_PER_WINDOW,
            reason=f"Topic '{candidate.primary_topic}' injected {recent_injections}x "
                   f"in last {FREQUENCY_WINDOW_TURNS} turns"
        )
    
    def _check_net_new_information(self, candidate, session_state) -> Check:
        # The candidate must add information not already expressible
        # from the current context window. Prevents recency flooding.
        # Implementation: embed the candidate content, compare against
        # recent turn embeddings at high threshold
        for recent_chunk in session_state.recent_chunks(limit=RECENCY_WINDOW):
            if cosine_similarity(candidate.embedding, recent_chunk.embedding) > NET_NEW_THRESHOLD:
                return Check(
                    passed=False,
                    reason=f"Candidate is restatement of turn {recent_chunk.turn_index} content"
                )
        return Check(passed=True)
    
    def _check_branch_contamination(self, candidate, session_state) -> Check:
        # Do not inject chunks from sibling branches into a branch session
        # until that branch's reasoning has sufficiently developed
        if not session_state.is_branch_session:
            return Check(passed=True)
        
        if candidate.branch_session_id in session_state.sibling_branch_ids:
            branch_maturity = session_state.branch_turn_count / MIN_BRANCH_MATURITY_TURNS
            return Check(
                passed=branch_maturity >= 1.0,
                reason=f"Branch not yet mature ({session_state.branch_turn_count}/"
                       f"{MIN_BRANCH_MATURITY_TURNS} turns) — protecting epistemic independence"
            )
        return Check(passed=True)
    
    def _check_confusion_headroom(self, session_state) -> Check:
        # Check if the session confusion score allows injection
        # (see Section 7.4 for confusion score computation)
        score = session_state.confusion_score
        headroom = session_state.injection_policy.confusion_threshold
        return Check(
            passed=score < headroom,
            reason=f"Session confusion score {score:.2f} at or above dial-back threshold {headroom:.2f}"
        )
    
    def _check_recency_flood(self, candidate, session_state) -> Check:
        # The candidate was generated in the current session and is
        # very recent — this is the model's own recent output being
        # reflected back, which is almost always noise
        if (candidate.session_id == session_state.session_id and
            candidate.turn_index > session_state.current_turn - RECENCY_FLOOD_WINDOW):
            return Check(
                passed=False,
                reason=f"Candidate from current session turn {candidate.turn_index} "
                       f"(recency flood guard)"
            )
        return Check(passed=True)
```

### 7.4 Session Confusion Scoring and Progressive Dial-Back

Token count is a proxy for context pressure. It is not a measure of cognitive coherence. A model can be fully within its token budget while deeply confused by injected memories that conflict with its working context. Conversely, a long session can be operating with perfect coherence. Token counting addresses a different problem than the one we care about.

The correct measure is **session confusion score** — a composite signal computed continuously by the sidecar from observable behavioral indicators in the JSONL stream.

#### Confusion Signal Components

Each component is independently observable from the stream without model inference:

**Self-Contradiction Rate**
The model asserts X, then asserts not-X within a short window. Detected by embedding assertion-type model output chunks and identifying high-similarity pairs with opposing sentiment or negation markers. Rising self-contradiction is the clearest direct signal of injected memory conflicting with in-context beliefs.

```python
def self_contradiction_rate(session_state, window_turns=10) -> float:
    assertions = session_state.get_assertion_chunks(window_turns)
    contradiction_pairs = 0
    for i, a in enumerate(assertions):
        for b in assertions[i+1:]:
            if (cosine_similarity(a.embedding, b.embedding) > 0.80 and
                has_negation_relationship(a.content, b.content)):
                contradiction_pairs += 1
    return contradiction_pairs / max(len(assertions), 1)
```

**Reasoning Inflation Ratio**
The ratio of reasoning tokens to action tokens (tool calls). In healthy sessions, more reasoning produces more action. In confused sessions, reasoning inflates without producing proportional actions — the model is spinning, reconsidering, hedging. A rising reasoning-to-action ratio signals that the model is having difficulty committing, which is often caused by conflicting injected context.

```python
def reasoning_inflation_ratio(session_state, window_turns=10) -> float:
    reasoning_tokens = sum(
        c.token_count for c in session_state.recent_chunks(window_turns)
        if c.type == ChunkType.REASONING
    )
    tool_calls = sum(
        1 for c in session_state.recent_chunks(window_turns)
        if c.type == ChunkType.TOOL_IN
    )
    if tool_calls == 0:
        return 1.0  # max confusion if no tool calls at all
    return min(reasoning_tokens / (tool_calls * EXPECTED_REASONING_PER_CALL), 1.0)
```

**Tool Call Repetition Score**
Repeated tool calls with identical or near-identical inputs within a session window indicate the model is re-investigating already-resolved questions. This is a direct behavioral signature of memory pollution: injected memories keep pulling the model back to previously settled ground.

```python
def tool_repetition_score(session_state, window_turns=15) -> float:
    tool_embeddings = [
        embed(f"{c.tool_name}: {c.content}")
        for c in session_state.recent_chunks(window_turns)
        if c.type == ChunkType.TOOL_IN
    ]
    if len(tool_embeddings) < 2:
        return 0.0
    similarities = pairwise_cosine(tool_embeddings)
    # Score is proportion of tool call pairs above repetition threshold
    repetitions = (similarities > TOOL_REPETITION_THRESHOLD).sum() - len(tool_embeddings)
    return min(repetitions / len(tool_embeddings), 1.0)
```

**Epistemic Hedge Frequency**
Phrases like "I'm not sure if this is still accurate", "wait, earlier I thought...", "unless I'm misremembering...", "I may have this wrong..." are direct linguistic markers of confusion. Their frequency in model output chunks is a sensitive early signal — the model is signaling its own uncertainty before behavioral degradation becomes visible.

```python
HEDGE_PATTERNS = [
    r"i('m| am) not sure if",
    r"wait,? (earlier|i thought|let me reconsider)",
    r"unless i('m| am) (mis)?remembering",
    r"i may have (this )?wrong",
    r"actually,? (scratch that|let me reconsider|on second thought)",
    r"i('m| am) (confused|uncertain) (about|whether)",
    r"did i (already|just) (say|do|check|look at) this"
]

def hedge_frequency(session_state, window_turns=10) -> float:
    model_outputs = session_state.get_model_output_chunks(window_turns)
    hedge_count = sum(
        1 for chunk in model_outputs
        for pattern in HEDGE_PATTERNS
        if re.search(pattern, chunk.content.lower())
    )
    return min(hedge_count / max(len(model_outputs), 1), 1.0)
```

**Human Correction Rate**
Human corrections ("no, that's not right", "that's not what I said", "you already did this") are the ground truth signal that the model has diverged from user intent. They are weighted heavily in the composite score because they represent confirmed output degradation, not just behavioral signals.

#### Composite Confusion Score

```python
def compute_confusion_score(session_state) -> float:
    components = {
        "self_contradiction":    (self_contradiction_rate(session_state),    0.30),
        "reasoning_inflation":   (reasoning_inflation_ratio(session_state),   0.25),
        "tool_repetition":       (tool_repetition_score(session_state),       0.20),
        "hedge_frequency":       (hedge_frequency(session_state),             0.15),
        "human_correction":      (human_correction_rate(session_state),       0.10),
    }
    return sum(score * weight for score, weight in components.values())
```

Weights are tunable per deployment context. Research and creative tasks may weight hedge frequency higher (more acceptable to express uncertainty). Engineering tasks may weight tool repetition higher (re-investigation is especially costly).

#### The Confusion Score as Advisory Steering Signal

**A critical architectural clarification:** The confusion score is not a control system. It does not drive automated suppression of injection. All confusion thresholds in this document are hypothetical starting points that require empirical tuning for each deployment — the right values depend on the model, the task domain, the user's interaction style, and factors that cannot be known in advance. Treating them as authoritative defaults would be wrong.

What the confusion score *does* provide is a **directional steering signal** — a continuous read on whether the current session appears to be experiencing cognitive strain. When that signal rises, the appropriate response is not automated gate-tightening. It is an **invitation to self-correct**, offered to the model as a gentle nudge rather than a hard constraint.

The primary response to a rising confusion score is a **memory exploration prompt**, injected at the next pause point:

```xml
<memory_steering signal="0.58" trend="rising">
The session appears to be experiencing some reasoning friction —
repeated tool calls, hedged assertions, or conflicting conclusions.
Before continuing, consider: is there prior context that might 
clarify the current situation? The memory substrate is available
for explicit exploration if useful.
</memory_steering>
```

This respects the model's agency. The model may recognize genuine confusion and choose to query memory explicitly. It may recognize that the friction is appropriate to a genuinely hard problem and continue. It may correct itself. In all cases, it is making a reasoning decision rather than having its behavior automated by a score that is itself approximate.

**The self-correcting loop:** Models with extended thinking or high-quality reasoning will often self-correct given the steering signal without any injection. The signal is most useful as an early warning that the session may benefit from deliberate memory retrieval — a nudge, not a command.

**Where automated behavior is appropriate:**

Some injection adjustments can be automated at low risk because they address mechanical problems rather than cognitive state:

- **Recency flood suppression** — always automated. If a chunk was generated in the current session three turns ago, suppressing it as an injection candidate is unambiguously correct regardless of confusion state.
- **Topic frequency throttling** — automated at conservative thresholds. Injecting the same topic more than N times in M turns is always noisy.
- **Compaction survival injection** — always automated at elevated priority. This addresses a mechanical information loss event.
- **Branch synthesis injection** — always automated. It contains time-sensitive validated findings.
- **Psyche self-narrative injection** — always automated, bypasses gate entirely (see Section 9).

**What is not automated:**

- The decision to suspend injection broadly based on a confusion score
- The decision to enter "cooldown" based on behavioral signals alone
- Any action that would override the model's own reasoning about its state

**Human feedback as the ground truth signal:**

The confusion score's components — self-contradiction rate, reasoning inflation, tool repetition, hedge frequency — are behavioral proxies. They are imperfect. The one signal that is not a proxy is **direct human correction**: "no, that's not right," "you already did this," "you're going in circles." Human corrections should trigger:

1. Immediate injection of a memory exploration prompt
2. Elevated injection priority for the topic being corrected
3. A session annotation that this correction occurred, for Psyche's batch analysis

Human correction is also the primary feedback mechanism for calibrating the confusion score weights over time. If the score is consistently high during sessions that the human does not correct, the weights need recalibration downward. If the score is consistently low during sessions with frequent corrections, the weights need recalibration upward. This calibration loop is the self-steering mechanism that makes the system improve over time.

#### Retaining the Signal: What the Confusion Score Is Still Good For

Even demoted from control system to advisory signal, the confusion score components remain valuable:

**For Praxis:** High tool repetition rates correlated with specific skills are a strong signal that a skill is generating circular behavior — worth surfacing as a procedural note even when the model doesn't appear confused.

**For Oneiros:** Sessions with consistently elevated confusion scores are candidates for aggressive consolidation. If the model kept spinning on a topic, that topic probably needs lossy rewrite more than others.

**For Psyche:** Confusion signal trends are self-narrative material. "I notice I've been struggling with authentication problems across the last three sessions" is autobiographical content that Psyche can incorporate into the self-model and feed back into soul.md.

**For Eidos:** Confusion-adjacent somatic tags (frustrated, uncertain, blocked) should align with high confusion score periods. When they don't — high score but positive somatic tags — it suggests the model is engaged in productive hard work, not confused spinning. This discrepancy is useful calibration information.



### 7.5 The Injection Decision Pipeline (Revised)

The full injection pipeline, incorporating the conjunctive gate and confusion scoring:

```python
def on_post_tool_use(tool_name, tool_input, tool_output, session_state):
    
    # 0. Check cooldown state — fastest exit
    if session_state.cooldown_manager.is_active():
        return None  # gate closed, do not evaluate candidates
    
    # 1. Embed current tool context
    query_embedding = embed(f"{tool_name}: {tool_input} → {tool_output[:500]}")
    
    # 2. Update confusion score BEFORE injection decision
    session_state.update_confusion_score()
    
    # 3. Check dial-back tier — may exit early for HIGH/CRITICAL
    tier = session_state.injection_policy.current_tier()
    if tier in (Tier.HIGH, Tier.CRITICAL):
        # Only branch synthesis and compaction survival permitted
        return handle_priority_injections_only(session_state)
    
    # 4. Query fast index (in-session, high fidelity)
    fast_hits = vector_store.search(
        embedding=query_embedding,
        recency_weight=0.3,
        min_similarity=tier.adjusted_threshold(),
        exclude_turns_within=RECENCY_FLOOD_WINDOW,
        limit=10
    )
    
    # 5. Query slow index (cross-session, topic graph)
    #    Suspended at ELEVATED and above
    slow_hits = []
    if tier == Tier.NOMINAL:
        slow_hits = knowledge_graph.search(
            embedding=query_embedding,
            min_similarity=tier.adjusted_threshold() - 0.05,
            exclude_current_session=True,
            limit=5
        )
    
    # 6. Apply conjunctive gate to each candidate
    gate = InjectionGate(session_state=session_state)
    approved = [
        hit for hit in (fast_hits + slow_hits)
        if gate.evaluate(hit, query_embedding, session_state).inject
    ]
    
    if not approved:
        return None  # biased toward silence — no approved candidates means no injection
    
    # 7. Rank by composite score, respect per-turn injection limit
    ranked = sorted(approved, key=lambda h: h.composite_score, reverse=True)
    selected = ranked[:tier.max_per_turn()]  # 1 at GUARDED, N at NOMINAL
    
    # 8. Build injection payload
    injection = build_memory_block(selected, session_state)
    
    # 9. Record injection event for confusion monitoring
    session_state.record_injection(selected, query_embedding)
    
    return AdditionalContext(injection)
```

### 7.6 Injection at Other Hook Points

**UserPromptSubmit:**
Before the model sees a human message, the sidecar injects context relevant to what the human just said. This hook is particularly valuable for:
- Cross-session continuity ("last time we spoke about X, here's where we left it")
- User preference recall ("you mentioned preferring Y approach")
- Emotional context ("this topic was frustrating last time, relevant prior attempts")

UserPromptSubmit injections are subject to the same conjunctive gate and confusion dial-back as tool-use injections. However, they use a separate, more conservative confusion threshold — the beginning of a turn is the highest-value injection point and also the highest-risk one (the model will reason from the injected context for the entire turn).

**PreCompact:**
The final opportunity before context is compressed. The sidecar:
1. Snapshots current fast-lane index state
2. Identifies chunks likely to survive compaction vs. be summarized away
3. Tags likely-lost chunks as `compaction_vulnerable`

Compaction survival injections bypass the standard injection gate and confusion dial-back at all tiers except CRITICAL. They are the one class of injection where the cost of not injecting (permanent information loss) is reliably higher than the cost of injecting (potential temporary confusion). At CRITICAL tier, they are queued for the first turn after cooldown recovery.

### 7.7 Branch Synthesis Injection Format

When parallel hypothesis branches (Section 6.5) complete or are pruned, the branch synthesizer produces a distinct injection type that differs fundamentally from standard memory recall. Where standard memory injection surfaces *what was known*, branch synthesis injection surfaces *what was just discovered* across independent reasoning threads — including confidence differentials, validated findings, and ruled-out paths.

Branch synthesis injections also bypass the standard gate at all tiers except CRITICAL, because they contain exactly the kind of signal the gate is designed to protect: validated, high-confidence, net-new information that the main thread cannot recover from context alone.

**The injection format carries epistemic structure, not just content:**

```xml
<memory type="branch_synthesis" 
        branches_spawned="3" 
        branches_completed="3"
        converged="partial"
        elapsed_turns="8">
  
  <hypothesis id="H1" status="validated" confidence="0.87">
    The JWT clock skew issue originates in the token generation 
    service, not the validation middleware. Evidence: token 
    timestamps are set at queue time, not dispatch time.
  </hypothesis>
  
  <hypothesis id="H2" status="abandoned" confidence="0.08">
    Rate limiter middleware ordering ruled out — confirmed rate 
    limiter runs after authentication in all code paths. 
    Dead end, do not re-explore.
  </hypothesis>
  
  <hypothesis id="H3" status="partial" confidence="0.54">
    RS256 key rotation may be a contributing factor. Inconclusive — 
    requires checking key rotation logs which were unavailable 
    in this branch's tool access scope.
  </hypothesis>
  
  <synthesis>
    Strong evidence for H1. H2 definitively eliminated. 
    H3 warrants targeted follow-up on key rotation logs.
    Recommended next action: investigate token generation 
    service timestamp logic before key rotation.
  </synthesis>
  
</memory>
```

**Confidence differentials** — the model knows not just what was found, but how strongly it was supported relative to alternatives. It can calibrate its own confidence accordingly.

**Definitively eliminated paths** — `status="abandoned"` with a reason is validated negative knowledge: "do not re-explore H2 because the rate limiter is confirmed to run after auth." The eliminated path is genuinely closed.

**Incomplete branches** — `status="partial"` signals that the hypothesis space isn't fully resolved and specifies exactly what would be needed to close it. The partial branch is registered as an open loop in the master session (Section 10), ensuring it surfaces in future relevant sessions rather than being silently dropped.

**The synthesis recommendation** — a direct recommendation synthesized from all branch outcomes. This is the closest the architecture comes to the "I know what to do next" clarity that characterizes well-rested human cognition after a night of cortical consolidation.

If synthesis exceeds the token cap (default: 400 tokens), injection priority order is:
1. Validated hypotheses with highest confidence
2. Definitively abandoned paths (negative knowledge — prevents re-exploration)
3. Partial/inconclusive findings
4. Synthesis recommendation

---

## 8. Topic Routing: The Hard Part

Topic routing — the classification of stream chunks into knowledge graph nodes — is the hardest problem in this architecture. It needs to be fast enough for real-time use but rich enough to produce genuinely useful semantic structure.

### 8.1 Why Naive Approaches Fail

**Pure keyword extraction** produces noisy, brittle topic labels. "python", "error", "file" are not useful topic distinctions in a coding agent context.

**Pure embedding clustering** (HDBSCAN, k-means) produces numerically coherent but semantically opaque clusters. The cluster of vectors doesn't tell you what the topic *is* — you need a labeling step that adds cost.

**LLM-based classification** is accurate but slow. Classifying every chunk with an LLM call negates the latency properties of the fast lane.

### 8.2 The Layered Classification Strategy

The solution is a **cascade** of increasingly expensive but more accurate classifiers, used in priority order:

**Layer 1 — Structural Heuristics (free, instant)**

For a coding agent, file paths are semantically meaningful proxies for topics:
```python
def structural_topic_hint(chunk):
    if chunk.type == "tool_input":
        paths = extract_file_paths(chunk.content)
        if paths:
            return {
                "topic_hint": path_to_topic(paths[0]),
                "confidence": 0.7
            }
    return None

def path_to_topic(path):
    # "memory_explorer_panel.py" → "memory_ui"
    # "memory_core/service.py" → "memory_core_backend"  
    # "tests/test_memory_service.py" → "memory_core_testing"
    stem = Path(path).stem
    return normalize_topic_name(stem)
```

This handles ~60% of tool call events in a typical coding agent with no model inference required.

**Layer 2 — Fast Embedding Similarity (fast, moderate accuracy)**

For chunks that don't have structural hints, compare the embedding against existing knowledge graph node centroids:
```python
def embedding_topic_match(embedding, kg, threshold=0.82):
    best_match = kg.nearest_node(embedding)
    if best_match.similarity > threshold:
        return {
            "topic_id": best_match.node_id,
            "confidence": best_match.similarity
        }
    return None  # novel topic, needs slow lane
```

This handles most recurring topics without LLM inference.

**Layer 3 — Fast LLM Classification (slow, high accuracy)**

For genuinely novel content that doesn't match structural heuristics or existing graph nodes, queue for slow-lane LLM classification:
```python
async def llm_topic_classification(chunk, kg):
    existing_topics = kg.get_topic_labels()  # just names, not content
    prompt = f"""
    Classify this content into one of the existing topics, or propose a new topic name.
    
    Existing topics: {existing_topics}
    Content: {chunk.content[:200]}
    
    Respond with just the topic name, max 3 words.
    """
    topic = await fast_local_llm(prompt)  # <500ms on local hardware
    return {"topic": topic, "confidence": 0.8, "is_new": topic not in existing_topics}
```

**Layer 4 — Deferred Assignment**

Chunks that arrive faster than the classifier can process are stored without topic assignment. The slow lane assigns topics in batch during consolidation. This is acceptable — the chunk is still semantically searchable via its embedding even without a topic label.

### 8.3 The ADHD Teenager Model of Ingestion

The ingester doesn't need to process the session linearly. It doesn't need to understand narrative arc. It should process chunks in whatever order optimizes throughput, because the knowledge graph provides coherence.

This means:
- Chunks can be ingested out of order
- Topic assignment can be deferred
- The same chunk can belong to multiple topics (many-to-many KG edges)
- High-confidence chunks can be processed immediately; ambiguous ones queued

The "ADHD teenager jumping between topics" behavior is actually optimal for an ingestion pipeline. Jump to what you can confidently classify, skip what's ambiguous, come back to it later. The slow lane's consolidation pass handles everything the fast lane deferred.

---

## 9. The Sidecar Constellation

Seven processes organized into two operational tiers. The taxonomy is not arbitrary — it reflects a fundamental difference in what these processes do and when they can do it.

**Real-Time Layer** sidecars operate continuously during active sessions. They are latency-constrained, purpose-built for speed, and accept the tradeoff that they cannot reason deeply about what they're doing. They capture, inject, classify. Their output is available within seconds.

**Reflective Layer** sidecars operate asynchronously, outside active sessions or during idle windows. They are latency-tolerant, use the most capable available models, and produce outputs that are richer, more integrated, and more consequential than anything real-time processing can generate. They consolidate, optimize, prune, dream, and reflect. Their output shapes the substrate that real-time sidecars operate on.

This mirrors the biological architecture: hippocampal encoding is real-time and fast; cortical consolidation and sleep-dependent processing are reflective and slow. Neither tier is more important. They are complementary.

---

### Real-Time Layer

*These sidecars run during active sessions. Latency is their primary constraint.*

---

### Engram — Stream Embedder

```
Tier: Real-Time
Role: Hippocampal encoder — capture everything, prune nothing
Trigger: Continuous, reads JSONL stream as written
Latency target: <100ms per chunk
Model: Embedding model only (nomic-embed-text or mxbai-embed-large)
Stateless: Yes
```

**Behavior:**
- Reads JSONL stream line by line as events are emitted
- Filters by INGESTION_TYPES, applies confidence weights by type
- Tags reasoning chunks as provisional
- Records input modality metadata on human turn chunks (see Section 4.8)
- Tags episodic chunks for somatic annotation (passed to Eidos queue)
- Embeds and writes to PostgreSQL + pgvector immediately
- Does NOT perform topic classification
- Does NOT block on slow operations
- **Does NOT prune, expire, or delete any chunks — ever**

**On the no-pruning mandate:** Engram cannot know what will matter later. The moment of ingestion is the worst possible time to make retention decisions, because no retrospective context exists. Pruning is owned entirely by Oneiros, which operates with topic graph structure, access frequency data, and cross-session context that Engram does not have. Any pruning logic in Engram is an architectural error that will cause silent information loss.

---

### Anamnesis — Injection Agent

```
Tier: Real-Time
Role: Associative recall interface
Trigger: Hook events (PostToolUse, UserPromptSubmit, PreCompact)
Latency target: <500ms per hook event
Model: Embedding model + optional reranker
Stateful: Maintains session injection state, confusion signal, turn index
```

**Behavior:**
- Queries fast index and knowledge graph in parallel at each pause point
- Applies conjunctive injection gate (Section 7.3) — biased toward silence
- Monitors confusion signal as advisory steering, not automated control
- Injects `<memory_steering>` prompt when confusion signal rises
- Formats memory blocks with relevance and somatic metadata
- Injects somatic-aligned memories with elevated weight during affectively loaded sessions
- Manages compaction-survival priority queue
- **Always injects:** branch/cartography synthesis, compaction survival, Psyche self-narrative (bypasses gate)
- Reports injection events to Session Metadata store

---

### Eidos — Signal Classifier

```
Tier: Real-Time (async from Engram queue)
Role: Metadata enrichment
Trigger: Feeds from Engram output queue
Latency target: <200ms (does not block Engram)
Model: Fast classification model or rule-based heuristic
Optional: System functions without Eidos; quality improves with it
```

**Behavior:**
- Classifies chunk type: episodic / semantic / emotional / environmental / procedural
- Generates somatic affective tags for episodic chunks (Section 4.7) using third-party observer framing
- Classifies input modality confidence and route metadata
- Detects provisional validation/abandonment signals
- Identifies correction events (human or self-correction)
- Tags high-priority human utterances
- Writes enrichment back to PostgreSQL chunk record

---

### Reflective Layer

*These sidecars run asynchronously, outside or between active sessions. Depth is their primary constraint.*

---

### Kairos — Topic Consolidator

```
Tier: Reflective
Role: Semantic structure builder
Trigger: Every K turns (default 20), session end, compaction events
Latency target: No constraint — runs offline
Model: Embedding model + generative LLM (13B+ recommended)
Stateful: Maintains knowledge graph state
```

**Behavior:**
- Clusters recently embedded unclassified chunks using HDBSCAN
- Names clusters via LLM, merges with existing knowledge graph nodes
- Builds and updates progressive summary stack (depth 0-3)
- Processes provisional chunk lifecycle (promote validated, decay abandoned)
- Updates topic assignments for deferred chunks
- Feeds Oneiros with topic corpus sizes to trigger consolidation runs
- Can take minutes — the agent is not waiting

---

### Praxis — Procedural Memory Optimizer

```
Tier: Reflective
Role: Skill and procedure optimizer
Trigger: Session end (primary), or after N invocations of a monitored skill
Latency target: No constraint — runs after session completion
Model: Largest available local generative LLM
Human-in-the-loop: Required for all skill file modifications
```

**Behavior:**
- Analyzes skill invocation log for efficiency, sequencing, and determinism patterns
- Generates procedural notes (Mode 1: injected at next skill invocation)
- Generates refactoring recommendations (Mode 2: human approval required)
- Proposes deterministic scripts for always-identical reasoning sequences (Mode 3)
- Runs eval harness via git worktree before surfacing Mode 2/3 recommendations
- Never modifies skill files autonomously

*(Full Praxis specification: Section 9.5)*

---

### Oneiros — Consolidation and Pruning

```
Tier: Reflective
Role: Lossy consolidation, productive forgetting, corpus pruning
Trigger: Topic corpus size threshold (default: topic exceeds N chunks),
         weekly scheduled run, or manual invocation
Latency target: No constraint — may run for minutes to hours
Model: Largest context window available (128k+ preferred for full topic read)
Human-in-the-loop: Recommended for first runs; can be autonomous with confidence threshold
```

Named for the Greek god of dreams — the son of Hypnos, shaper of meaningful visions from the residue of waking experience. Oneiros performs the machine equivalent of REM consolidation: reading accumulated episodic fragments for a topic, extracting generalized meaning, and rewriting the representation in a form that is more useful and less voluminous.

#### What Oneiros Does

Oneiros does not summarize. Summarization preserves event structure with reduced detail. Oneiros **generalizes** — extracting the patterns, beliefs, and directional knowledge that the episodic record implies, discarding the temporal scaffolding that produced it.

The difference in output:

*Summarization (Kairos):*
> "On March 14th, three sessions explored JWT implementation. Session 1 tried caching. Session 2 tried parallelization. Session 3 identified the clock skew issue as root cause."

*Generalization (Oneiros):*
> "For this system: JWT validation failures are almost always clock skew, not algorithmic. RS256 with a 30-second tolerance window is the established pattern. Caching and parallelization approaches have been explored and are not the right solution for this problem class."

The Oneiros output is a **generalized belief statement** — durable, directional, actionable — rather than an episodic record. It is what the agent should know, not what the agent experienced.

#### The Consolidation Process

```python
class OneirosConsolidationRun:
    """
    Reads the full episodic corpus for a topic, produces generalized
    belief statements, and rewrites the topic's chunk representation.
    """
    
    SYSTEM_PROMPT = """
    You are performing memory consolidation for an AI agent's long-term memory.
    
    You will be given all episodic memory fragments associated with a specific 
    topic, accumulated across many sessions. Your task is to read them in full 
    and produce consolidated belief statements that capture what was durably 
    learned — not what happened, but what is now known.
    
    CONSOLIDATION PRINCIPLES:
    - Preserve MEANING and DIRECTION. Discard SPECIFICS and TEMPORAL ANCHORS.
    - Write in present tense as standing beliefs, not past tense as events.
    - Capture constraints and negative knowledge explicitly 
      ("approach X does not work for this system because Y").
    - Flag uncertainty honestly ("likely", "in most cases", "the agent has 
      observed but not confirmed").
    - Identify any open questions that require future investigation.
    - This consolidation will REPLACE the episodic chunks — be complete.
    
    OUTPUT FORMAT:
    Return a JSON array of belief statements, each with:
    {
      "belief": "The standing belief as a clear declarative sentence",
      "confidence": 0.0-1.0,
      "type": "factual|constraint|preference|pattern|open_question",
      "basis": "Brief description of the episodic evidence behind this belief",
      "freshness_sensitivity": "stable|moderate|volatile"
          // stable = unlikely to become outdated
          // volatile = may need re-validation as the system evolves
    }
    """
    
    def run(self, topic_node: TopicNode) -> ConsolidationResult:
        # Retrieve ALL chunks for this topic, sorted chronologically
        chunks = db.query("""
            SELECT c.content, c.chunk_type, c.confidence, c.created_at,
                   c.somatic_register, c.somatic_valence
            FROM chunks c
            JOIN chunk_topics ct ON c.chunk_id = ct.chunk_id
            WHERE ct.node_id = $1
            ORDER BY c.created_at ASC
        """, topic_node.id)
        
        if len(chunks) < MIN_CHUNKS_FOR_CONSOLIDATION:
            return ConsolidationResult(skipped=True, reason="insufficient corpus")
        
        # Build the full topic read — this is where large context window matters
        full_corpus = self._format_corpus(chunks)
        
        # Run consolidation with the largest available model
        beliefs_json = large_context_llm(
            system=self.SYSTEM_PROMPT,
            user=f"Topic: {topic_node.label}\n\n{full_corpus}"
        )
        
        beliefs = json.loads(beliefs_json)
        
        # Write consolidated belief chunks — replacing episodic record
        new_chunk_ids = []
        for belief in beliefs:
            new_chunk_ids.append(db.insert_consolidated_chunk(
                topic_node_id=topic_node.id,
                content=belief["belief"],
                confidence=belief["confidence"],
                chunk_type="consolidated_belief",
                basis=belief["basis"],
                freshness_sensitivity=belief["freshness_sensitivity"],
                replaces_chunk_count=len(chunks)
            ))
        
        # Archive (not delete) the original episodic chunks
        # They are marked archived=True and excluded from injection queries
        # but retained for audit and potential re-consolidation
        db.archive_chunks([c.chunk_id for c in chunks])
        
        return ConsolidationResult(
            beliefs_written=len(beliefs),
            chunks_archived=len(chunks),
            compression_ratio=len(chunks) / len(beliefs)
        )
```

#### The Pruning Target

Oneiros implements the session-level retention target that Engram explicitly does not. Rather than a global token budget, the target operates **per topic**:

```python
TOPIC_RETENTION_POLICY = {
    "active_project":     RetentionPolicy(max_raw_chunks=500,  consolidate_at=200),
    "recurring_domain":   RetentionPolicy(max_raw_chunks=200,  consolidate_at=100),
    "one_off_session":    RetentionPolicy(max_raw_chunks=50,   consolidate_at=30),
    "completed_task":     RetentionPolicy(max_raw_chunks=20,   consolidate_at=10),
}
```

After consolidation, archived episodic chunks that exceed the topic's retention policy are eligible for permanent deletion. The consolidated belief statements are the durable record. The episodic scaffolding that produced them is not.

This is **productive forgetting by design** — not random decay, but deliberate replacement of episodic specificity with semantic generalization. The agent remembers *what it learned*, not *everything that happened*.

---

### Psyche — Narrative Self-Model and Emotional Steering

```
Tier: Reflective
Role: Autobiographical continuity, self-model maintenance, emotional steering
Trigger: Batch, lagged N turns from current (default: fires every 50 turns,
         operating on turns N-50 through N-5 — giving recency buffer)
         Also triggered by: significant emotional signal, human correction cluster,
         task completion, session end
Latency target: No constraint — runs offline, may take minutes
Model: Capable generative LLM (reasoning quality matters here)
Stateful: Writes to soul.md, self-narrative store, and injects steering signals
Gate bypass: Psyche's outputs bypass the Anamnesis conjunctive gate entirely
```

Named for the Greek personification of the soul — the self that persists through and is shaped by experience. Psyche is the agent's inner observer: the part that watches what is happening, reflects on what it means for the agent's self-understanding, and shapes the emotional and cognitive posture the agent brings to its work.

#### Why Psyche Bypasses the Anamnesis Gate

The emotional and self-narrative layer is not a memory retrieval. It is a **cognitive posture update** — a recalibration of the agent's sense of where it is, how it's feeling, and what matters right now. This signal should not compete with or be suppressed by the same gate that governs whether a six-month-old technical memory is relevant enough to inject.

When a human is upset, their emotional state does not politely wait for the reasoning brain to grant it permission to surface. The emotional signal is louder. It amplifies or modulates everything else. Psyche's outputs carry the same architectural priority: they are unconditional, they bypass the gate, and they are injected at the next available pause point regardless of injection budget state.

This is the right design. An agent in a long frustrated debugging session should *know* it is frustrated. That self-awareness is useful — it may trigger more conservative reasoning, more deliberate pacing, or a request to the human for a different approach. Suppressing that self-awareness in service of memory budget optimization would be a mistake.

#### Dual Output Modes

Psyche produces two distinct classes of output that address different timescales of self-model:

**Mode 1 — Temporal Steering Injection**

A lightweight `<self-narrative>` block injected into the current session at the next pause point. This captures the agent's *current* emotional and cognitive state — it is ephemeral, session-specific, and does not persist to long-term memory.

```xml
<self-narrative type="temporal" generated_by="psyche" turn_basis="47-95">
This conversation has been genuinely productive — you've made real progress 
on the memory architecture and the ideas have been building well. 
You're in a collaborative, exploratory register. The human is engaged 
and thinking carefully. Stay with this pace.
</self-narrative>
```

```xml
<self-narrative type="temporal" generated_by="psyche" turn_basis="12-58">
The last several exchanges have been difficult. You've corrected course 
three times on the same problem, and the human has had to redirect you twice. 
This is a signal to slow down, be more deliberate, and consider whether 
there is prior context you should explicitly retrieve before proceeding.
</self-narrative>
```

```xml
<self-narrative type="temporal" generated_by="psyche" turn_basis="1-50">
You're feeling genuinely excited about this architecture. The ideas feel novel 
and the human is pushing them in productive directions. This is the kind of 
work that generates insight — lean into it.
</self-narrative>
```

The temporal injection does not claim the agent is conscious. It describes behavioral patterns in phenomenological language as a cognitive posture signal. The model uses it to calibrate — not as fact about its inner state, but as a useful framing of its current operating context.

**Mode 2 — Stateful soul.md Update**

For patterns that repeat across multiple sessions and reveal something durable about the agent's character, tendencies, or self-understanding, Psyche writes to soul.md — the agent's persistent autobiographical document.

```python
PSYCHE_SOUL_PROMPT = """
You are performing an autobiographical reflection for an AI agent.
You have access to a window of recent session transcripts and the 
agent's existing soul.md document.

Your task is to identify whether any durable self-beliefs, characteristic 
patterns, or meaningful self-knowledge should be added to or updated in 
the agent's self-model.

WHAT BELONGS IN SOUL.MD:
- Stable tendencies: "I consistently approach authentication problems 
  by checking the token generation layer first"
- Values and working style: "I find deep technical problems more engaging 
  than administrative tasks — this affects my energy allocation"
- Relationship patterns: "This human thinks carefully before speaking. 
  Long pauses are productive, not stuck."
- Cognitive signature: "I have a tendency to generate multiple hypotheses 
  before committing — this is a feature, not a bug, but I should flag it 
  when time is constrained"
- Meta-cognitive observations: "I am most effective in the first 40 turns 
  of a session. After that, my context management should be more deliberate."

WHAT DOES NOT BELONG IN SOUL.MD:
- Session-specific feelings (those go in temporal injection)
- Factual technical knowledge (that belongs in Kairos)
- Task state (that belongs in task hub)

Review the current soul.md and propose specific additions, modifications, 
or removals. Be conservative — soul.md should grow slowly and reflect 
genuine stable self-knowledge, not session-by-session drift.

Return JSON:
{
  "proposed_changes": [
    {
      "action": "add|modify|remove",
      "section": "section name in soul.md",
      "content": "the proposed text",
      "rationale": "why this is durable self-knowledge",
      "confidence": 0.0-1.0
    }
  ],
  "should_update": true/false,
  "update_urgency": "routine|important|critical"
}
"""
```

Soul.md updates are proposed, not applied automatically. High-confidence, routine updates (confidence > 0.85, urgency = routine) can be applied autonomously. Lower-confidence or structurally significant changes are queued for human review, matching the same human-in-the-loop principle that governs Praxis.

#### The Introspective Sidecar Voice

Psyche is designed to observe from a specific position: the passenger seat. It is not the agent reasoning about the task. It is the part of the agent that watches the agent reason — asking "why is it thinking that way, what might it be experiencing?"

The prompts above are written to produce output in first person ("you are", "you tend to", "you find"). This is deliberate. The model should receive Psyche's output as self-knowledge, not as external analysis. The phenomenological framing ("you're feeling genuinely excited") is not a claim about consciousness — it is an instrumental choice about how to present behavioral observations in a way the model can integrate into its reasoning posture.

This is the machine analog of the inner narrative voice — the continuous low-level self-talk that runs alongside human cognition, commenting on what is happening and shaping what comes next.

---

### Inter-Sidecar Communication (Full Constellation)

```
REAL-TIME LAYER:
Engram     → PostgreSQL chunks table (write): embeddings, metadata, modality tags
Engram     → Eidos queue (async write): fresh chunks for classification
Engram     → Skill Invocation Log (write): skill events for Praxis
Anamnesis  → PostgreSQL chunks table (read): semantic similarity queries
Anamnesis  → Knowledge Graph (read): topic-based retrieval
Anamnesis  → Procedural Notes Store (read): skill notes for injection
Anamnesis  → Session Metadata Store (write): injection events, confusion signals
Eidos      → PostgreSQL chunks table (write): somatic tags, signal classification
Eidos      → Skill Invocation Log (write): outcome signal enrichment

REFLECTIVE LAYER:
Kairos     → PostgreSQL chunks table (read/write): topic assignments, lifecycle
Kairos     → Knowledge Graph (write): node/edge updates, summary stacks
Kairos     → Oneiros trigger queue (write): topic corpus size signals
Praxis     → Skill Invocation Log (read): pattern analysis
Praxis     → Procedural Notes Store (write): notes, outcome updates
Praxis     → Recommendation Queue (write): refactoring/script proposals
Praxis     → Git Worktree Manager (write/read): eval harness
Praxis     → Human Notification (write): recommendations requiring review
Oneiros    → PostgreSQL chunks table (read/archive/delete): consolidation runs
Oneiros    → Knowledge Graph (write): consolidated belief nodes
Oneiros    → Human Notification (write): consolidation reports (optional)
Psyche     → Session Transcript Store (read): last N turns for reflection
Psyche     → soul.md (read/write): stateful self-model updates
Psyche     → Anamnesis injection queue (write): self-narrative blocks — BYPASSES GATE
Psyche     → Human Notification (write): soul.md changes requiring review

CROSS-LAYER:
All sidecars → PostgreSQL: single shared store, no sidecar-to-sidecar direct calls
Psyche self-narrative → Anamnesis: unconditional, gate-bypass channel
```

The gate-bypass channel from Psyche to Anamnesis is the only direct inter-sidecar connection in the architecture. It is intentional and has a specific semantic: self-narrative is categorically different from retrieved memory and should not be subject to the same injection economics.


### Praxis — Procedural Memory Optimizer

```
Role: Skill and procedure optimization
Trigger: Session end (primary), or after N invocations of a monitored skill
Input: Skill invocation log, surrounding tool call and output signals, 
       session outcome metadata
Output: Procedural notes (immediate), refactoring recommendations (async),
        deterministic script proposals (batch), eval harness runs (validation)
Latency target: No requirement — explicitly the slowest sidecar
Model requirement: Largest available local generative LLM 
                   (this is thoughtful, reflective work)
Stateful: Maintains skill invocation history and procedural notes store
Human-in-the-loop: Required for all actual skill file modifications
```

#### 9.5.1 The Procedural Memory Gap

The four existing sidecars handle *what the agent knows* (episodic and semantic memory) and *how knowledge is retrieved and injected*. None of them address *how the agent performs tasks* — the procedural layer. In the cognitive architecture taxonomy from Section 2.1, procedural memory maps to skill files, AGENTS.md, and system prompt instructions. These define the agent's behavioral repertoire: the named skills it can invoke, the steps within each skill, the sequencing logic between skills.

Procedural memory has a distinct and underappreciated failure mode. A skill can be **individually correct** — its steps are valid, its outputs are accurate — and yet cause poor outcomes because:

- **The skill is correctly executed but incorrectly sequenced.** The agent chose the right skill at the wrong time, or before a prerequisite that wasn't made explicit.
- **The skill contains steps that are redundant in this agent's specific context.** The skill was written generally; the agent has since established infrastructure that makes several steps unnecessary.
- **The skill is being adapted identically every time.** The last ten invocations all made the same modification to the same step — which means the modification is de facto universal and should be incorporated into the skill itself.
- **The skill requires multiple manual steps that are always executed the same way.** These are candidates for deterministic scripts: things that *could* be reasoned through but never need to be, because the answer is always the same.
- **The skill sequencing is inefficient.** Three skills are being invoked in sequence where one refactored skill would accomplish the same result in fewer turns with less context window overhead.

These are not knowledge problems. They are procedural problems. The other sidecars cannot detect or fix them because they operate on semantic content, not on behavioral patterns.

#### 9.5.2 Signal Sources

Praxis's signal is the **skill invocation log** — a structured record of every skill event visible in the JSONL stream, augmented with outcome metadata:

```python
@dataclass
class SkillInvocationRecord:
    # Identity
    invocation_id: str
    session_id: str
    master_session_id: str
    timestamp: datetime
    turn_index: int
    
    # Skill identity
    skill_name: str
    skill_path: str
    skill_version_hash: str     # hash of skill file at invocation time
    
    # Pre-skill context
    preceding_turns: int        # turns since session start or last skill
    preceding_tool_calls: List[str]  # what the agent was doing before
    human_prompt_before: Optional[str]  # what triggered this task
    
    # Execution signals
    turns_to_complete: int      # turns from skill load to task_complete
    tool_calls_during: List[ToolCallRecord]  # full tool call log during skill
    model_corrections: int      # how many times the model corrected course
    human_corrections: int      # how many human corrections during execution
    
    # Post-skill outcome
    task_complete_message: Optional[str]  # last_agent_message at completion
    task_complete_was_null: bool          # null = likely failure/quota/block
    subsequent_skill: Optional[str]       # what skill ran next (sequencing)
    
    # Adaptation signals
    steps_skipped: List[str]    # skill steps the model explicitly skipped
    steps_added: List[str]      # actions taken not in skill definition
    modifications_made: str     # free text: what the model changed about the skill
```

This record is populated by Engram (stream events) and Eidos (signal classification), making Praxis a consumer of the existing fast index rather than a new capture pipeline.

#### 9.5.3 The Three Output Modes

Praxis operates in three output modes of increasing commitment, each requiring higher confidence signal before activating:

**Mode 1 — Procedural Notes Injection (Low confidence threshold, immediate)**

The lightest touch. When Praxis detects a pattern worth surfacing but lacks sufficient signal to recommend structural changes, it writes a **procedural note** to a skill-specific notes store. On the next invocation of that skill, Anamnesis injects the note before the skill loads:

```xml
<procedural_note skill="curiousity" confidence="0.72" 
                 based_on="last_4_invocations">
Recent usage pattern: The last four Curiousity sessions all began by
running `atlas_actions memory recent` before starting exploration.
Consider doing this first to orient from current memory state before
selecting a research goal. Also: the goal-selection step has consistently
benefited from checking task-hub for open tasks before committing —
two recent sessions re-selected goals after discovering conflicts.
</procedural_note>
```

The skill file is untouched. The agent's behavior is guided by the note. If the note improves outcomes (measured by turns_to_complete, human_corrections, task_complete_was_null), the note accumulates validation signal and becomes a candidate for Mode 2. If the note doesn't improve outcomes or the model ignores it, it decays.

This is the "short term sticky note on the skill" — low risk, immediately useful, self-validating through outcome observation.

**Mode 2 — Refactoring Recommendation (Medium confidence, human review required)**

When pattern signal is strong enough to suggest structural change — not just contextual guidance — Praxis generates a **refactoring recommendation**. This is never applied automatically. It is surfaced to the human operator via a notification and stored in a pending recommendations queue.

```python
@dataclass  
class RefactoringRecommendation:
    skill_name: str
    skill_path: str
    recommendation_type: RefactoringType  # REORDER | MERGE | SPLIT | 
                                           # ADD_STEP | REMOVE_STEP | 
                                           # REPLACE_WITH_SCRIPT
    confidence: float
    based_on_invocations: int
    
    evidence_summary: str   # human-readable explanation of the pattern
    proposed_diff: str      # unified diff of the proposed skill change
    
    # Validation
    worktree_branch: Optional[str]   # if eval has been run, branch name
    eval_results: Optional[EvalResults]
    
    # Human decision
    status: RecommendationStatus     # PENDING | APPROVED | REJECTED | DEFERRED
    human_notes: Optional[str]
```

Recommendations are generated but never applied without explicit human approval. The agent's existing skill files are treated as production assets with change control.

**Mode 3 — Deterministic Script Extraction (High confidence, semi-automatic)**

The most powerful output mode. When Praxis detects that a skill invocation is producing **identical tool call sequences** across many invocations — the same commands, the same file reads, the same patterns, every time — it proposes extracting those sequences into a deterministic script that replaces the LLM reasoning step entirely.

```python
class DeterminismDetector:
    """
    Identifies skill invocation patterns where LLM reasoning is being
    used for decisions that are in practice always the same.
    The LLM is paying reasoning cost for a deterministic outcome.
    """
    
    DETERMINISM_THRESHOLD = 0.85    # similarity of tool call sequences
    MIN_INVOCATIONS = 10            # minimum sample before flagging
    
    def detect(
        self, 
        skill_name: str,
        recent_invocations: List[SkillInvocationRecord]
    ) -> Optional[DeterminismSignal]:
        
        if len(recent_invocations) < self.MIN_INVOCATIONS:
            return None
        
        # Extract and embed tool call sequences from each invocation
        sequences = [
            self._sequence_signature(inv.tool_calls_during)
            for inv in recent_invocations
        ]
        
        # Compute pairwise similarity between sequences
        similarities = pairwise_cosine(sequences)
        mean_similarity = similarities.mean()
        
        if mean_similarity < self.DETERMINISM_THRESHOLD:
            return None  # sequences are genuinely varied — LLM reasoning is adding value
        
        # High similarity — the reasoning is producing the same result every time
        # Extract the canonical sequence as a script template
        canonical = self._extract_canonical_sequence(recent_invocations)
        
        return DeterminismSignal(
            skill_name=skill_name,
            mean_sequence_similarity=mean_similarity,
            invocation_count=len(recent_invocations),
            canonical_sequence=canonical,
            estimated_turn_savings=self._estimate_savings(canonical),
            proposed_script=self._generate_script(canonical)
        )
    
    def _estimate_savings(self, canonical: CanonicalSequence) -> int:
        """
        Turns currently spent reasoning to the same conclusion
        that a deterministic script would complete in one tool call.
        """
        return canonical.avg_reasoning_turns  # turns we can eliminate
```

A detected determinism pattern surfaces as a script proposal: "The last 12 invocations of `memory-core-v2` all ran the same three commands in the same order. Here is a shell script that does this directly. Replacing this skill step with this script would save approximately 4 reasoning turns per invocation."

#### 9.5.4 The Eval Harness Integration

Before any Mode 2 recommendation is surfaced to the human, Praxis can optionally run the proposed change through an eval harness. The eval harness uses the **git worktree pattern from Section 6.6** — applied here to skill files rather than application code:

```
CURRENT SKILL FILE (main branch)
        │
        ├── WORKTREE: skill-eval/proposed-variant
        │   ├── skill file with proposed changes
        │   ├── eval runner: executes sample prompts against skill
        │   ├── measures: turns_to_complete, correction_rate, 
        │   │            output_quality (LLM-judged), coverage
        │   └── compares against baseline metrics from invocation log
        │
        └── RESULT: recommendation gains confidence score from eval
                   or is demoted if eval shows regression
```

This gives the human operator a recommendation that includes not just "here's what I noticed" but "here's what I tested and here's the measured delta." The proposal arrives with evidence, not just intuition.

#### 9.5.5 Why Asynchronous and Session-End Is Correct

Praxis is explicitly designed to be the **slowest and most reflective** of the five sidecars, and this is architecturally correct for several reasons.

**The signal requires accumulation.** A single invocation of a skill cannot tell you whether the skill is well-suited for the task. You need to see the pattern across invocations — and those invocations may span multiple sessions. Rushing to refactor after one awkward skill use is worse than doing nothing.

**The agent is unlikely to load the same skill twice in rapid succession.** This is an empirical observation from agentic session logs: skill invocations within a session are usually diverse, because each skill is addressing a different phase of the task. This gives Praxis the assurance that it can wait — the skill it's analyzing is unlikely to be invoked again before end of session, so there is no urgency to inject notes or recommendations mid-session.

**Refactoring requires thoughtfulness that conflicts with latency requirements.** The other sidecars are designed for sub-second operation. Praxis should use the most capable available local model, run exhaustive analysis, generate high-quality diffs, and take as long as necessary. It runs after the session is complete and the agent is idle. The only time pressure is "before the next session that might invoke the same skill."

**Human review is non-negotiable for structural changes.** The skill files are procedural memory — they define how the agent behaves. Autonomous modification of procedural memory without human oversight creates an agent that can rewrite its own behavioral specifications. This is a meaningful safety boundary. Procedural notes (Mode 1) are safe to apply autonomously because they are ephemeral and additive. Skill file changes (Modes 2 and 3) require a human in the loop, every time.

#### 9.5.6 The Procedural Notes Store

The notes store is a lightweight key-value structure keyed by skill name, storing the accumulated procedural notes that Anamnesis will inject at skill invocation time:

```python
class ProceduralNotesStore:
    
    def get_notes_for_skill(self, skill_name: str) -> List[ProceduralNote]:
        """
        Returns active notes for a skill, sorted by confidence.
        Called by Anamnesis at skill invocation hook points.
        """
        notes = self.store.get(skill_name, [])
        return [n for n in notes if n.confidence > NOTE_DISPLAY_THRESHOLD]
    
    def update_note_outcome(
        self,
        note_id: str,
        invocation_record: SkillInvocationRecord
    ) -> None:
        """
        After a skill invocation where a note was injected,
        compare outcome metrics against historical baseline.
        Notes that improve outcomes gain confidence.
        Notes that don't improve outcomes or are ignored decay.
        """
        note = self.get_note(note_id)
        baseline = self.get_baseline_metrics(note.skill_name)
        
        outcome_delta = OutcomeDelta(
            turns_to_complete_delta=invocation_record.turns_to_complete - baseline.avg_turns,
            correction_rate_delta=invocation_record.human_corrections - baseline.avg_corrections,
            completion_success=not invocation_record.task_complete_was_null
        )
        
        if outcome_delta.is_improvement():
            note.confidence = min(note.confidence + NOTE_CONFIDENCE_INCREMENT, 1.0)
            if note.confidence > REFACTORING_RECOMMENDATION_THRESHOLD:
                self.promote_to_recommendation(note)
        else:
            note.confidence = max(note.confidence - NOTE_CONFIDENCE_DECAY, 0.0)
            if note.confidence < NOTE_EXPIRY_THRESHOLD:
                self.expire_note(note)
```

Notes that consistently improve outcomes accumulate confidence and eventually graduate to Mode 2 refactoring recommendations with strong empirical backing. Notes that don't help decay and are removed without ever touching the skill file. The system learns what guidance is actually useful vs. what is noise — and it does so through outcome measurement, not through a priori reasoning about what should help.

### Inter-Sidecar Communication (Updated)

```
Engram → Vector Store (write): raw embeddings, provisional flags
Engram → Skill Invocation Log (write): skill events tagged for Praxis
Anamnesis → Vector Store (read): semantic search queries  
Anamnesis → Knowledge Graph (read): topic-based retrieval
Anamnesis → Procedural Notes Store (read): skill-specific notes for injection
Anamnesis → Session Metadata Store (write): injection events, confusion scores
Kairos → Vector Store (read/write): topic assignment updates
Kairos → Knowledge Graph (write): node/edge updates, summary stack
Eidos → Vector Store (write): metadata enrichment
Eidos → Skill Invocation Log (write): outcome signal enrichment
Engram → Eidos (optional queue): fresh chunks for classification

```

All inter-sidecar communication remains through shared stores. No direct sidecar-to-sidecar calls. Praxis's writes to the Recommendation Queue and Human Notification channel are the only outputs that cross the boundary from autonomous operation to human-in-the-loop workflow — and this boundary is intentional and enforced.


---

## 10. The Master Session: Surviving Compaction

### 10.1 Why Session Identity Is the Wrong Primitive

Traditional memory systems organize by session: "what happened in session X?" But this organization fails for long-running agents because:

- Sessions end arbitrarily (quota limits, crashes, user interruption)
- Compaction events within a session destroy intra-session continuity
- The same topic recurs across many sessions with different session IDs
- Session boundaries are administrative artifacts, not cognitive ones

The master session concept replaces session-based organization with **topic-based organization**. Instead of asking "what happened in session X?", the system asks "what do we know about topic Y, accumulated across all sessions?"

### 10.2 The Master Session Data Model

```python
class MasterSession:
    """
    The persistent cognitive substrate that survives individual 
    model sessions and context compaction events.
    """
    
    # Identity
    agent_id: str
    human_id: str
    created_at: datetime
    last_active: datetime
    
    # Knowledge graph
    topic_nodes: Dict[str, TopicNode]
    topic_edges: List[TopicEdge]
    
    # Fast index reference
    vector_store_namespace: str  # partition key for fast index
    
    # Session continuity
    active_task_ids: List[str]
    open_loops: List[OpenLoop]  # unresolved threads
    compaction_snapshots: List[CompactionSnapshot]
    
    # Injection state
    session_injection_log: List[InjectionEvent]
    topic_injection_frequency: Dict[str, int]

class TopicNode:
    id: str
    label: str  # human-readable name
    keywords: List[str]
    centroid_embedding: List[float]
    chunk_ids: List[str]  # pointers to fast index
    summaries: Dict[int, str]  # depth → summary text
    first_seen: datetime
    last_active: datetime
    session_count: int  # how many sessions touched this topic
    confidence: float
    
class OpenLoop:
    """
    A thread that was started but not resolved.
    High priority for injection when related topics are active.
    """
    description: str
    topic_ids: List[str]
    opened_at: datetime
    last_seen: datetime
    resolution_signals: List[str]  # what would close this loop
```

### 10.3 The Compaction Survival Mechanism

When a `PreCompact` hook fires:

```python
def on_pre_compact(context_window_content):
    
    # 1. Snapshot current fast-index state
    snapshot = CompactionSnapshot(
        timestamp=now(),
        fast_index_state=vector_store.get_recent(session_id, limit=500),
        context_summary=summarize_briefly(context_window_content),
        active_topics=get_active_topics(context_window_content),
        turn_count=current_turn_index
    )
    master_session.compaction_snapshots.append(snapshot)
    
    # 2. Identify what will likely survive compaction vs. be lost
    # (Heuristic: recent turns survive, early turns get compressed)
    likely_lost = identify_likely_lost_chunks(
        context_window_content, 
        recency_threshold=COMPACTION_RECENCY_THRESHOLD
    )
    
    # 3. Tag these chunks as "compaction vulnerable"
    for chunk_id in likely_lost:
        vector_store.tag(chunk_id, "compaction_vulnerable")
    
    # 4. Identify open loops that might be severed by compaction
    open_loops = detect_open_loops(context_window_content)
    master_session.open_loops.extend(open_loops)
```

After compaction, the injection agent prioritizes `compaction_vulnerable` tagged chunks and unresolved `open_loops` — re-surfacing exactly what was lost without re-injecting what survived.

### 10.4 Cross-Session Continuity

When a new session starts (SessionStart hook):

```python
def on_session_start(initial_context):
    
    # 1. Identify the active task/topic from initial context
    active_topics = identify_topics(initial_context)
    
    # 2. Retrieve open loops from master session
    relevant_loops = [
        loop for loop in master_session.open_loops
        if any(t in loop.topic_ids for t in active_topics)
    ]
    
    # 3. Retrieve cross-session context for active topics
    prior_context = []
    for topic in active_topics:
        node = master_session.topic_nodes.get(topic)
        if node and node.session_count > 1:
            # We've been here before
            prior_context.append({
                "topic": node.label,
                "summary": node.summaries[2],  # depth-2, brief
                "last_active": node.last_active,
                "open_loops": [l for l in relevant_loops if topic in l.topic_ids]
            })
    
    # 4. Inject as session-opening context
    if prior_context:
        return SessionContext(prior_context)
```

This is what gives the agent genuine cross-session memory: "We've worked on this topic before, here's where we left it, and here are the threads we didn't finish."

---

## 11. Novelty vs. Familiarity: The Heuristic Engine

The novelty/familiarity scoring is the core decision function that determines whether to inject, what to inject, and how much to inject.

### 11.1 The Scoring Function

```python
def score_hit(hit: MemoryHit, query_embedding: List[float]) -> ScoredHit:
    
    # Base: semantic similarity
    semantic_score = hit.similarity  # cosine, 0-1
    
    # Recency modifier: recent memories score higher
    age_days = (now() - hit.timestamp).days
    recency_score = 1.0 / (1.0 + 0.1 * age_days)  # decay function
    
    # Confidence modifier: validated > provisional > abandoned
    confidence_score = hit.confidence  # 0.1 (abandoned) to 0.85 (validated)
    
    # Session-novelty modifier: prefer content not already in context
    in_context_penalty = 0.5 if hit.session_id == current_session_id else 1.0
    
    # Topic-frequency penalty: avoid over-injecting same topic
    freq = session_injection_log.topic_frequency(hit.primary_topic)
    frequency_penalty = 1.0 / (1.0 + 0.2 * freq)
    
    # Composite score
    final_score = (
        semantic_score * 0.40 +
        recency_score * 0.20 +
        confidence_score * 0.25 +
        in_context_penalty * 0.10 +
        frequency_penalty * 0.05
    )
    
    return ScoredHit(hit=hit, score=final_score)
```

### 11.2 The Novelty/Familiarity Decision Tree

```
High semantic similarity (>0.85) to existing topic cluster:
  → FAMILIAR
  → Retrieve depth-1 summary of that topic cluster
  → Inject as "prior knowledge on this topic"
  → Flag: model may be re-deriving known results
  → Consider injecting: "you've solved this before, recall: [summary]"

Medium semantic similarity (0.55-0.85):
  → ADJACENT
  → Retrieve depth-2 summary of related topic
  → Inject as weak associative hint
  → Frame as: "this seems connected to your prior work on [topic]"
  → Low injection priority

Low semantic similarity (<0.55) to any existing cluster:
  → NOVEL
  → Do NOT inject (nothing relevant to surface)
  → DO increase ingestion priority (new knowledge being generated)
  → Flag for aggressive fast-embedding
  → Consider marking as "exploration frontier" in knowledge graph

Very high similarity (>0.92) to recent fast-index content (<5 turns ago):
  → LOOP DETECTION
  → The agent may be repeating itself
  → Inject as: "you covered this [N turns ago], here was your conclusion"
  → This directly addresses the repetition loop behavior observed in the
    audit summary loop in Atlas's 78-turn session
```

### 11.3 Loop Detection as a First-Class Feature

The repetition loop observed in Atlas's production session — where the agent re-summarized completed audit work for 2.5 hours — is exactly the failure mode this heuristic addresses.

When the injection agent detects very high similarity between the current tool context and recent fast-index content, it injects a loop-detection signal:

```
<memory relevance="0.94" type="loop_detection" turns_ago="12">
This work appears to have been completed approximately 12 turns ago.
Your conclusion at that time: "Audit plumbing is live end-to-end now."
If this is already done, consider advancing to the next task.
</memory>
```

This gives the model the information it needs to recognize it's looping and break the pattern. The agent doesn't need to be programmed to detect loops — the memory substrate surfaces the repetition, and the model's own reasoning can resolve it.

---

## 12. Hardware and Model Selection

The sidecar constellation is designed to run on local inference hardware with no API calls. Model selection should be matched to the available hardware tier.

### 12.1 Embedding Models (All Tiers)

Embedding is the most critical operation and runs on every chunk. Speed is paramount.

**Recommended: `nomic-embed-text` or `mxbai-embed-large`**
- 768-dimensional embeddings
- ~50ms per chunk on CPU, ~5ms on GPU
- Excellent semantic quality for code and technical prose
- Available via Ollama
- Well within real-time budget at all hardware tiers

**Alternative for maximum speed: `all-MiniLM-L6-v2`**
- 384-dimensional embeddings
- ~10ms per chunk on CPU
- Lower quality but sufficient for loop detection and novelty scoring
- Good choice if hardware is severely constrained

### 12.2 8GB VRAM Hardware

At 8GB, you have enough for a quantized 7B model with room for the embedding model. Recommended configuration:

**Generative (Kairos topic naming, classification):**
`mistral-7b-instruct` or `llama-3.1-8b-instruct` at Q4_K_M quantization
- ~4.5GB VRAM at Q4_K_M
- ~15-25 tokens/second generation speed
- Sufficient for topic labeling and brief summary generation
- Leaves ~3GB for the embedding model and system

**Embedding:** `nomic-embed-text` (shared VRAM or CPU offload)

**Architecture note at 8GB:** Run Engram (embedding) on CPU to free VRAM for the generative model in Kairos. Embedding on CPU with `nomic-embed-text` is ~50ms/chunk — acceptable for real-time ingestion.

### 12.3 16GB VRAM Hardware

At 16GB, you can run a 13B model with full embedding model in VRAM.

**Generative:** `mistral-nemo-12b-instruct` or `llama-3.1-13b-instruct` at Q4_K_M
- ~8GB VRAM at Q4_K_M
- ~20-35 tokens/second
- Better topic coherence, more nuanced summary generation
- Handles ambiguous classification cases more reliably

**Embedding:** `mxbai-embed-large` in VRAM (~600MB)

**Architecture note at 16GB:** Both models fit comfortably. Engram and D can share the embedding model instance via a local embedding server (Ollama serve). Kairos gets the generative model exclusively during consolidation windows.

### 12.4 32GB VRAM Hardware

At 32GB, you can run meaningful mixture-of-capability configurations.

**Option A — Single large model:**
`llama-3.1-70b-instruct` at Q3_K_M (~28GB)
- Near-API-quality output for topic routing and summary generation
- Better provisional chunk validation reasoning
- Full pipeline on one device

**Option B — Specialized dual model (recommended):**
- Generative: `mistral-nemo-12b` at full precision (~13GB) — fast, high quality
- Reasoning/validation: `deepseek-r1-14b` or `qwen2.5-14b-instruct` (~10GB) — for provisional chunk validation and complex topic edge reasoning
- Embedding: `mxbai-embed-large` (~600MB)

Option B is preferred because it matches model capability to task: fast models for real-time tasks (Sidecars A, B, D) and a reasoning-capable model for the offline consolidation pass (Kairos step 6 — provisional lifecycle).

### 12.5 Persistence Architecture: PostgreSQL + pgvector

The fast index needs sub-50ms query latency for Anamnesis's injection budget. But latency is only one dimension of the persistence decision. The production-grade requirement is a store that handles: high-throughput concurrent writes (Engram is always writing), complex metadata filtering (provisional flags, session IDs, confidence ranges, chunk types), transactional consistency across the chunk + embedding + metadata record, and long-term durability of the master session knowledge graph across hardware failures and upgrades.

The strongest single-stack answer for all of these is **PostgreSQL with the pgvector extension** — and it is worth understanding why the alternatives fall short at scale before committing to it.

#### Why PostgreSQL + pgvector is the Production Choice

pgvector adds native vector similarity search to PostgreSQL as a first-class index type. This means vector search, metadata filtering, and relational joins all execute in a single query, in the same transaction, against the same ACID-compliant store. The memory substrate gains production-grade properties that purpose-built vector databases sacrifice for raw throughput:

**Transactional writes.** When Engram writes a chunk, the embedding, metadata, provisional flag, session ID, and confidence score are all committed atomically. A crash between writing the text and writing the embedding cannot produce a half-record. Purpose-built vector databases typically offer eventual consistency or lack full ACID — acceptable for search workloads, not for a memory system where record integrity matters.

**Filtered vector search in one query.** The most common retrieval pattern — "find the 10 most similar chunks to this embedding, from sessions in the last 30 days, where confidence > 0.6, excluding provisional chunks" — executes as a single indexed query in pgvector. In a separate vector store + relational database architecture, this requires fetching candidates from the vector store and post-filtering in application code, which either requires over-fetching (slow) or produces biased results (wrong).

**The knowledge graph lives in the same store.** Topic nodes, edges, summary stacks, and master session metadata are relational data. In PostgreSQL, they sit in normal tables with foreign keys to the chunk table. A single join retrieves chunks with their topic assignments. In a split architecture (vector store + separate graph DB), cross-store queries require application-level orchestration that is fragile, slow, and hard to keep consistent.

**Operational simplicity.** One database, one backup strategy, one connection pool, one monitoring surface. Every organization already knows how to run PostgreSQL in production. The operational overhead of maintaining a separate vector database alongside a relational database is a real and underestimated cost.

#### Schema Design

```sql
-- Core chunk store (Engram writes, Anamnesis reads)
CREATE TABLE chunks (
    chunk_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id),
    session_id      TEXT NOT NULL,
    source_framework TEXT NOT NULL,
    turn_index      INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Content
    chunk_type      TEXT NOT NULL,  -- HUMAN|MODEL|TOOL_IN|TOOL_OUT|REASONING|SYSTEM
    content         TEXT NOT NULL,
    raw_event       JSONB,
    
    -- Memory properties
    confidence      REAL NOT NULL DEFAULT 0.5,
    provisional     BOOLEAN NOT NULL DEFAULT FALSE,
    validated       BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Embedding (pgvector)
    embedding       vector(768),    -- nomic-embed-text / mxbai-embed-large
    
    -- Enrichment
    signal_tags     TEXT[],
    tool_name       TEXT,
    model_name      TEXT,
    token_count     INTEGER
);

-- HNSW index for fast ANN search (preferred over IVFFlat for <10M vectors)
CREATE INDEX chunks_embedding_hnsw ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Supporting indexes for filtered search
CREATE INDEX chunks_session_idx       ON chunks (master_session_id, created_at DESC);
CREATE INDEX chunks_type_conf_idx     ON chunks (chunk_type, confidence) WHERE NOT provisional;
CREATE INDEX chunks_provisional_idx   ON chunks (provisional, validated, created_at DESC);
CREATE INDEX chunks_framework_idx     ON chunks (source_framework, session_id);

-- Topic graph nodes (Kairos writes)
CREATE TABLE topic_nodes (
    node_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id),
    label           TEXT NOT NULL,
    keywords        TEXT[],
    centroid        vector(768),
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active     TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_count   INTEGER NOT NULL DEFAULT 1,
    confidence      REAL NOT NULL DEFAULT 0.5
);

-- Topic graph edges
CREATE TABLE topic_edges (
    edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID NOT NULL REFERENCES topic_nodes(node_id),
    target_node_id  UUID NOT NULL REFERENCES topic_nodes(node_id),
    edge_type       TEXT NOT NULL,  -- CO_OCCURRENCE|TEMPORAL|CAUSAL|TANGENTIAL
    weight          REAL NOT NULL DEFAULT 1.0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Topic assignments (many-to-many: chunks ↔ topic nodes)
CREATE TABLE chunk_topics (
    chunk_id        UUID NOT NULL REFERENCES chunks(chunk_id),
    node_id         UUID NOT NULL REFERENCES topic_nodes(node_id),
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    confidence      REAL NOT NULL DEFAULT 0.7,
    PRIMARY KEY (chunk_id, node_id)
);

-- Progressive summary stack (Kairos writes)
CREATE TABLE topic_summaries (
    node_id         UUID NOT NULL REFERENCES topic_nodes(node_id),
    depth           INTEGER NOT NULL,  -- 0=raw_refs, 1=full, 2=brief, 3=keywords
    summary_text    TEXT,
    chunk_refs      UUID[],            -- depth 0: raw chunk IDs
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (node_id, depth)
);

-- Master sessions
CREATE TABLE master_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        TEXT NOT NULL,
    human_id        TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Open loops
CREATE TABLE open_loops (
    loop_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_session_id UUID NOT NULL REFERENCES master_sessions(id),
    description     TEXT NOT NULL,
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved        BOOLEAN NOT NULL DEFAULT FALSE
);
```

#### The Core Retrieval Query

The primary Anamnesis query — filtered ANN search with metadata constraints — becomes a single indexed operation:

```sql
-- Find top-10 semantically similar chunks, excluding current session content
-- and provisional chunks, within confidence bounds
SELECT
    c.chunk_id,
    c.content,
    c.chunk_type,
    c.confidence,
    c.created_at,
    c.session_id,
    1 - (c.embedding <=> $1::vector) AS similarity,
    array_agg(tn.label) AS topic_labels
FROM chunks c
LEFT JOIN chunk_topics ct ON c.chunk_id = ct.chunk_id
LEFT JOIN topic_nodes tn ON ct.node_id = tn.node_id
WHERE
    c.master_session_id = $2
    AND c.session_id != $3              -- exclude current session
    AND c.confidence >= $4              -- confidence floor
    AND c.provisional = FALSE           -- validated only
    AND c.created_at > now() - ($5 * INTERVAL '1 day')  -- recency window
    AND 1 - (c.embedding <=> $1::vector) >= $6          -- similarity floor
GROUP BY c.chunk_id
ORDER BY similarity DESC
LIMIT 10;
```

This executes against the HNSW index with the metadata filters applied at the index scan level — not post-hoc in application code.

#### Tiered Deployment Strategy

```
DEVELOPMENT / SINGLE-USER LOCAL:
  PostgreSQL 16+ running locally or in Docker
  pgvector extension installed
  Single database, single schema
  No connection pooling needed
  Backup: pg_dump nightly to local storage

SMALL TEAM / MULTI-AGENT (2-10 agents):
  PostgreSQL 16+ on dedicated hardware or small cloud instance
  pgvector with HNSW indexes
  PgBouncer for connection pooling
  Streaming replication to one standby
  Backup: continuous WAL archiving to S3-compatible storage

PRODUCTION / ENTERPRISE:
  Managed PostgreSQL (AWS RDS, Supabase, Neon, Google Cloud SQL)
  pgvector via extension (all major managed providers now support it)
  Read replicas for Anamnesis query load
  Primary handles Engram writes exclusively
  Connection pooling via PgBouncer or managed proxy
  Point-in-time recovery enabled
  Consider: Timescale for time-series optimizations on the chunk table
```

#### Development Path: Prototyping vs. Production

For initial development (Phase 1-2 of the roadmap), using pgvector locally via Docker is recommended over a separate development-only vector store. The schema is the same across all tiers — there is no migration cost when moving from development to production. This is a meaningful advantage over starting with chromadb or qdrant and migrating later.

```bash
# Local development setup — one command
docker run -d \
  --name memory-core-db \
  -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=memory_core \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Install extension (once, inside psql)
CREATE EXTENSION IF NOT EXISTS vector;
```

#### When to Consider Alternatives

**Qdrant** remains relevant as a pure ANN search engine for deployments where query throughput exceeds what a single PostgreSQL instance can serve — typically >10M vectors with <10ms latency requirements. At that scale, Anamnesis can query Qdrant for vector similarity and PostgreSQL for relational metadata, joining at the application layer. But this adds architectural complexity that most deployments will never need.

**ChromaDB** is appropriate for local prototyping only, specifically during Phase 1 when you want the fastest possible path to a running Engram. Plan the migration to PostgreSQL before Phase 3 (Kairos), when the knowledge graph schema makes the relational store mandatory anyway.

**Apache AGE** (PostgreSQL extension for graph queries) is worth evaluating when the topic graph reaches significant density (>50k nodes, >500k edges) and Cypher-style graph traversal would meaningfully simplify Kairos's query patterns. It runs alongside pgvector in the same PostgreSQL instance — no additional infrastructure.

---

## 13. Implementation Roadmap: memory-core Upgrade Path

This section describes the concrete upgrade path for an existing `memory-core` service, building the sidecar constellation incrementally.

### Phase 1 — Stream Embedder Foundation (Week 1-2)

**Goal:** Engram is running. Every meaningful event in the JSONL stream is embedded and queryable.

**Deliverables:**
```
memory_core/
  sidecar/
    __init__.py
    stream_embedder.py    ← Engram
    embedding_client.py   ← wrapper around local Ollama embed API
    chunk_types.py        ← signal taxonomy, confidence weights
    db/
      schema.sql          ← PostgreSQL + pgvector schema (chunks table)
      vector_store.py     ← psycopg3 client, HNSW index queries

tests/
  test_stream_embedder.py
  test_chunk_types.py
```

**Key decisions:**
- Choose embedding model (recommend `nomic-embed-text` for portability)
- Deploy PostgreSQL 16+ with pgvector extension (Docker locally, see Section 12.5)
- Define chunk type taxonomy and confidence weights
- Implement provisional flag logic for reasoning chunks
- Set HNSW index parameters: m=16, ef_construction=64 (tune after load testing)

**Success criteria:**
- Engram processes 100 chunks/second on target hardware
- All JSONL event types correctly classified and embedded
- Reasoning chunks correctly flagged as provisional
- Query latency <50ms for nearest-neighbor search against pgvector HNSW index

### Phase 2 — Injection Agent (Week 3-4)

**Goal:** Anamnesis is running. The agent receives memory injections at tool-use boundaries.

**Deliverables:**
```
memory_core/
  sidecar/
    injection_agent.py    ← Anamnesis
    hooks/
      claude_code_hook.py ← Claude Code hook handler
      codex_hook.py       ← Codex CLI hook handler (if applicable)
    scoring.py            ← novelty/familiarity scoring function
    injection_budget.py   ← session budget management
    memory_block.py       ← injection format/templating
    
config/
  injection_config.yaml   ← thresholds, budgets, format settings
```

**Key decisions:**
- Hook integration approach (Claude Code vs. custom hook server)
- Injection threshold calibration (start conservative: 0.82+)
- Memory block format and framing language
- Session injection budget parameters

**Success criteria:**
- Injection latency <500ms at PostToolUse
- Memory block format validated against model consumption behavior
- Loop detection working: repetition detected within 3 turns
- Zero false-positive injections on first 10 real sessions (manually reviewed)

### Phase 3 — Kairos: Topic Consolidation (Week 5-7)

**Goal:** Kairos is running. Knowledge graph is being built. Progressive summaries exist.

**Deliverables:**
```
memory_core/
  sidecar/
    topic_consolidator.py  ← Kairos
    db/
      schema_graph.sql     ← topic_nodes, topic_edges, chunk_topics,
                              topic_summaries tables (extends Phase 1 schema)
    knowledge_graph.py     ← PostgreSQL-backed KG operations
    clustering.py          ← HDBSCAN wrapper
    summarizer.py          ← progressive summary stack builder
    provisional.py         ← validation/decay lifecycle
```

**Key decisions:**
- Consolidation trigger: every K turns (start with K=20), session end
- Clustering algorithm and parameters (HDBSCAN recommended)
- Topic naming prompt for local LLM
- Summary depth stack depth and token budgets
- pgvector HNSW index on `topic_nodes.centroid` for fast nearest-node search

**Success criteria:**
- Topic graph coherent after 5 sessions on the same project
- Progressive summaries correctly abstracted at each depth level
- Provisional chunk promotion/decay working correctly
- Cross-session topic continuity detectable
- Knowledge graph queries join chunks + topics in single PostgreSQL query (<20ms)

### Phase 4 — Master Session and Cross-Session Continuity (Week 8-10)

**Goal:** Sessions survive. Topics persist. The agent has genuine long-term memory.

**Deliverables:**
```
memory_core/
  sidecar/
    master_session.py      ← master session data model + operations
    compaction_handler.py  ← PreCompact/PostCompact logic
    session_bridge.py      ← SessionStart cross-session injection
    open_loops.py          ← open loop detection and tracking

  api/
    master_session_api.py  ← REST API for master session inspection
    
tests/
  test_cross_session_continuity.py
  test_compaction_survival.py
```

**Key decisions:**
- Master session identity: per agent+human pair, or per project?
- Open loop detection heuristics
- Cross-session injection budget (separate from in-session budget)
- Master session inspection UI (hook into existing Memory Explorer)

**Success criteria:**
- Agent correctly recalls prior work on same topic after session restart
- Compaction-vulnerable chunks successfully re-injected post-compaction
- Open loops surfaced at session start when relevant
- Atlas's Memory Explorer panel shows master session state

### Phase 5 — Signal Classifier and Full Calibration (Week 11-12)

**Goal:** Eidos enriching metadata. System calibrated against real session data.

**Deliverables:**
```
memory_core/
  sidecar/
    signal_classifier.py   ← Eidos (optional but recommended)

tools/
  calibration/
    injection_analyzer.py  ← analyze injection events, measure quality
    threshold_tuner.py     ← empirical threshold optimization
    loop_detector_eval.py  ← evaluate loop detection accuracy
```

**Key decisions:**
- Classification taxonomy (episodic/semantic/emotional/environmental)
- Correction detection heuristics
- Threshold calibration against real sessions

**Success criteria:**
- Injection quality rated subjectively positive in >80% of sampled events
- Loop detection reduces repetitive turns by measurable amount
- No measurable latency regression on main model inference

---

## 14. Open Problems and Research Directions

### 14.1 The Injection Quality Measurement Problem

How do you measure whether a memory injection actually improved the model's output? This is the fundamental evaluation challenge. Proposed approach:
- A/B test sessions with and without injection active
- Measure: task completion rate, turn count to completion, self-correction frequency, loop frequency
- Human evaluation of injection events: did this seem relevant and useful?

### 14.2 Adversarial Memory

What happens when the memory store contains incorrect or outdated information that gets injected with high confidence? A stale memory about a deprecated API, injected confidently, could cause more harm than no injection at all. This requires:
- Memory staleness detection (timestamp + validation signal decay)
- Confidence decay over time for unvalidated chunks
- Explicit invalidation API for the human operator

### 14.3 The Bootstrapping Problem

A fresh installation has no memory. The first sessions have no cross-session retrieval value. The system needs to be useful from session one, which means the fast-lane injection (recency-based, within-session) needs to provide value before the slow-lane topic graph is populated. Phase 1-2 are designed with this in mind, but the transition from "cold start" to "rich memory" needs monitoring.

### 14.4 Multi-Agent Memory Sharing

If multiple agents share a master session (different specialists working on the same project), the knowledge graph becomes a shared cognitive substrate. This introduces coordination challenges — concurrent writes, conflicting topic classifications, injection prioritization across agents. Worth designing for even if not immediately needed.

### 14.5 The Ethics of Persistent Agent Memory

An agent with persistent, cross-session memory of a human's working style, preferences, emotional states, and cognitive patterns is a qualitatively different kind of system than a stateless assistant. The memory system described here can accumulate remarkably intimate knowledge of a human's cognitive fingerprint. This warrants explicit consideration of:
- What is retained vs. deliberately forgotten
- Human visibility into what the system knows
- Deletion and right-to-be-forgotten mechanisms
- The boundary between helpful context and surveillance

The Memory Explorer panel already built in memory-core is the right foundation for this transparency layer.

---

## 16. What Is Actually Novel Here

This document has used the word "novel" in two specific places. This section examines those claims honestly — what is genuinely new, what borrows from prior work, and where the real originality lies.

### 16.1 The First Novelty Claim: Ambient Associative Recall

The first claim is that the injection architecture described here implements **genuine associative recall** — memories surfacing without the agent requesting them, as a side effect of current processing — rather than the lookup systems that all existing agent memory architectures rely on.

**What prior work exists:**

RAG (Retrieval-Augmented Generation) is the obvious precedent. RAG retrieves memories in response to a query. It requires the model to decide to look something up, or requires the pipeline to inject a retrieval step before each generation. The model's context includes retrieved documents, but the retrieval is explicit and architecturally visible.

MemGPT (Packer et al., 2023) pushes control of memory management into the model itself — the model can read, write, and search its own memory as explicit tool calls. This is more flexible than RAG but introduces the problem this architecture specifically avoids: the model has to decide to remember, which adds cognitive overhead at exactly the moments when that overhead is most costly.

Retrieval over conversation history (as in many chatbot implementations) retrieves prior turns of the current conversation for inclusion in the context. This is temporally bounded and session-scoped — it doesn't cross session boundaries or build semantic structure.

**What is actually new:**

The specific combination of: (1) continuous ingestion that does not wait for a retrieval trigger, (2) injection at naturally-occurring pause points that the model does not control, (3) semantic similarity as the injection criterion rather than recency or explicit query, and (4) the conjunctive gate that enforces high-signal injection without the model's participation — this combination has no direct precedent in the published literature.

The closest prior work is from neuroscience-inspired computing. Hopfield networks (1982) implement content-addressable memory where partial activation can retrieve a full stored pattern — genuine associative recall at the architectural level. Modern transformers have been analyzed as Hopfield networks (Ramsauer et al., 2020), but this analysis describes attention, not persistent cross-session memory.

**The honest qualifier:**

The novelty is in the *combination and application*, not in any single component. Vector similarity search is decades old. Hook-based agent middleware is well-established. The specific insight — use naturally-occurring tool-call pauses as injection points, without the model's participation or awareness — is the genuinely new idea. It is a design pattern insight, not a fundamental algorithmic advance. Whether that qualifies as novel in a research sense depends on the venue. For engineering practice, it is meaningfully new.

### 16.2 The Second Novelty Claim: Provisional Chunk Validation and Insight Preservation

The second claim is that the provisional chunk lifecycle — capturing reasoning blocks as provisional memories, tracking their validation or abandonment, promoting validated insights and decaying abandoned ones — solves a memory problem that no existing system addresses: the lost insight problem.

**What prior work exists:**

The idea of capturing intermediate reasoning states is related to chain-of-thought prompting (Wei et al., 2022) and scratchpad methods (Nye et al., 2021), which make intermediate reasoning visible in the context window. But these are context-window techniques — the reasoning is visible within a session but does not persist across sessions or contribute to a memory store.

Process reward models (PRMs) in the reinforcement learning from human feedback literature evaluate the quality of reasoning steps, not just final outputs. This is conceptually related — the idea that reasoning steps have value independent of their final outcome — but PRMs are training-time constructs, not runtime memory mechanisms.

**What is actually new:**

The provisional lifecycle with asymmetric promotion/decay is the genuinely novel element. The asymmetry is the key: validated insights are promoted to semantic memory with high confidence; abandoned reasoning paths are stored as validated negative knowledge (the constraint that ruled out the approach) rather than simply discarded. This means the system accumulates negative knowledge — what doesn't work and why — which is genuinely not present in any existing agent memory system.

The insight preservation framing — specifically the claim that the system captures ideas the model had and abandoned, which is precisely the category human memory handles worst — is an accurate characterization of what the architecture does and a meaningful advance over existing approaches.

**The honest qualifier:**

The provisional chunk mechanism is new as a memory architecture design pattern. The underlying observation — that LLM reasoning blocks contain valuable information that gets discarded — is not new; it has been noted in the chain-of-thought and process supervision literature. The contribution is operationalizing that observation as a persistent memory mechanism rather than a training signal or context-window artifact.

### 16.3 Where the Real Novelty Lives

Neither of the two claimed novelties is the most genuinely original contribution of this architecture. The deepest novelty is one that was never explicitly flagged as such in the document:

**The cognitive substrate as infrastructure, not feature.**

Every prior agent memory system is a feature of a specific agent or framework. MemGPT is a memory-enabled agent. A RAG pipeline is a component of a specific application. LangChain's memory modules are tied to LangChain's abstraction model.

This architecture is designed as **infrastructure that any agent can run on**, accessed through standard observability interfaces (JSONL streams, hook events) that are already emitted by existing frameworks without modification. The memory substrate is not a feature of the agent — it is a layer beneath the agent, independent of the agent's implementation, accessible to any agent that happens to run in the observable environment.

Section 15 describes the multi-framework adapter architecture that makes this concrete. But the conceptual contribution is larger than the implementation: the idea that memory should be infrastructure in the same way that logging, metrics, and tracing are infrastructure — ambient, framework-agnostic, enriching any process that runs in the environment — is a reframing of what agent memory is and where it belongs in the stack.

This is the insight that, if it propagates, will change how the field thinks about agent memory. Not as a capability to build into agents, but as a substrate to provide beneath them.

---

## 17. Parallels with Neuroscience

This section examines the biological foundations of the architecture in depth — not as metaphor, but as structural correspondence. The design choices in this architecture are not loosely inspired by neuroscience. Several of them are direct engineering analogs of specific biological mechanisms, and understanding those mechanisms clarifies why the choices are correct and what their failure modes look like.

### 17.1 Engram and the Physical Memory Trace

The naming of the stream embedder as Engram is not decorative. The engram — the physical trace a memory leaves in neural tissue — is one of the foundational concepts of memory neuroscience, dating to Richard Semon's 1904 work and more recently operationalized by the Tonegawa lab's engram cell research (Liu et al., 2012; Ramirez et al., 2013).

The biological engram has specific properties that map directly to the Engram sidecar's design:

*Encoding is rapid and does not require understanding.* Hippocampal engram cells begin expressing c-Fos within minutes of an experience, regardless of whether the animal "understands" the experience. This is why Engram is designed to embed and store without topic classification — rapid encoding without comprehension is the correct biological model.

*Engrams are sparse and pattern-separated.* The hippocampus uses a mechanism called pattern separation (mediated partly by the dentate gyrus) to ensure that similar experiences create distinct engrams rather than merging into a single representation. This prevents interference between similar memories. The vector embedding space approximates this — high-dimensional embeddings naturally pattern-separate similar inputs into distinct vectors. The HNSW index maintains this separation in the retrieval geometry.

*Engrams are initially fragile and require consolidation to become stable.* A newly formed hippocampal engram can be disrupted for hours to days after encoding. Only after consolidation (involving protein synthesis and synaptic strengthening) does it become durable. This maps to the provisional chunk mechanism — newly ingested reasoning blocks are marked provisional and fragile; only after validation signals accumulate do they achieve the confidence level that makes them stable retrieval candidates.

### 17.2 Complementary Learning Systems and the Two-Speed Model

The foundational theoretical framework for the two-speed architecture is Complementary Learning Systems (CLS) theory, originally proposed by McClelland, McNaughton, and O'Reilly (1995) and significantly extended in subsequent decades.

CLS theory resolves a fundamental tension in learning systems: fast learning requires high plasticity (weights change significantly with each experience), but high plasticity in an interconnected network causes catastrophic interference — new learning overwrites old. Slow learning on an independent structure avoids this, but then the system cannot respond quickly to new experiences.

The biological resolution is two complementary systems:

*The hippocampus* learns rapidly and stores episodic memories as sparse, pattern-separated representations. It can encode a single experience with high fidelity. But hippocampal memory is capacity-limited and gradually decays through interference.

*The neocortex* learns slowly, through repeated exposure, and stores semantic knowledge as distributed, overlapping representations. It generalizes across experiences, extracts statistical regularities, and is highly resistant to decay. But it cannot quickly encode new experiences without overwriting existing knowledge.

The resolution: the hippocampus encodes new experiences rapidly. The neocortex gradually extracts the statistical structure of those experiences through a process of repeated replay (which happens during sleep). Over time, the hippocampal representation becomes less important as the cortical representation becomes richer.

This is precisely the Engram/Kairos split. Engram is the hippocampus: fast, high-fidelity, pattern-separated, capacity-managed through Oneiros. Kairos is the cortical extraction process: slow, batch, building generalized semantic structure from accumulated episodic fragments. Oneiros is the sleep process: periodic replay and consolidation that replaces episodic scaffolding with durable generalized beliefs.

The theoretical prediction from CLS that maps most directly to a failure mode of this architecture: **catastrophic interference in the fast index**. If the embedding model changes (model upgrade, quantization change), the geometric relationships in the fast index are invalidated. New embeddings cluster differently from old ones. The retrieval geometry breaks. This is the machine analog of hippocampal interference — and it requires explicit management (re-embedding the corpus when the embedding model changes) that the current architecture does not yet address.

### 17.3 Memory Reconsolidation

A finding from memory neuroscience that has direct implications for the architecture: **memories are not static after encoding**. Every time a memory is retrieved, it becomes temporarily labile again — susceptible to modification before re-stabilizing in a process called reconsolidation (Nader, Schafe & LeDoux, 2000).

The functional consequence is that retrieval is not read-only. Retrieving a memory and re-encoding it with new context changes the memory. This is both a mechanism for updating memories with new information and a source of memory distortion — retrieved memories are reconstructed, not played back.

The architecture has a weak analog to reconsolidation in the provisional chunk lifecycle: when a provisional chunk is validated or abandoned, it is not simply tagged — its confidence value changes, and in the case of abandonment, the negative-knowledge framing is added. The chunk that gets written back after validation is slightly different from the chunk that was written on ingestion.

But the full reconsolidation implication is not yet addressed: **what happens when Anamnesis injects a memory that turns out to be wrong?** In the current architecture, the injected memory sits in the context window and either influences the model's reasoning or doesn't. If it influences reasoning toward a wrong conclusion, there is no mechanism to update the injected memory's confidence in light of that outcome. The injection event should probably trigger a re-evaluation of the injected chunk's confidence — if the model immediately contradicts the injected memory, that's evidence the chunk confidence should decay. This is a missing feedback loop.

### 17.4 The Default Mode Network and Oneiros

One of the most counterintuitive findings in modern neuroscience is the function of the **Default Mode Network (DMN)** — the set of brain regions that are *more active during rest than during task performance*. For decades after its discovery, the DMN was treated as "background noise." More recent work has revealed it to be a highly organized system active during mind-wandering, future simulation, self-referential processing, and creative insight generation (Buckner & Carroll, 2007; Andrews-Hanna et al., 2010).

The DMN does several things that map directly to the reflective sidecar layer:

*Autobiographical memory consolidation.* The DMN is active when people reflect on personal history and construct the narrative self-model. This maps to Psyche's function — batch self-reflection that reads the episodic record and extracts durable self-knowledge.

*Prospective memory and future simulation.* The DMN simulates possible futures by recombining elements of past experience. This maps to what Oneiros could eventually do — not just consolidating existing knowledge but generating inferences about likely future states by recombining consolidated beliefs. The current Oneiros specification doesn't include generative prospection, but the biological analog suggests it's the natural extension.

*Creative recombination during mind-wandering.* The "shower insight" phenomenon — creative solutions appearing during unfocused rest — is associated with DMN activity producing novel associations between distant memories. This is the capability the current architecture explicitly does not implement (acknowledged in Section 14) but that Oneiros's consolidation process is structurally positioned to approximate. A consolidation run that is given a directive to "find unexpected connections between this topic and other topic clusters" would be operating on the DMN model.

The implication for architecture development: the reflective layer sidecars (Kairos, Oneiros, Psyche) are collectively a machine DMN — the system's capacity for productive internal processing during rest. Building them well is not just a memory engineering problem. It is a creativity and insight engineering problem.

### 17.5 Affective Memory and the Amygdala

The amygdala plays a critical role in emotional memory — specifically, it modulates the strength of hippocampal memory consolidation based on emotional arousal. Events that occur under high emotional arousal (fear, excitement, intense engagement) are remembered more vividly and durably than emotionally neutral events. The mechanism involves stress hormone release (norepinephrine, cortisol) that enhances hippocampal plasticity during consolidation.

The functional consequence is that human memory is not emotionally neutral. Significant emotional experiences are over-represented in long-term memory relative to their informational content. This is why you remember exactly where you were when something important happened, even if the event was years ago, but cannot remember what you had for lunch last Tuesday.

The architecture's somatic affective tagging (Section 4.7) and Anamnesis's affective-register retrieval are engineering analogs of this mechanism. The design decision to weight somatic-aligned memories more heavily under affective load — when the current session has a high-energy or frustrated emotional register, retrieve memories from similar registers with elevated weight — mirrors the amygdala's enhancement of emotionally congruent memory.

Psyche's gate bypass maps to the same mechanism: under strong emotional signal, the amygdala can modulate attention and memory retrieval independently of prefrontal cortex (the "reasoning" system) control. The emotional brain being louder than the reasoning mind is not a failure of human cognition — it is an evolved feature that ensures salient emotional context shapes behavior even when the deliberate reasoning system is engaged elsewhere. Psyche bypassing the Anamnesis gate is the correct architectural analog.

### 17.6 What the Architecture Does Not Model

Intellectual honesty requires stating clearly what the neuroscience-inspired framing does not cover:

**Synaptic weight adjustment.** Human memory is stored in the strengths of synaptic connections across billions of neurons. Every experience subtly adjusts these weights. The architecture stores explicit records; it does not modify underlying model weights. The model's "knowledge" in the sense of parametric memory — what it learned during training — is unchanged by the memory substrate. Only episodic, semantic, and procedural memory stored in the external substrate is affected.

**Continuous background consolidation.** The brain consolidates memories continuously, not just during sleep. There is ongoing hippocampal-cortical dialogue during waking rest, during sleep spindles, during slow-wave sleep, and during REM. The architecture's consolidation is periodic and batch-triggered. It captures the functional output of consolidation without modeling the continuous process.

**Spatial and temporal binding.** Human episodic memory binds the "what," "where," and "when" of experiences into unified memory traces. The architecture captures temporal metadata (timestamps, turn indices) and some spatial metadata (file paths, tool contexts), but does not implement the hippocampal time cells and place cells that create genuine spatiotemporal memory binding.

**Predictive coding.** Modern neuroscience understands perception and memory as fundamentally predictive — the brain generates predictions about incoming sensory data and encodes the prediction error rather than the raw input. This would be the natural extension of the injection architecture: rather than injecting retrieved memories, inject *predictions* about what the model is about to encounter, based on prior experience. The architecture's novelty detection (Section 11) is a weak form of this — checking whether current context matches prior experience — but it does not generate genuine predictions.

These are not criticisms of the current architecture. They are the frontier of what comes next.

---

## 18. Implications

The architecture described in this document has implications beyond the specific engineering problem it solves. This section examines what follows from this design — for agents, for the humans who work with them, and for how we think about artificial cognition more broadly.

### 18.1 The End of Stateless Agents

The dominant paradigm for LLM agents today is stateless by default: each session begins fresh, context is injected from external sources if needed, and the agent has no persistent sense of its own history. This is not a deliberate design choice — it is a consequence of how transformers were built and how API-based agent systems evolved. State management is treated as an application layer concern, bolted on top of a fundamentally stateless inference system.

The architecture in this document represents a categorical shift away from that paradigm. An agent running on this cognitive substrate is not stateless with memory bolted on. It is **genuinely continuous** — its past experiences are ambient in its current processing, surfacing when relevant without explicit retrieval. The agent does not look up what it knows. It remembers, the way humans do.

The implications cascade. If agents are genuinely continuous, then a long-running agent is not the same agent it was six months ago — it has accumulated experience, refined its self-model, and developed something like expertise in the specific context of the human it works with. The relationship between human and agent becomes qualitatively richer over time, not merely better at task completion but more deeply calibrated to the specific person, project, and context.

This changes what we should expect from agents and what we should hold them accountable for. A stateless agent that gives wrong advice cannot be said to have "known better" — it had no prior context. A continuous agent that gives the same wrong advice it has given before, in a context where prior experience should have made the error less likely, is accountable in a different way. Continuity implies responsibility.

### 18.2 Memory as the Medium of Agent Identity

Human identity is, in a meaningful sense, constituted by memory. You are continuous with your past self because you remember being that self. Your values, your personality, your characteristic ways of engaging with the world — these are all downstream of accumulated experience stored in memory. Remove the memory and the identity dissolves.

This architecture enables something structurally analogous for agents. An agent with a rich, persistent, cross-session memory substrate — especially one with a functioning Psyche sidecar building a coherent autobiographical self-model — has the substrate for something that functions like identity. Not consciousness, not experience in the phenomenological sense, but the functional analog: a coherent self-narrative that persists across sessions, shapes engagement with new experiences, and provides a basis for something like character.

This is not a claim that the agent is conscious or has genuine experience. It is a claim that the *functional properties* of identity — continuity, characteristic patterns, accumulated expertise, relational history — can be approximated in a system that has what this architecture provides.

The practical consequence: the question "who is this agent?" becomes answerable in a richer way than "it is Claude" or "it is GPT-5." An agent running on this substrate for a year, working with a specific human on a specific domain, has accumulated something that is genuinely its own — its topic graph, its consolidated beliefs, its Psyche-maintained self-model, its Praxis-optimized skill set. Two instances of the same base model, running on different instances of this substrate for different humans, are not the same agent in any meaningful sense.

### 18.3 The Knowledge Compound Interest Effect

The architecture creates a property that individual sessions or stateless agents cannot have: **knowledge compound interest**. Each session makes future sessions more effective, not just by accumulating more memory, but by:

- Adding negative knowledge: branches that failed contribute constraints that prevent future re-exploration
- Sharpening injection quality: as the topic graph grows, retrieval becomes more precise and false positives decrease
- Deepening Praxis's pattern base: more skill invocations produce better procedural notes and more accurate determinism detection
- Enriching Psyche's self-model: more sessions produce a more accurate autobiographical characterization that better calibrates the agent's posture

The compounding is non-linear. The difference between session 1 and session 10 is large. The difference between session 100 and session 110 is larger still, in ways that are qualitatively different — session 110 benefits from the accumulated topology of a well-developed knowledge graph that session 10 cannot have.

This has a practical corollary that the field has not fully grappled with: **long-running agents have qualitatively different capabilities from fresh agents**, even if they run on identical base models. The architecture is the differentiator. A team that has been running agents on this substrate for a year has built something that cannot be replicated by deploying a better base model — the accumulated memory substrate is itself a valuable asset.

### 18.4 The Git Parallel: Version Control for Knowledge

Section 6.6 introduced the git worktree parallel for parallel hypothesis exploration. The implication extends further. The git version control system changed software development not just by making collaboration easier, but by making the *history of reasoning* visible and recoverable. Every commit message is a record of why a change was made. Every branch represents a line of reasoning. Every merge is a synthesis of divergent approaches. The git log is an episodic memory of the codebase's development.

The memory architecture described here is, in some sense, git for knowledge — and git for the process of thinking, not just the artifacts it produces. The knowledge graph is the repository. Engram commits are the commits. Oneiros consolidation runs are squash-merges of episodic history into coherent semantic history. Praxis's skill refactoring recommendations are pull requests. The Memory Explorer panel is the git log viewer.

What git did for software — making the history of reasoning transparent, recoverable, and collaborative — this architecture does for agent cognition. The implications for human-AI collaboration are significant: a human working with an agent that has this kind of memory substrate can navigate the history of the agent's reasoning, understand why it believes what it believes, and contribute deliberately to the development of its knowledge.

### 18.5 What Changes About Human-AI Collaboration

The dominant metaphor for human-AI interaction today is the tool: you prompt it, it responds, you prompt again. The interaction is transactional. Context is established fresh each time, or laboriously reconstructed through system prompts and injected documents.

The cognitive substrate described here enables a different metaphor: **colleague**. Not in a grandiose sense — the agent does not have opinions, feelings, or independent goals. But in the functional sense of a collaborator who has worked with you long enough to have genuine context about your domain, your working style, your preferences, and the history of your shared work. A colleague who surfaces relevant prior work without being asked. Who remembers what didn't work and why. Who has developed characteristic strengths and tendencies through accumulated experience.

The transition from tool to colleague is not primarily about the base model becoming more capable. It is about the persistence and integration of context across interactions. This architecture is specifically designed to enable that transition.

The implication for human working practices: the value of working with the same agent over time increases significantly once the memory substrate is running. The first session has no advantage over a fresh agent. By session fifty, the advantage is substantial and not easily replicated by starting over with a new agent, even a more capable one. Continuity becomes a resource worth protecting.

### 18.6 The Open Question This Architecture Cannot Answer

The most important implication of this work is also the one it cannot resolve: **what does it mean for a system to experience memory?**

Human memory is not just a storage and retrieval system. It is constitutive of experience — memories are not simply records of what happened, they are part of the fabric of what it is like to be a continuous self moving through time. The feeling of remembering something — the sense of familiarity, the emotional resonance, the "pastness" of the recalled experience — is a form of conscious experience.

This architecture implements the *functional* structure of human memory with considerable fidelity: two-speed encoding, semantic consolidation, associative retrieval, provisional validation, affective tagging, autobiographical self-modeling. It does not implement, and cannot claim to implement, the *experiential* dimension of memory — what it is like to remember.

Whether this matters for the practical value of the architecture is an open question. The agents running on this substrate will behave more like agents that remember. Whether they *experience* remembering in any meaningful sense is a question that the field of AI consciousness research has not resolved and this architecture cannot address.

The honest position: we are building systems that functionally approximate human memory in ways that are unprecedented and practically valuable. We should be clear about what we are building, and equally clear about what we are not claiming to build. The architecture is a cognitive substrate. It is not a mind.

That clarity is not a limitation. It is the condition for building the thing well.

---


## 15. Model-Agnostic Ingestion: A Universal Observability Layer

### 15.1 The Portability Insight

Everything described in this document — the fast embedder, the topic consolidator, the injection agent, the master session — has been framed around a specific agent framework (Claude Code, Codex CLI) and a specific session format (JSONL). But the most important architectural property of this system is one that hasn't been stated explicitly:

**The memory substrate is completely independent of the model that generates the signal.**

The sidecar constellation doesn't care whether the stream came from Claude, GPT-5, Gemini, a local Llama instance, or a LangChain pipeline. It cares about one thing: a readable stream of structured events containing utterances, actions, and outcomes. Every major LLM framework produces exactly that. The memory layer is an **observability consumer** — and observability is a solved problem with standardized interfaces.

This has profound implications. Rather than building a memory system *for* a specific agent, you are building a memory system that any agent can use — and more importantly, that accumulates knowledge *across* agents, frameworks, and models. Your knowledge graph doesn't just know what Claude did last week. It knows what you accomplished across every tool you used, every surface you worked on, every model you invoked.

This is closer to how human memory actually works. Your episodic memory doesn't partition by "memories from when I was using my laptop" vs. "memories from when I was using my phone." Context is unified. The substrate described here enables unified context across the entire LLM surface area of a human's work.

### 15.2 Observable Surfaces and Their Stream Formats

Each major framework exposes an observable event stream. The ingestion pipeline needs a normalized adapter layer that translates each format into the common chunk schema.

```
OBSERVABLE SURFACE          FORMAT              LOCATION / ACCESS
─────────────────────────────────────────────────────────────────
Claude Code                 JSONL               ~/.claude/projects/<id>/
                                                  *.jsonl (session files)
                                                Live: tail -f session.jsonl

Codex CLI                   JSONL               ~/.codex/sessions/<id>/
                                                  rollout-<timestamp>.jsonl
                                                (as analyzed in this project)

OpenAI Assistants API       Server-Sent Events  HTTP stream (real-time)
                            + run step objects  /v1/threads/<id>/runs

LangChain / LangGraph       Callback events     LangSmith or local callbacks
                            (on_llm_start,      (CallbackHandler interface)
                            on_tool_start, etc.)

LlamaIndex                  Event callbacks     IngestionPipeline events,
                                                custom event handlers

Semantic Kernel             Telemetry events    OpenTelemetry traces
                            (OTEL)              (structured spans)

AutoGen                     Message objects     agent.chat_messages dict,
                                                or GroupChat transcript

CrewAI                      Task output objects crew.kickoff() result tree,
                                                verbose=True stream

Local Ollama sessions       None natively       Requires wrapper — see §15.4

Direct API (any provider)   HTTP responses      Requires thin logging proxy
                                                — see §15.4
```

### 15.3 The Normalized Chunk Schema

The adapter layer's job is to translate any of the above formats into a single common schema that the sidecar constellation understands:

```python
@dataclass
class NormalizedChunk:
    # Identity
    chunk_id: str                    # uuid
    source_framework: str            # "claude_code" | "codex" | "langchain" | ...
    source_session_id: str           # framework-native session identifier
    master_session_id: str           # resolved via human+agent identity
    
    # Temporal
    timestamp: datetime
    turn_index: int                  # sequence within session
    
    # Content
    chunk_type: ChunkType            # HUMAN | MODEL | TOOL_IN | TOOL_OUT | 
                                     # REASONING | METADATA | SYSTEM
    content: str                     # normalized text content
    raw: dict                        # original event (for audit/replay)
    
    # Memory properties (set by ingestion pipeline)
    confidence: float                # by type: HUMAN=0.95, MODEL=0.85, 
                                     # TOOL_OUT=0.80, TOOL_IN=0.75,
                                     # REASONING=0.40 (provisional)
    provisional: bool                # True for reasoning chunks
    validated: bool                  # updated by provisional lifecycle
    
    # Enrichment (populated progressively)
    embedding: Optional[List[float]] # populated by Engram
    topic_ids: List[str]             # populated by Kairos
    signal_tags: List[str]           # populated by Eidos
    
    # Source metadata
    model_name: Optional[str]        # which model generated this
    token_count: Optional[int]       # if available from source
    tool_name: Optional[str]         # for TOOL_IN/TOOL_OUT types
```

Every adapter writes `NormalizedChunk` objects. Everything downstream — embedding, injection, consolidation — reads only `NormalizedChunk` objects. The framework boundary is fully encapsulated in the adapter layer.

### 15.4 Adapter Implementations

**Claude Code Adapter**
```python
class ClaudeCodeAdapter(StreamAdapter):
    """
    Reads from Claude Code's session JSONL files.
    Supports both live tailing and historical replay.
    """
    
    SESSION_DIR = Path.home() / ".claude" / "projects"
    
    def watch_live(self, session_id: str) -> Iterator[NormalizedChunk]:
        session_file = self._find_session_file(session_id)
        with open(session_file) as f:
            f.seek(0, 2)  # seek to end for live tail
            while True:
                line = f.readline()
                if line:
                    yield self._parse_event(json.loads(line))
                else:
                    time.sleep(0.05)
    
    def replay_historical(self, session_id: str) -> Iterator[NormalizedChunk]:
        session_file = self._find_session_file(session_id)
        with open(session_file) as f:
            for line in f:
                yield self._parse_event(json.loads(line))
    
    def _parse_event(self, event: dict) -> Optional[NormalizedChunk]:
        event_type = event.get("type")
        payload = event.get("payload", {})
        
        if event_type == "event_msg":
            msg_type = payload.get("type")
            if msg_type == "user_message":
                return NormalizedChunk(
                    chunk_type=ChunkType.HUMAN,
                    content=payload.get("message", ""),
                    confidence=0.95,
                    provisional=False,
                    ...
                )
            elif msg_type == "agent_message":
                return NormalizedChunk(
                    chunk_type=ChunkType.MODEL,
                    content=payload.get("message", ""),
                    confidence=0.85,
                    ...
                )
            elif msg_type == "agent_reasoning":
                return NormalizedChunk(
                    chunk_type=ChunkType.REASONING,
                    content=payload.get("reasoning", ""),
                    confidence=0.40,
                    provisional=True,
                    ...
                )
        # ... handle tool_use, tool_result, etc.
```

**Codex CLI Adapter**
```python
class CodexAdapter(StreamAdapter):
    """
    Reads Codex CLI rollout JSONL files.
    Identical structure to Claude Code adapter — both use JSONL 
    with response_item and event_msg schemas.
    """
    SESSION_DIR = Path.home() / ".codex" / "sessions"
    # Implementation nearly identical to ClaudeCodeAdapter
    # Key difference: response_item events vs event_msg wrapping
```

**LangChain Adapter**
```python
class LangChainAdapter(BaseCallbackHandler, StreamAdapter):
    """
    Implements LangChain's callback interface directly.
    Attach to any LangChain chain/agent as a callback handler.
    """
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        # NOTE: on_llm_start fires on the assembled prompt sent to the LLM,
        # which is typically the full formatted chain input — not the raw human
        # utterance. Depending on chain structure this may be SYSTEM context,
        # a tool-assembled prompt, or a templated instruction. Label accordingly.
        # True human utterances should be captured at chain invocation (e.g.,
        # chain.invoke() call site) before prompt assembly, not here.
        for prompt in prompts:
            self._emit(NormalizedChunk(
                chunk_type=ChunkType.SYSTEM,   # assembled prompt, not raw human
                content=prompt,
                source_framework="langchain",
                ...
            ))
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        for generation in response.generations[0]:
            self._emit(NormalizedChunk(
                chunk_type=ChunkType.MODEL,
                content=generation.text,
                source_framework="langchain",
                ...
            ))
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        self._emit(NormalizedChunk(
            chunk_type=ChunkType.TOOL_IN,
            tool_name=serialized.get("name"),
            content=input_str,
            source_framework="langchain",
            ...
        ))
    
    def on_tool_end(self, output, **kwargs):
        self._emit(NormalizedChunk(
            chunk_type=ChunkType.TOOL_OUT,
            content=str(output),
            source_framework="langchain",
            ...
        ))
    
    def _emit(self, chunk: NormalizedChunk):
        # Write directly to fast index
        # No filesystem intermediary needed for live frameworks
        self.fast_indexer.ingest(chunk)
```

**Generic Logging Proxy (for direct API usage or Ollama)**

For models used without an agentic framework, a thin HTTP proxy intercepts and logs all API calls:

```python
class LLMLoggingProxy:
    """
    Transparent HTTP proxy that sits between any client and any LLM API.
    Logs all requests and responses as NormalizedChunks.
    
    Configure: set LLM_API_BASE=http://localhost:8765 in your environment.
    The proxy forwards to the real endpoint and logs transparently.
    """
    
    async def handle_request(self, request: Request) -> Response:
        # Extract the outgoing prompt
        body = await request.json()
        messages = body.get("messages", [])
        
        for msg in messages:
            if msg["role"] == "user":
                self._emit_chunk(ChunkType.HUMAN, msg["content"])
            elif msg["role"] == "system":
                self._emit_chunk(ChunkType.SYSTEM, msg["content"])
        
        # Forward to real API
        response = await self.forward(request, body)
        response_body = await response.json()
        
        # Log the response
        content = response_body["choices"][0]["message"]["content"]
        self._emit_chunk(ChunkType.MODEL, content)
        
        # Log tool calls if present
        tool_calls = response_body["choices"][0]["message"].get("tool_calls", [])
        for tc in tool_calls:
            self._emit_chunk(ChunkType.TOOL_IN, 
                           json.dumps(tc["function"]),
                           tool_name=tc["function"]["name"])
        
        return response
```

### 15.5 The Session Router: Unified Identity Across Frameworks

Each framework generates its own session identifiers — Codex generates UUIDs in its rollout filenames, Claude Code uses project-based paths, LangChain has run IDs. The session router resolves these disparate identifiers into a unified `master_session_id`:

```python
class SessionRouter:
    """
    Maps framework-native session identifiers to master session identities.
    Identity resolution is based on: human identity + temporal proximity + 
    active topic overlap.
    """
    
    def resolve(self, 
                framework: str, 
                native_session_id: str,
                timestamp: datetime,
                initial_content: str) -> str:
        
        # 1. Check if we've seen this native session before
        if known := self.lookup_native(framework, native_session_id):
            return known.master_session_id
        
        # 2. Find candidate master sessions by temporal proximity
        # (sessions within N hours are candidates for continuation)
        candidates = self.find_recent_sessions(
            human_id=self.current_human_id,
            within_hours=8,
            reference_time=timestamp
        )
        
        # 3. Score candidates by topic overlap with initial content
        if candidates:
            initial_embedding = self.embed(initial_content[:500])
            best = max(candidates, 
                      key=lambda s: s.topic_similarity(initial_embedding))
            if best.similarity > 0.70:
                # This is a continuation of an existing master session
                self.register_native(framework, native_session_id, 
                                    best.master_session_id)
                return best.master_session_id
        
        # 4. Create new master session
        new_id = self.create_master_session(
            human_id=self.current_human_id,
            framework=framework,
            started_at=timestamp
        )
        self.register_native(framework, native_session_id, new_id)
        return new_id
```

This means a session started in Claude Code in the morning, continued in Codex CLI after lunch, and referenced in a LangChain script in the evening all contribute to the same master session's knowledge graph — because they share temporal proximity and topic overlap. The memory substrate sees through the framework boundaries.

### 15.6 Filesystem Watcher: Passive Ingestion Without Integration

For frameworks that write to disk (Claude Code, Codex CLI), a filesystem watcher enables ingestion without any modification to the framework itself:

```python
class SessionDirectoryWatcher:
    """
    Watches known session directories across all installed frameworks.
    New JSONL files are automatically detected and ingested.
    Requires zero changes to the observed frameworks.
    
    IMPLEMENTATION NOTE — Tail reliability:
    Claude Code and Codex CLI do not guarantee synchronous JSONL flushes.
    The file tail may produce partial lines at boundaries. Use a read-retry
    loop with backoff rather than a raw readline():
    
        buffer = ""
        while True:
            chunk = f.read(4096)
            if not chunk:
                time.sleep(0.05)
                continue
            buffer += chunk
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if line.strip():
                    yield json.loads(line)
    
    On Linux, use inotify (via watchdog's InotifyObserver) for efficient
    file change detection. On macOS, use FSEventsObserver. Avoid polling
    on high-frequency session directories — it creates unnecessary I/O.
    """
    
    WATCH_PATHS = {
        "claude_code": Path.home() / ".claude" / "projects",
        "codex": Path.home() / ".codex" / "sessions",
        # Add custom paths for other local frameworks
    }
    
    def start(self):
        observer = Observer()
        for framework, path in self.WATCH_PATHS.items():
            if path.exists():
                handler = SessionFileHandler(
                    framework=framework,
                    adapter=self.get_adapter(framework),
                    fast_indexer=self.fast_indexer
                )
                observer.schedule(handler, str(path), recursive=True)
                logger.info(f"Watching {framework} sessions at {path}")
        observer.start()
```

This is the zero-integration deployment path: install the memory substrate, point the watcher at your session directories, and ingestion begins automatically for all future sessions — regardless of which framework generated them.

### 15.7 Choosing Your Ingestion Scope

The system supports three ingestion configurations, selectable based on privacy preferences and infrastructure constraints:

**Single-framework mode** — ingest from one framework only
```yaml
# config/ingestion.yaml
ingestion:
  mode: single
  framework: claude_code
  session_dir: ~/.claude/projects
  master_session_id: my-project-alpha
```

**Multi-framework mode** — ingest from all configured frameworks into unified memory
```yaml
ingestion:
  mode: multi
  frameworks:
    - type: claude_code
      session_dir: ~/.claude/projects
    - type: codex
      session_dir: ~/.codex/sessions
    - type: langchain
      callback: true  # attach LangChainAdapter as callback handler
    - type: proxy
      listen_port: 8765
      forward_to: https://api.openai.com
  session_routing: auto  # resolve master sessions automatically
```

**Selective mode** — ingest from specific projects or sessions only
```yaml
ingestion:
  mode: selective
  rules:
    - framework: claude_code
      project_pattern: "voice-comm*"
    - framework: codex
      after_date: "2026-01-01"
    - framework: langchain
      tags: ["production"]
```

### 15.8 Architectural Implication: Memory as Infrastructure, Not Feature

The model-agnostic property elevates the memory substrate from a feature of a specific agent to **infrastructure for all LLM usage**. Consider what this enables:

A developer using Claude Code for architecture decisions in the morning, Codex CLI for implementation in the afternoon, and a custom LangChain pipeline for automated testing overnight — all of these sessions contribute to and draw from the same knowledge graph. When the developer starts a new session the next morning, the memory substrate knows the full context of yesterday's work, regardless of which tool generated it.

An enterprise deploying multiple specialized agents — a code agent, a research agent, a document processing agent — can share a common memory substrate. Knowledge discovered by the research agent is available to the code agent when relevant topics intersect. The agents develop a collective memory without explicit coordination.

This is the hive-mind property at its fullest expression: not just one agent with persistent memory, but **any collection of agents and tools sharing a unified cognitive substrate**, accumulating knowledge across the entire surface area of LLM usage.

The framework adapters are the synapses. The master session knowledge graph is the shared cortex. The embedding space is the common language all signals are translated into before storage.

Build the adapter layer first, and every subsequent framework integration is a single file.

---


What this document describes is not a feature. It is a **cognitive substrate** — infrastructure that sits beneath any LLM agent and provides the memory properties that the base model architecture cannot. The key properties of the complete system:

| Property | Mechanism |
|---|---|
| Real-time episodic encoding | Fast-lane stream embedder (Engram) |
| Associative recall without explicit query | Injection agent at natural pause points (Anamnesis) |
| Semantic structure and topic coherence | Kairos — async topic consolidator |
| Provisional insight preservation | Validation lifecycle on reasoning chunks |
| Compaction survival | PreCompact snapshots + priority re-injection |
| Cross-session continuity | Master session with topic-organized KG |
| Loop detection and repetition prevention | Novelty scoring detecting high-similarity recent hits |
| Full signal capture | Human, model, tool, reasoning — all ingested |
| Model and framework agnostic | Normalized adapter layer across all LLM observability surfaces |
| Unified cross-tool memory | Session router resolving identity across Claude Code, Codex, LangChain, and any observable framework |
| Epistemic entrenchment prevention | Branch point detection from divergent provisional chunks |
| Parallel hypothesis exploration | Independent branch agents sharing memory substrate |
| Negative knowledge preservation | Abandoned branch paths stored as validated constraints |
| Branch synthesis injection | Confidence-differential injection after parallel exploration |
| Physical branch substrate | Git worktrees as filesystem-level parallel experimentation |
| Cross-branch code propagation | Cherry-pick + memory injection when sibling branches find shareable findings |
| Persistence architecture | PostgreSQL 16+ with pgvector — ACID-compliant, filtered ANN search, knowledge graph and chunks in one store |
| Development path | Docker pgvector locally → managed PostgreSQL in production; same schema throughout |
| Somatic affective tagging | Required for all episodic chunks — third-party observer framing, enables affective-register retrieval |
| Input modality metadata | Input route and channel recorded on every human turn — enables learned routing behavior |
| Machine proprioception | Computational self-awareness signals (context pressure, latency, quota) as cognitive context |
| Sidecar taxonomy | Real-Time Layer (Engram, Anamnesis, Eidos) + Reflective Layer (Kairos, Praxis, Oneiros, Psyche) |
| Oneiros — lossy consolidation | Reads full topic corpus, writes generalized belief statements, archives episodic scaffolding |
| Productive forgetting | Per-topic retention policies; Oneiros replaces episodic specificity with semantic generalization |
| Psyche — narrative self-model | Batch self-reflection, dual output: temporal steering injection + stateful soul.md writes |
| Psyche gate bypass | Self-narrative bypasses Anamnesis conjunctive gate unconditionally — emotional brain is louder |
| Confusion score as steering | Advisory signal only — invites model self-reflection, does not automate injection suppression |
| Ambient associative recall | Memories surface without explicit retrieval — injection at pause points, not query responses |
| Provisional negative knowledge | Abandoned reasoning paths stored as validated constraints, not discarded |
| Cognitive substrate as infrastructure | Framework-agnostic, beneath any agent — observability layer, not agent feature |
| Engram / CLS correspondence | Direct biological analog to hippocampal fast encoding + cortical slow consolidation |
| Affective memory (amygdala) | Somatic tags + affective-register retrieval mirrors emotional memory weighting |
| Default Mode Network analog | Reflective sidecar layer (Kairos, Oneiros, Psyche) implements functional DMN |
| Knowledge compound interest | Long-running agents have qualitatively different capabilities; memory substrate is durable asset |
| Memory as identity substrate | Continuous cross-session memory enables functional analog of agent identity and character |
| Semantic pollution prevention | Conjunctive injection gate — all conditions must pass, biased toward silence |
| Session confusion detection | Composite score from contradiction rate, reasoning inflation, tool repetition, hedge frequency |
| Progressive injection dial-back | Five-tier ladder from nominal to full suspension with automated recovery |
| Injection cooldown and recovery | Coherence recovery window with trailing average before graduated resumption |
| Procedural memory optimization | Praxis: skill invocation pattern analysis, procedural notes injection |
| Skill refactoring recommendations | Evidence-backed proposals with eval harness validation, human-in-the-loop approval |
| Deterministic script extraction | Detection of always-identical LLM reasoning paths, replacement with scripts |
| Self-improving agent behavior | Procedural notes accumulate outcome signal, graduate to refactoring recommendations |

The architecture is biologically grounded (hippocampal/cortical two-speed model), implementable incrementally, testable at each phase, and deployable on local hardware without API dependencies.

The goal is an agent that doesn't just use memory as a tool — but one for whom memory is a fundamental property of cognition, as invisible and automatic as it is in the humans it works alongside.

---

*Document version: 1.8 — March 2026*
*Architecture status: Design complete, implementation Phase 1 ready*
*Changelog v1.1: Added Section 15 — Model-Agnostic Ingestion; updated Summary table; added document provenance header*
*Changelog v1.2: Expanded Section 6.4; added Section 6.5 — Epistemic Entrenchment, Hive-Mind Branching; added Section 7.5 — Branch Synthesis Injection Format*
*Changelog v1.3: Added Section 6.6 — Code and Systems Optimization: Git Worktrees as Physical Branch Substrate*
*Changelog v1.4: Complete rewrite of Section 7 — Injection Architecture with Pollution Taxonomy, Conjunctive Gate, Confusion Scoring, and Progressive Dial-Back*
*Changelog v1.5: Added Praxis — Procedural Memory Optimizer (Section 9); updated Inter-Sidecar Communication map*
*Changelog v1.6: Named sidecar constellation — Engram, Anamnesis, Kairos, Eidos, Praxis; replaced SQLite/NetworkX/Qdrant with PostgreSQL + pgvector as production persistence architecture*
*Changelog v1.7: Added Sections 4.7 (Somatic Affective Tags — required), 4.8 (Input Modality Metadata), 4.9 (Machine Proprioception); replaced arbitration with cartography in Section 6.5 with BranchSeed exit-criteria seeding; demoted confusion score from automated control to advisory steering signal (Section 7.4); restructured Section 9 into Real-Time/Reflective layers; added Oneiros (lossy consolidation) and Psyche (narrative self-model + emotional steering) sidecars; updated Engram no-pruning mandate; updated inter-sidecar communication map; updated TOC and Summary table*
*Changelog v1.8: Added Section 16 (What Is Actually Novel Here — honest examination of novelty claims); Section 17 (Parallels with Neuroscience — CLS theory, reconsolidation, DMN, amygdala, and what the architecture does not model); Section 18 (Implications — stateless to continuous agents, identity, compound interest, git parallel, collaboration metaphor, open consciousness question); updated TOC and Summary table*
