# Trading Skill Suite (Crypto + Equities)

## Context and Background

User requested a multi-skill autonomous trading architecture separated by domain (crypto and stocks), with persistent learning via Memory Core V2 and explicit portfolio management behavior.

## Feature Requirements

### Functional

- Create at least three new skills with distinct responsibilities.
- Provide separate skill paths for crypto and stock workflows.
- Ensure each skill reads/writes Memory Core V2 context.
- Integrate crypto execution handoff to `coinbase-api-manager`.
- Provide reusable helper for memory ingestion from trading workflows.

### Non-Functional

- Keep execution guardrails explicit and fail-closed.
- Keep skill outputs structured for agent-to-agent handoff.
- Avoid overloading one skill with all responsibilities.

## User Stories / Acceptance Criteria

1. As an operator, I can run crypto research and persist findings before strategy execution.
2. As an operator, I can run crypto strategy execution with prior memory context and Coinbase guardrails.
3. As an operator, I can run stock market research separately from crypto workflows.
4. As an operator, I can manage stock portfolio allocations with explicit rebalance outputs.
5. As an operator, I can log any strategy note into Memory Core V2 using one helper script.

## Execution Plan

### Phase 1: Skill Definitions

- Add `crypto-market-intel`.
- Add `crypto-strategy-trader`.
- Add `equities-market-intel`.
- Add `equities-portfolio-manager`.
- Add `hybrid-trading-orchestrator`.

### Phase 2: Memory Integration

- Add standard memory search/ingest/promote command blocks in each skill.
- Add shared `scripts/trading/trading_memory_note.py` helper.

### Phase 3: Handoff Architecture

- Crypto path: `crypto-market-intel -> crypto-strategy-trader -> coinbase-api-manager`.
- Equity path: `equities-market-intel -> equities-portfolio-manager -> stocks_paper_trader`.
- Combined path: `hybrid-trading-orchestrator -> trading_dual_cycle.py`.

## Technical Architecture

- `Agreed`: Domain-separated skills for crypto and stocks.
- `Agreed`: Memory Core V2 used in every skill (recall + persist).
- `Agreed`: Coinbase execution is isolated in `coinbase-api-manager`.
- `Proposed`: Add future stock broker execution adapter skill to close equity execution loop.
- `Proposed`: Add scheduler triggers for periodic research and strategy runs.
- `Agreed`: Current stocks execution mode is paper trading only.

## Test Cases

- Trigger crypto research prompt and verify output includes structured regime + watchlist + memory ingest step.
- Trigger crypto strategy prompt and verify handoff to Coinbase execution command.
- Trigger equities research prompt and verify sector/macro outputs + memory step.
- Trigger equities portfolio prompt and verify allocation/hedge/execution-intent output schema.

## Test Methodology

### Manual

- Invoke each skill with one representative prompt.
- Confirm command blocks and output templates are coherent.
- Confirm memory helper script CLI works.

### Automated

- Syntax compile check for helper script.
- Future: add trigger-eval suite for under/over-trigger tuning.

## Risks, Dependencies, Rollout, Rollback

### Risks

- Skill overlap can cause ambiguous triggering if descriptions are too broad.
- Equity execution remains planning-only until broker adapter exists.

### Dependencies

- `atlas_actions memory` command availability.
- Existing `coinbase-api-manager` execution scripts.

### Rollout

- Deploy skills immediately for research/strategy workflows.
- Add scheduled orchestration after initial manual validation.

### Rollback

- Remove newly added skill folders.
- Stop using `scripts/trading/trading_memory_note.py` helper.
