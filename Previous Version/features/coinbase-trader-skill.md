# Coinbase Trader Skill Plan

## Context and Background

User needs an autonomous Coinbase Advanced Trade skill for agentic crypto/market trading with limited funds and strict account safety. The solution must avoid withdrawal/funding/borrowing pathways and support API-key authentication without OAuth refresh handling.

## Feature Requirements

### Functional

- Create a new skill at `.codex/skills/coinbase-trader/`.
- Implement scriptable runtime under `scripts/coinbase_trader/`.
- Authenticate with Coinbase API key name + private key.
- Support autonomous LLM-driven trade decisions.
- Support live order placement (no paper-trade gate).
- Support all holdings and all markets exposed through selected Advanced Trade endpoints.
- Support order construction for `market`, `limit`, and `stop_limit` in v1.
- Enforce a daily loss cap.
- Append all trade events to `trading-logs/YYYY-MM-DD.log`.
- Send Telegram alert for placed trades where quote notional is greater than `$10`.
- Enforce strict endpoint allowlist + denylist.

### Non-Functional

- Fail closed on policy violations.
- Keep secrets out of source-controlled config.
- Keep setup simple for single-user Windows workflow.
- Maintain auditable JSON logs with timestamps.

## User Stories / Acceptance Criteria

1. As an operator, I can import a Coinbase key file once, then run autonomous cycles without exposing secrets in config.
2. As an operator, I can configure `daily_loss_cap_usd` and see trading blocked automatically after breach.
3. As an operator, I can review appended daily log entries for decision, preview, and placement outcomes.
4. As an operator, I can confirm prohibited endpoint calls are blocked at runtime.
5. As an operator, I get Telegram notifications for trades over `$10`.

## Execution Plan

### Phase 1: Core Scaffolding

- Create skill directory and SKILL.md.
- Create runtime package and CLI entrypoints.
- Create config template and active config.

### Phase 2: Security and Policy

- Add secure key import/store flow.
- Add JWT-authenticated Coinbase client.
- Add endpoint allowlist/denylist gate.

### Phase 3: Autonomous Trading Loop

- Add market snapshot builder.
- Add LLM decision call + strict JSON parse.
- Add order payload builder + preview/place steps.

### Phase 4: Risk and Observability

- Add daily loss-cap state and equity estimator.
- Add append-only logs.
- Add Telegram trade notification.

### Phase 5: Validation and Handoff

- Run static compile checks.
- Document usage and operational kill-switch.

## Technical Architecture

- `Agreed`: API key auth only; no OAuth/token refresh server.
- `Agreed`: Runtime under `scripts/coinbase_trader/` with CLI wrappers in `scripts/`.
- `Agreed`: Endpoint denylist forbids payment methods, transfers, sweeps, allocations, and convert.
- `Agreed`: Logs append to `trading-logs/YYYY-MM-DD.log` as JSON lines.
- `Agreed`: Telegram notifications for placed trades over configured threshold (`10.0` default).
- `Agreed`: Single-user local execution on this workstation.
- `Proposed`: Daily loss cap computed from local opening-equity snapshot minus current estimated equity.
- `Proposed`: No scheduler service included; operator or external scheduler triggers cycles.

## Test Cases

- Import valid keyfile and confirm secure-store retrieval works.
- Run cycle with missing OpenAI key and confirm clear failure.
- Trigger denylisted endpoint (unit/integration simulation) and confirm blocked failure.
- Set tiny daily loss cap and confirm trade cycle returns `blocked_daily_loss_cap`.
- Force HOLD decision and confirm no order placement.
- Force BUY/SELL decision and confirm preview then create order path executes.
- Place trade over `$10` and confirm Telegram send attempted.

## Test Methodology

### Manual

- Use real Coinbase credentials with minimal notional.
- Run single cycle and inspect logs and Telegram output.
- Rotate/remove credentials and confirm kill-switch behavior.

### Automated

- Compile-time checks for new Python modules.
- Add future mock-based tests for decision parsing, policy checks, and order payload validation.

## Risks, Dependencies, Rollout, Rollback

### Risks

- LLM output may be malformed or low quality.
- Equity estimate may not fully capture all derivatives PnL states.
- Live trading can lose funds if strategy is poor.

### Dependencies

- Coinbase Advanced Trade API availability.
- `coinbase-advanced-py` for JWT helper functions.
- OpenAI API access.
- Telegram bot settings for notifications.

### Rollout

- Start with low daily cap and low quote size in config.
- Run one cycle manually before any external automation.

### Rollback

- Disable autonomous orders in config.
- Remove or rotate stored Coinbase credentials.
- Stop invoking run script/scheduler.