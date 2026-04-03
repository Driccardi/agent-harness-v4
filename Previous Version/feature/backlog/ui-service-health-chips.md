# UI Service Health Chips Feature Plan

## Context and Background
- Atlas-core now depends on multiple local services/endpoints (memory-core, curator LLM, LAN API, Postgres, and integrations).
- Current UI only shows memory health. Operators need fast at-a-glance operational state for all critical dependencies.
- Requirement: show one chip per service, with no visible label text; identity is provided on hover tooltip.

## Feature Requirements
### Functional
1. Render a compact chip row in Atlas UI with one chip per monitored service.
2. Chips are icon-only by default (no text labels).
3. Hover tooltip must show:
- service name,
- endpoint/port,
- last check timestamp,
- current status details.
4. Each chip must support `Red`, `Yellow`, `Green` state.
5. Poll services on interval and update chips without blocking UI thread.
6. Support token-protected health probes (LAN API) using expected-auth semantics.

### Non-Functional
- Polling must not degrade UI responsiveness.
- Failed probes must be bounded by short timeouts.
- Service list should be centrally configurable for future additions.

## Monitored Services (Initial)
1. `memory_core_api`
- Probe: `GET http://127.0.0.1:5147/health`
- Green: `200` with JSON `status in {ok,degraded}`
- Yellow: `200` with degraded payload concerns (nonzero errors/backlog threshold)
- Red: timeout/connection refused/non-200

2. `curator_llm`
- Probe: `GET http://127.0.0.1:18080/health`
- Green: `200`
- Yellow: `200` but slow response over threshold
- Red: timeout/connection refused/non-200

3. `atlas_remote_api`
- Probe: `GET http://127.0.0.1:8715/api/status` without token
- Green: endpoint reachable and returns `401 INVALID_TOKEN` (expected unauth)
- Yellow: reachable but unexpected payload/status
- Red: timeout/connection refused

4. `postgres_memory`
- Probe: TCP connect `127.0.0.1:5432` and optional lightweight SQL/`pg_isready`
- Green: accepting connections
- Yellow: accepting but high latency or intermittent failures
- Red: refused/unreachable

5. `spotify_integration`
- Probe: local readiness check via existing Spotify skill/config validation
- Green: configured and status call succeeds
- Yellow: configured but auth refresh needed/temporary API failure
- Red: missing config or repeated failures

6. `whisper_local`
- Probe: in-process model readiness flags + recent transcription heartbeat age
- Green: model loaded and recent successful STT within threshold
- Yellow: loaded but stale/no recent STT
- Red: model load failure/unavailable

## User Stories / Acceptance Criteria
1. As an operator, I can glance at the chip row and see if Atlas dependencies are healthy.
- Acceptance: all configured services show a chip with color state.
2. As an operator, I can hover each chip to identify the underlying service.
- Acceptance: tooltip shows service name and endpoint/port.
3. As an operator, I can distinguish degraded from failed dependencies.
- Acceptance: yellow and red states are triggered by defined probe rules.
4. As an operator, I can trust chips are current.
- Acceptance: tooltip displays last check time and probe latency.

## Technical Architecture
### Architecture Decisions
- `Agreed`: Add a centralized `ServiceHealthMonitor` in `atlas_ui.py`.
- `Agreed`: Use icon-only chips; no inline service labels.
- `Agreed`: Tooltip is authoritative identity/details channel.
- `Agreed`: Run probes in background thread; UI updates via main-thread queue.
- `Proposed`: Move probe definitions into a dedicated module (`service_health.py`) once stable.

### Data Model (UI Runtime)
- `ServiceProbeSpec`
  - `id`
  - `display_name`
  - `kind` (`http`, `tcp`, `internal`)
  - `target`
  - `timeout_s`
  - `expected_statuses`
  - `expected_auth_behavior` (optional)
- `ServiceHealthState`
  - `id`
  - `color_state` (`green|yellow|red|unknown`)
  - `summary`
  - `latency_ms`
  - `last_checked_at`
  - `raw_status_code`

## Execution Plan
### Phase 1: UI and Probe Framework
1. Add chip container to header/status area.
2. Add icon-only chip widgets and tooltip wiring.
3. Add probe scheduler loop and state cache.

### Phase 2: Service Probes
1. Implement HTTP probes for memory-core, curator LLM, atlas-remote.
2. Implement TCP/internal probes for Postgres, whisper-local, spotify.
3. Encode red/yellow/green threshold logic per service.

### Phase 3: Polish and Reliability
1. Add stale-data fallback (`unknown` when no recent checks).
2. Add debounce/throttle to avoid tooltip churn.
3. Add settings toggles for poll interval and enabled probes.

## Test Cases
| ID | Test | Type | Pass Criteria |
|---|---|---|---|
| SHC-T1 | Memory-core healthy | Integration | Memory chip turns green on `200 /health` |
| SHC-T2 | Curator endpoint down | Integration | Curator chip turns red on connection refusal |
| SHC-T3 | LAN API auth-protected reachable | Integration | Atlas-remote chip green on expected `401 INVALID_TOKEN` |
| SHC-T4 | Postgres down | Integration | Postgres chip red when TCP connect fails |
| SHC-T5 | Whisper stale | Unit/UI | Whisper chip yellow if no recent STT heartbeat |
| SHC-T6 | Tooltip identity | UI | Hover shows service name + endpoint + last check |
| SHC-T7 | Polling resilience | Soak | UI remains responsive with repeated probe failures |

## Test Methodology
### Automated
- Unit tests for state classification logic.
- Integration tests with mocked HTTP/TCP responders.

### Manual
- Start/stop each dependency and verify chip color transitions.
- Verify tooltips for all chips.

## Risks, Dependencies, Rollout, Rollback
### Risks
- False yellow/red from transient local spikes.
- Endpoint semantics drift (e.g., auth response format changes).
- UI clutter if chips are not visually balanced.

### Dependencies
- Existing `memory_admin` / network utilities.
- Atlas UI tooltip component.
- Service availability on configured ports.

### Rollout
1. Ship behind `service_chips_enabled` UI flag.
2. Enable for local operator profile.
3. Tune thresholds after live observation.

### Rollback
- Disable `service_chips_enabled` and retain existing memory status panel.
