# LAN Control Plane & API Management Layer

## 1. Context
- **Problem statement:** Atlas currently exposes almost no programmability surface beyond the local UI/CLI, which blocks multi-device workflows and prevents other local agents or tools from orchestrating Atlas capabilities. We need a first-class control plane that lets trusted LAN clients issue commands, share clipboard/context, and observe state without punching holes to the public internet.
- **Why now:** The backlog already calls for a LAN Web Control Bridge; recent requests (03 Mar 2026) explicitly ask for “the entire control plane for this application in that API” plus a comprehensive API management layer. Shipping it now unlocks collaboration across Dave’s multi-PC desk setup and sets the foundation for richer automation.
- **Current behavior:** No HTTP API; all flows require Atlas UI/voice loop. Clipboard moves, Task Hub edits, mic control, etc., are limited to the host machine. Security policies are ad hoc (per-feature toggles only).
- **Constraints:** Must stay LAN-only by default (no WAN routing/tunneling), guard against unauthorized devices, reuse existing Task Hub/action infrastructure, and introduce API governance without breaking the offline-friendly posture. Windows host but should stay portable to Linux/macOS for future expansion.

## 2. Requirements
### 2.1 Functional
- **R1:** Provide a FastAPI-based service bound to configurable LAN interfaces (default `0.0.0.0:<port>`) exposing REST + optional SSE/WebSocket streams.
- **R2:** Implement core routes for messaging (`POST /api/message`), action dispatch, clipboard push/pull, Task Hub CRUD, heartbeat metrics, and status/history queries.
- **R3:** Add an API management layer with API keys, per-client policies (`auto/ask/deny`), request logging, rate/quota enforcement, and audit export.
- **R4:** Support multi-device sessions (desktop, tablet, automation scripts) with token-scoped capabilities and optional secondary factors (short-lived signed nonce).
- **R5:** Surface API control (enable/disable, token rotation, per-route toggles) inside Atlas UI Settings + CLI.

### 2.2 Non-Functional
- **Performance:** Median command latency < 250 ms from LAN client to dispatcher enqueue; streaming responses should begin within 750 ms.
- **Reliability:** API service auto-recovers with Atlas UI restarts; requests queue persistently (disk-backed) so commands aren’t lost on short restarts.
- **Security/Privacy:** TLS optional but recommendable (support local certificate). Minimum shared-secret auth, optional mTLS, IP allowlists, per-route scopes. No WAN exposure by default.
- **UX:** Minimal setup (generate token + toggle). Clear error semantics for rejected requests; human-readable audit log.

## 3. User Stories
- As Dave, I want to send Atlas a text command from my work laptop without switching keyboards, so I can keep focus on primary monitors.
- As Atlas, I need to enforce per-device policies so untrusted LAN devices can’t trigger destructive actions.
- As an automation script, I want to poll a structured status endpoint so I can display Atlas heartbeat on a wallboard.
- As Dave, I want to copy Atlas’s last reply to my clipboard from another PC to drop into notes quickly.

## 4. Acceptance Criteria
- [ ] AC1: From a second LAN machine, Dave can open the web app, authenticate, send a `/api/message` command, and see Atlas respond in real time.
- [ ] AC2: Clipboard push/pull works cross-device with audit entries showing caller identity, timestamp, and result.
- [ ] AC3: Policy toggle demonstrates `auto/ask/deny`: when set to `ask`, Atlas pauses the request and asks Dave for approval before executing.
- [ ] AC4: API logs show per-request metadata (client id, route, latency, status) and can be tailed from UI.

## 5. Technical Architecture
- **Decision:** Use FastAPI + Uvicorn workers running inside Atlas host process (shared event loop) with `multiprocessing.Queue` handoff into the existing dispatcher.  
  - Status: `Agreed`  
  - Rationale: FastAPI already in stack; async-friendly; easy to document via OpenAPI.  
  - Alternatives: Flask (sync-heavy), custom TCP server (reinventing tooling).
- **Decision:** Bind service to LAN interface only and gate via API keys w/ HMAC signature + optional IP allowlist.  
  - Status: `Agreed`  
  - Rationale: Keeps default local, avoids accidental public exposure.  
  - Alternatives: Reverse proxy w/ Cloudflare tunnel (too risky now).
- **Decision:** Introduce “Atlas Control Plane” module responsible for API policy, throttling, and audit logging backed by SQLite (new `output/api_control.db`).  
  - Status: `Proposed`  
  - Rationale: Reuses existing SQLite familiarity; decouples from Task Hub DB.  
  - Alternatives: Extend Task Hub schema (risks entanglement).
- **Decision:** Offer client SDK scaffolds (Python + TypeScript) generated from OpenAPI spec.  
  - Status: `Proposed`  
  - Rationale: Encourages adoption; ensures consistent auth header usage.  
  - Alternatives: Manual docs only.
- **Decision:** Default responses over SSE for streaming channels; fallback to long-poll for clients without SSE support.  
  - Status: `Proposed`.

## 6. Execution Plan
### M1 – Infrastructure & Security
- Scope: FastAPI skeleton, config surface, token management CLI/UI, auth middleware, request logging.
- Deliverables: `control_plane/server.py`, `api_control.db`, UI settings pane, CLI tooling to rotate tokens.
- Dependencies: FastAPI/uvicorn packages, encryption helpers (reuse DPAPI/Fernet).

### M2 – Core APIs & Policy Engine
- Scope: Implement `/api/message`, `/api/action/run`, `/api/status`, `/api/history`, `/api/clipboard/get|set`, `/api/tasks/*`, plus policy evaluation (`auto/ask/deny`, rate limits).
- Deliverables: Handlers, dispatcher bridge, policy evaluation unit tests, OpenAPI spec.
- Dependencies: Task Hub CRUD, clipboard module, existing dispatcher hooks.

### M3 – Streaming & Observability
- Scope: Add SSE/WebSocket streaming, per-request metrics, Prometheus-style counters, UI audit viewer, CLI `atlas_actions.py api logs`.
- Deliverables: Streaming adapter, metrics instrumentation, documentation.
- Dependencies: heartbeat_checkin instrumentation, logging framework.

### M4 – Client App & Hardening
- Scope: Lightweight LAN web client, API SDKs, soak tests, failover behavior, security review.
- Deliverables: `webapp/` bundle, SDK packages, test plans, docs.
- Dependencies: Node toolchain (for UI), manual QA resources.

## 7. Test Cases
- **TC1 – Auth rejection:**  
  - Preconditions: API enabled, invalid token.  
  - Steps: Call `/api/status` with wrong token.  
  - Expected: 401 with `INVALID_TOKEN`, log entry.
- **TC2 – Policy ask flow:**  
  - Preconditions: Client policy set to `ask`.  
  - Steps: POST `/api/action/run`.  
  - Expected: API returns `PENDING_APPROVAL`, Atlas prompts Dave; upon approval, action runs; log updated.
- **TC3 – Clipboard sync:**  
  - Preconditions: Clipboard route enabled.  
  - Steps: `/api/clipboard/set` followed by `/api/clipboard/get`.  
  - Expected: Content matches, audit record stored.
- **TC4 – Streaming status:**  
  - Preconditions: SSE enabled.  
  - Steps: Subscribe to `/api/status/stream`.  
  - Expected: Heartbeat payload within 1 s and updates every 5 s.

## 8. Test Methodology
- **Automated tests:** Pytest suite covering auth middleware, policy engine, rate limiting, dispatcher bridge, SSE streaming. Include fuzz tests for malformed payloads.
- **Manual QA:** Multi-device scenario tests (Windows primary, Mac secondary). Validate UI toggles, approval prompts, clipboard flows.
- **Soak/perf:** 24-hour soak with synthetic requests @ 5 qps to ensure memory stability; capture latency histograms.
- **Failure-injection:** Simulate DB lock, dispatcher stalls, interface down; ensure API returns retriable errors + logs.

## 9. Observability
- **Logs:** Structured JSON per request: `ts`, `client_id`, `route`, `status`, `lat_ms`, `policy_action`. Stored in `output/logs/api_control.jsonl`.
- **Metrics:** Counters for requests, rejects, approvals; gauges for queue depth; histograms for latency. Expose `/metrics` (optional).
- **Alerts:** Thresholds for >5 consecutive auth failures (possible attack) and queue depth > 20 (backpressure).

## 10. Risks & Mitigations
- **Risk:** Accidental WAN exposure via misconfigured interface.  
  - Impact: Unauthorized access.  
  - Mitigation: Default to RFC1918 detection + explicit “I understand” confirmation before binding to public IP.
- **Risk:** API DoS from compromised device.  
  - Impact: Starved dispatcher.  
  - Mitigation: Rate limiting + per-client quotas + ability to revoke tokens instantly.
- **Risk:** Clipboard route leaks sensitive data.  
  - Impact: Privacy breach.  
  - Mitigation: Opt-in per client; redact audit log contents by default; allow “clipboard disabled” policy.

## 11. Rollout Plan
- **Stage 1 (Dev):** Internal testing on lab network, feature flag hidden in UI.
- **Stage 2 (Friends & Family):** Enable on Dave’s LAN only, monitor logs, iterate on UX.
- **Stage 3 (General Availability):** Documented, UI toggle default-on (but service disabled until token created).

## 12. Rollback Plan
- **Trigger:** Critical security flaw, runaway CPU, or API queue destabilizing core loop.
- **Revert steps:** Disable toggle → stop FastAPI server → revoke tokens → remove `api_control.db`. Revert commit if needed.
- **Data recovery:** Restore audit DB from nightly backup (`output/backups/api_control-*.db`).

## 13. Open Questions
- Q1: Do we require mutual TLS for “high-privilege” clients (e.g., other Atlas agents), or is HMAC token sufficient?
- Q2: Should clipboard routes support binary payloads (images) or stay text-only in v1?
- Q3: Does Dave want remote audio/mic control exposed in this API, or keep it intentionally manual for now?

