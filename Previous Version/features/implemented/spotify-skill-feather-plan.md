# Spotify Skill Feather Plan

**Owner:** Atlas  
**Last Updated:** 2026-02-28

## 1. Outcomes & Guardrails
- Allow Atlas to manage Spotify playlists (list, create, modify, reorder) on David's account without leaving the voice/ui flows.
- Allow Atlas to start/stop playback, skip tracks, and change volume on a local device at David's desk, defaulting to a headless Connect target that Atlas can launch and monitor.
- Respect Spotify's latest API policies (Authorization Code w/ PKCE, scoped access, new playlist item endpoints from Feb 2026) and store secrets/tokens outside of git.
- Keep orchestration voice-first: voice_loop + atlas_ui commands should invoke high-level skill intents, with state mirrored into Task Hub actions when appropriate.

## 2. Research Highlights
1. Spotify's Authorization Code flow w/ PKCE remains the supported pattern for native/desktop apps; token refresh uses the standard refresh token grant and requires `user-read-email` + `playlist-modify-*` + `user-modify-playback-state` scopes depending on feature depth. Premium is required for playback control.  
2. Playlist APIs were updated (Feb 14 2026) to consolidate around `/playlists/{id}/items` and `/playlists/{id}/tracks`; Atlas should move directly to the new endpoints to avoid deprecation churn.  
3. Playback control works against any active Spotify Connect device; we can either target the running desktop app or ship a bundled `librespot` child process to guarantee a controllable local player.  
4. The Web Playback SDK (JS) is optional, but a lightweight local Connect daemon gives us a device-id for CLI-triggered playback without user interaction.

## 3. Architecture Sketch
- **spotify_client.py**: typed wrapper around OAuth + Spotify REST endpoints using `requests` or `httpx`, with retry + rate-limit backoff and token caching in `output/secrets/spotify_tokens.json`.
- **spotify_skill.py**: intent router invoked from voice_loop / atlas_ui. Exposes high-level commands (`play_playlist`, `pause`, `ensure_local_device`, `add_to_playlist`, etc.) and logs actions to Task Hub for traceability.
- **local_device_manager.py**: optional helper that can start/stop a bundled `librespot`/`spotifyd` binary, report health, and surface Connect device_id. Tracks the spawned process PID for cleanup.
- **Config**: new `config/spotify.json` storing client_id, redirect_uri, preferred device name, allowed command whitelist. Secrets (client secret, refresh token) stored in `output/secrets/` and loaded via env variables.
- **UI hooks**: quick controls (play/pause, next, volume slider) embedded into atlas_ui along with playlist dropdown + “send track to playlist” menu. CLI voice commands call shared intents.

## 4. Workstreams
1. **Developer onboarding + OAuth harness**
   - Register Atlas app in Spotify dashboard, noting client id/secret + redirect URI (e.g., `http://localhost:47832/callback`).
   - Build `scripts/spotify_oauth.py` to run Authorization Code w/ PKCE, spin up a short-lived HTTP server, exchange code, and write encrypted token bundle.
   - Document scopes + manual steps in README and `config/spotify.json.example`.
2. **Core client + data models**
   - Implement typed client with helpers for pagination, `market` selection, error normalization, and rate limit (429) retries.
   - Unit-test token refresh, playlist listing, playback commands using `pytest` + recorded fixtures.
3. **Playlist management intents**
   - Support: list playlists, create playlist, add/remove/reorder tracks, sync Atlas-curated lists.
   - Provide voice intents like “Add this track to Worldhopper Mix” and UI forms for manual selection.
   - Log results (playlist id, track count) to Task Hub events when invoked automatically.
4. **Playback + local device control**
   - Build local Connect service wrapper (bundle `librespot` release, configure with David's Spotify username + stored OAuth token or app password) with CLI hooks to start/stop/process-health.
   - Implement device discovery, default-device selection, and fallback to whichever device is playing if David is already listening elsewhere.
   - Expose intents for play/pause/skip/seek/volume, leveraging `/me/player/play`, `/me/player/pause`, etc.
5. **Voice/UI integration & scripting**
   - Extend `voice_loop.py` command parser with Spotify verbs (“play”, “pause”, “queue track”), mapping to spotify_skill methods.
   - In `atlas_ui.py`, add a Spotify panel for quick actions + playlist picker + status, ensuring async calls do not freeze Tkinter loop.
   - Add automation hooks so Task Hub can schedule Spotify actions (e.g., “start playlist at 6 PM”).
6. **Telemetry, safety, and docs**
   - Emit structured logs for every Spotify API call (endpoint, latency, track ids) to help rate-limit debugging.
   - Provide guardrails so destructive calls (playlist delete, clearing queue) always confirm via UI or explicit voice confirmation.
   - Document known limitations (Premium requirement, device focus, offline behavior) and add manual test script covering playlists + playback + failover.

## 5. Dependencies & Risks
- **Spotify Premium**: playback APIs require premium; confirm David's account type.
- **OAuth tokens & secrets**: need secure storage + rotation story; consider encrypting token blob with Windows DPAPI or user-provided passphrase.
- **Local device binary**: bundling librespot/spotifyd introduces upkeep (updates, antivirus false positives). Alternative is controlling the official desktop app if always running.
- **Rate limiting**: high-frequency playlist edits could hit 429; include retries + Task Hub visibility for failures.
- **Voice UX**: need disambiguation strategy when playlist/track names collide; consider “confirm?” follow-ups.

## 6. Deliverables & Acceptance Criteria
1. `spotify_skill.py` and `spotify_client.py` with integration tests hitting Spotify sandbox data (mocked) and manual checklist recorded.
2. OAuth bootstrap script + README instructions verified end-to-end on Atlas machine.
3. Local device manager that can start/ping/stop a Connect target and automatically select it for playback.
4. Voice/UI hooks allowing at least: start playlist, pause/resume, skip, list playlists, add/remove track, announce currently playing track.
5. Task Hub automation entry points (`atlas_actions.py tasks run-spotify ...`) so other tasks can trigger Spotify control.

## 7. Next Actions
1. Approve plan + confirm David wants bundled librespot vs. relying on desktop app.
2. Implement Workstream 1 (OAuth harness + config scaffolding).
3. Stand up spotify_skill skeleton with stub intents and wire voice/UI commands behind feature flag.
4. Build local device manager + minimal playback controls before tackling full playlist automation.
