# Spotify Skill Feature Plan (Comprehensive PRD)

**Owner:** Atlas  
**Date:** 2026-03-01  
**Related Tasks:** #17–20 (Spotify workstreams), #9 (stability guardrails)

---

## 0. Summary
- **Goal:** Give Atlas a first-class Spotify capability that can authenticate once, control playback on a dependable local device, manipulate playlists, and surface Spotify context fluidly through voice_loop.py, atlas_ui.py, and Task Hub automations.
- **Why now:** David wants Spotify to be the primary co-activity surface; the skill unlocks music control, playlist curation, and context-aware routines from the same Atlas session without manual app juggling.
- **Definition of done:** OAuth/bootstrap tooling, resilient API client, playlist & playback intents, UI controls, telemetry, and docs are all shipped with guardrails, passing manual + automated validation, and Task Hub hooks exist for automation.

## 1. Desired Outcomes & KPIs
1. **Zero-friction auth:** OAuth flow runs end-to-end in <2 minutes with clear scopes and persists refresh tokens securely (success % of guided runs).
2. **Reliable playback control:** Atlas can start/pause/skip/seek on the preferred local device with <1.5 s median API latency and >95% command success rate in soak tests.
3. **Playlist operations:** Voice/UI intents for list/create/add/remove/reorder succeed against David’s library with conflict-safe confirmations; <1% failure rate after retries.
4. **UX integration:** Spotify status + quick actions are surfaced in atlas_ui and voice responses with no UI thread blocking (>60 FPS target).
5. **Observability:** Every Spotify API call logged with latency/outcome; alerts fire on sustained 429/5xx (>3 consecutive failures).

## 2. Personas & User Stories
- **David (primary):** “Atlas, start the Worldhopper Mix quietly on the office speakers.” → Voice command triggers playback on local Connect device, UI reflects status, telemetry captured.
- **Atlas task runner:** Scheduled Task Hub entry triggers `play_playlist` at a given time without manual intervention.
- **Power user scenario:** “Queue the latest Stormlight Archive soundtrack and add whatever is playing to the `Deep Work` playlist.” – requires playlist lookup + track context fetch + mutation with confirmation.

## 3. Scope
### In-Scope (v1)
- OAuth Authorization Code w/ PKCE tooling.
- `spotify_client.py` typed wrapper with retries/backoff and token caching.
- `spotify_skill.py` intent router used by voice_loop, atlas_ui, and future automations.
- Playlist management (list, create, add, remove, reorder, rename).
- Playback control (play, pause, resume, skip, previous, seek, volume, device switching).
- Local Connect device manager (librespot or desktop app control) with health checks.
- UI/voice affordances + Task Hub action bindings.
- Structured logging + guardrails for destructive operations.

### Out-of-Scope (v1)
- Spotify recommendations or radio endpoints.
- Collaborative playlist co-editing with other accounts.
- Podcast/library management APIs.
- Cross-account sharing or linking non-Spotify services.
- Billing/subscription management.

## 4. Constraints & Dependencies
- Requires Spotify Premium on David’s account.
- Tokens/secrets stored under `output/secrets/spotify_tokens.json` encrypted via Windows DPAPI (fallback: passphrase env var).
- Network egress to api.spotify.com must be allowed; rate limits handled per API docs.
- Local device binary (`librespot` or `spotifyd`) must be vetted against antivirus and bundled under `bin/`.
- Tkinter UI updates must remain on the main thread; network calls offloaded to worker threads/async tasks.

## 5. Architecture Overview
### Components
1. **scripts/spotify_oauth.py** – launches PKCE flow, spins up localhost callback, saves token bundle + metadata.
2. **spotify_client.py** – thin typed client built on `httpx` with retry policies, instrumentation hooks, and pagination helpers.
3. **spotify_skill.py** – high-level intent layer mapping commands to client calls, enforcing confirmations and logging Task Hub events.
4. **local_device_manager.py** – ensures controllable device via bundled librespot or attaches to desktop Spotify; exposes `ensure_device()`, `device_health()`, `terminate()`.
5. **voice_loop.py / atlas_ui.py adapters** – parse commands, update UI widgets, dispatch async tasks, handle error surfacing.
6. **Task Hub integration** – new action schema (e.g., `spotify.playlist.add_track`) plus CLI helpers inside `atlas_actions.py`.

### Data Flow
1. User command (voice/UI/Task) → `spotify_skill`.
2. Skill validates intent + resolves playlist/track/device context (may query client).
3. Skill invokes `spotify_client` → Spotify REST.
4. Responses + metadata logged to `output/logs/spotify.jsonl` and optionally Task Hub event stream.
5. UI updated via event bus; voice_loop announces confirmations when appropriate.

## 6. Detailed Workstreams & Milestones
### Workstream A – OAuth & Config Scaffold (Task #17)
- Deliverables: PKCE script, config/spotify.json.example, README updates, encrypted token storage helper.
- Steps: register app, capture scopes (`user-read-email`, `playlist-modify-private`, `playlist-modify-public`, `user-modify-playback-state`, `user-read-playback-state`), implement localhost callback server, persist token bundle with refresh + metadata.
- Milestone M1 (Today +1 day): OAuth script tested on Atlas PC, documented replay instructions.

### Workstream B – Core Client & Playlist Intents (Task #18)
- Build `spotify_client.py` with strongly typed request/response dataclasses, network retry/backoff (exponential w/ jitter), and instrumentation hooks.
- Implement playlist APIs:
  - list user playlists (paginated)
  - get playlist details/items
  - create/rename
  - add/remove tracks using new `/playlists/{id}/items` endpoints
  - reorder/move tracks
- Voice/UI intents: “List my playlists,” “Add this to <playlist>,” “Create playlist named <x>.”
- Milestone M2 (Today +3 days): client and playlist intents land with unit tests + CLI smoke script.

### Workstream C – Playback + Local Device Control (Task #19)
- Bundle librespot (64-bit Windows) under `bin/librespot.exe`, provide config template for credentials/device name.
- `local_device_manager` ensures device process running, monitors stdout for readiness, restarts on failure.
- Implement device discovery via `/me/player/devices`, allow selection/pinning, fallback to currently active device.
- Playback intents: play (playlist/track/album), pause, resume, skip, previous, seek, set volume, shuffle/repeat toggles.
- Milestone M3 (Today +5 days): deterministic playback on local device with health reporting + CLI hooks.

### Workstream D – Voice/UI Integration + Telemetry (Task #20)
- Extend `voice_loop.py` grammar with Spotify verbs; add context-specific confirmations (e.g., “Playing Worldhopper Mix on Office Speaker.”).
- Add Tkinter Spotify panel: status banner (track, artist, device), quick controls, playlist dropdown, command queue log.
- Wire Task Hub automations: new `atlas_actions.py tasks run-spotify --action <...>` and scheduler awareness.
- Telemetry: `output/logs/spotify.jsonl`, metrics aggregator (latency, failures, device switches), optional Grafana-friendly CSV export.
- Milestone M4 (Today +7 days): integrated UI + voice experience with observability and docs.

### Cross-Cutting Reliability (Task #9 dependency)
- Auto-retry stalled Spotify turns with tagged telemetry.
- Shared error taxonomy for UI (auth expired, device unavailable, rate limit, network).

## 7. UX & Interaction Notes
- Voice confirmations stay short; destructive actions (removing tracks, clearing playlists) require explicit “Yes” follow-up unless launched from UI with checkbox.
- UI panel includes:
  - Currently playing track info + cover art (optional v1.1)
  - Device selector with health indicator
  - Playlist dropdown + “Add current track” button
  - Command queue log with timestamps
- Task Hub notifications for scheduled Spotify actions (toast + log entry).

## 8. Telemetry & Observability
- `output/logs/spotify.jsonl` schema: `{ts, action, endpoint, latency_ms, status, device_id, playlist_id, retry_count, error?}`.
- Prominent counters:
  - `spotify_api_latency_ms` (p50/p95)
  - `spotify_command_success_total`
  - `spotify_command_failure_total` by reason
  - `spotify_device_restart_total`
- Alert triggers: >3 consecutive 401s (token invalid), >5 librespot restarts within 10 minutes, sustained 429 for >60s.

## 9. Testing & Validation
- **Unit tests:** playlist CRUD, token refresh, retry logic (pytest + responses/httpretty).
- **Integration tests:** mock server verifying OAuth exchange; CLI smoke script hitting live Spotify sandbox data after David authorizes.
- **Manual checklist:** documented in `tests/manual/spotify.md` covering OAuth, playlist operations, playback on local device, UI controls, and failure handling (device unplugged, network drop).
- **CI hook:** ensure `python -m py_compile` and `pytest tests/test_spotify_client.py` run clean.

## 10. Security & Privacy
- Refresh tokens encrypted at rest; only decrypted in-process.
- `.env` stores `SPOTIFY_CLIENT_ID`, `SPOTIFY_REDIRECT_URI`; secrets kept out of git.
- Logs redact sensitive IDs except when necessary for debugging (last 6 chars only).
- Guard rails prevent irreversible actions without confirmation (e.g., playlist delete).

## 11. Rollout Strategy
1. **Dev only:** Atlas runs skill locally with verbose logging.
2. **Shadow mode:** UI displays status read-only; commands disabled pending soak results.
3. **Controlled enablement:** enable voice commands for David with manual libre spot start, monitor telemetry.
4. **Full enablement:** autostart local device, Task Hub automations allowed.
5. **Post-launch audit:** review logs after 48 hours, tune retries/device health thresholds.

## 12. Risks & Mitigations
- **OAuth friction:** Provide fallback manual instructions + cached config template; log friendly errors when callback port busy.
- **Device instability:** Watchdog restarts librespot, fallback to desktop Spotify if persistent failures.
- **Rate limits:** Centralized retry/backoff + user feedback (“Spotify throttled; will retry in 5s”).
- **UI blocking:** All Spotify calls executed in worker pool with queue-driven UI updates.
- **Token leakage:** Enforce DPAPI/passphrase encryption; add `atlas doctor spotify` command to reset credentials safely.

## 13. Open Questions
1. Preferred local device implementation: bundled librespot vs. controlling desktop app? (default assumption: librespot.)
2. Should Atlas announce track metadata every time or only when asked? Need UX direction.
3. Do we need multi-account support (personal vs. shared) this quarter?
4. Is album art display a must-have for v1 UI panel?

## 14. Next Actions
1. Confirm David’s choice for default playback device + librespot acceptability.
2. Start Workstream A immediately (scripts/spotify_oauth.py + config docs).
3. Parallelize Workstream B (client scaffolding) with Workstream C (device manager) if sub-agent capacity exists.
4. Schedule Task Hub entry for integration milestone demos (M2, M3, M4) to keep progress visible.

---

**Appendix:** Reference the earlier `plan/features/backlog/spotify-skill-feather-plan.md` for historical research notes; this PRD supersedes it for execution tracking.
