# LAN Remote Control UI (Electron/Web)

## 1. Context
- **Problem statement:** Atlas now exposes a LAN control-plane API, but there is no friendly UI for remote computers. Dave wants a persistent Electron-style companion app at work that can issue chat messages, run actions, view status/history, and manage clipboard from a browser-like shell.
- **Why now:** The control-plane MVP landed (status/message/action/clipboard/help endpoints). Delivering a front-end quickly unlocks remote workflows while the API surface is still small.
- **Current behavior:** Interaction requires the Windows host (Atlas UI) or raw curl/CLI against the API. No hosted dashboard exists.
- **Constraints:** 
  - Front-end built with Node.js + TypeScript, bundling a web UI served on port 5111, optionally packaged as Electron later.
  - Must rely solely on LAN API endpoints (no direct DB reads).
  - Authentication via generated tokens; never store plaintext tokens on disk unless user opts in.
  - UI should be desktop-friendly (keyboard shortcuts, persistent session).

## 2. Requirements
### Functional
- **R1:** Provide pages/components for: chat (POST /api/message), action runner (/api/action/run), task snapshot (/api/tasks), status overview (/api/status), history viewer (/api/history), clipboard sync (/api/clipboard get/set).
- **R2:** Implement token onboarding (paste token, optional remember) and client-side rate limiting/backoff.
- **R3:** Show real-time updates by polling or SSE (initially poll /api/status + /api/history).
- **R4:** Surface API docs via `/api/help` (render endpoints + sample curl).
- **R5:** Provide configurable base URL/port (default http://atlas-host:8715) and run the web server on local port 5111 (Express/Next or Vite dev server) with reverse proxy for dev.

### Non-Functional
- Node 20+/ESM TypeScript project with ESLint + Jest/Vitest.
- Zero-trust default: require token on each request (stored in memory unless user enables “remember token” which uses encrypted storage).
- Responsive layout for 1080p desktops; degrade gracefully to 1366px.
- Error states for unauthorized, offline, or policy-blocked actions.

## 3. User Stories
- As Dave, I open the LAN Control app, see Atlas’s status/heartbeat, and send a chat message from my work PC without remoting home.
- As Dave, I trigger a saved Atlas action (e.g., “Compact”) from the web UI and see its acceptance result.
- As Dave, I view open tasks/history to decide whether to interrupt.
- As Dave, I copy a snippet from Atlas’s clipboard into my local clipboard via the UI.

## 4. Acceptance Criteria
- [ ] AC1: Visiting `http://localhost:5111` shows a login screen; after supplying host/token, chat pane sends `/api/message` and displays responses/queue state.
- [ ] AC2: Status dashboard polls `/api/status` every 5 seconds and renders session id, turn state, heartbeat info.
- [ ] AC3: Task table pulls `/api/tasks` + history list from `/api/history`.
- [ ] AC4: Action tab lists available actions (config file or manual entry) and runs `/api/action/run`.
- [ ] AC5: Clipboard tab shows current text (/api/clipboard/get) and allows pushing new text.
- [ ] AC6: Help tab renders `/api/help` JSON into human-readable docs.
- [ ] AC7: All API calls include token header, handle 401/429 gracefully, and prompt re-login when necessary.

## 5. Technical Architecture
- **Decision:** Use Vite + React + TypeScript for UI, packaged via Electron (later).  
  - Status: `Proposed`  
  - Rationale: Fast dev tooling, easy component model, works with future Electron.
- **Decision:** Use Express proxy on port 5111 to avoid CORS issues; Express forwards requests to Atlas host with token injection.  
  - Status: `Proposed`  
  - Alternatives: Configure CORS on Atlas API (not desired yet).
- **Decision:** Store configuration (host, port, token) in `~/.atlas-remote-ui/config.json` encrypted with system DPAPI on Windows or keytar cross-platform.  
  - Status: `Proposed`.
- **Decision:** Implement polling for status/history/tasks initially; add SSE later.  
  - Status: `Agreed`.
- **Decision:** Provide shared TypeScript client typed from OpenAPI (generate via `openapi-typescript`).  
  - Status: `Proposed`.

## 6. Execution Plan
### M1 – Project Bootstrap & Auth Flow
- Scope: Create Node/TS repo under `remote-ui/`, Vite + React app, Express proxy server, configuration persistence, login screen, help tab rendering `/api/help`.
- Deliverables: `package.json`, `tsconfig`, `vite.config`, `src/` components, proxy server, docs for running on port 5111.
- Dependencies: existing LAN API reachable; token in hand.

### M2 – Core Features (Chat, Status, Tasks, Clipboard)
- Scope: Chat pane (text input, send button, message log), status cards (session id, heartbeat, turn state), tasks table (paginated), history list, clipboard panel with copy/paste.
- Deliverables: React components + hooks for API calls, polling loop, optimistic UI for message send, toast notifications for errors.
- Dependencies: M1 infrastructure done.

### M3 – Action Runner & Enhancements
- Scope: Action tab (list actions, run action), host/port management UI, token rotation helper, optional SSE support, dark mode styling, packaging instructions for Electron or NW.js.
- Deliverables: Action runner UI, manual action config file, improved error handling, nodemon scripts, Electron entrypoint (optional).
- Dependencies: M2 complete, list of available actions.

## 7. Test Cases
- **TC1 – Auth Reject:** With invalid token, ensure UI shows “Unauthorized” and prompts re-entry.
- **TC2 – Chat Success:** Enter message “Ping”; expect queued status + activity record.
- **TC3 – Clipboard Flow:** Fetch clipboard -> show text; set clipboard -> call API, confirm text echo.
- **TC4 – Offline Mode:** Disconnect host; UI shows offline banner and retries with backoff.
- **TC5 – Action Runner:** Run action id 5; UI shows acceptance, error if busy.
- **TC6 – Help Rendering:** `/api/help` JSON is cached and displayed with endpoint descriptions.

## 8. Test Methodology
- Automated: Vitest/Jest unit tests for API client + hooks; Playwright component tests for critical flows (login, chat). 
- Manual: Run against dev Atlas host, verify each tab, test token rotation and offline states.
- Soak: Keep app open 24h polling every 5s, ensure no memory leaks (Chrome profiler).

## 9. Observability
- Client logs: structured console logs (level + message) and optional file logging for Electron packaging.
- Metrics: Track request durations via browser Performance API (optional). 
- Alerts: None (client-side), but UI should display status banners when repeated failures occur.

## 10. Risks & Mitigations
- **Risk:** Token leak stored in plain text.  
  - Mitigation: Default to memory-only; optional encrypted storage; warn user if persisting.
- **Risk:** API CORS issues.  
  - Mitigation: Use Express proxy or configure `fetch` with `proxyUrl`.
- **Risk:** Frequent polling loads Atlas.  
  - Mitigation: Exponential backoff when idle; allow user to tune interval.

## 11. Rollout Plan
- Stage 1: Dev-only build served via `npm run dev` (hot reload).
- Stage 2: Bundle static assets + proxy server; host on Atlas machine (optional) or run on remote PC.
- Stage 3: Package as Electron app with auto-start + auto-update (later).

## 12. Rollback Plan
- Since it’s a separate client, rollback = stop server or revert to previous release; no Atlas changes required. Revoke tokens if compromised.

## 13. Open Questions
- Q1: Should the actions list be fetched from Atlas (new `/api/actions`) or maintained locally?
- Q2: Is SSE/WebSocket support required in v1, or is polling acceptable?
- Q3: Do we need multi-user support (per-device tokens) or is single-user (Dave) sufficient initially?
