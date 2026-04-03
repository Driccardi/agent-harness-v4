# Always-On Wake + Flexible Hotkeys PRD

## 0. Summary
- **Goal**: add an always-on local wake pipeline that keeps mic monitoring low-cost, arms on wake phrase, captures a full command utterance, transcribes with configurable STT route (local/API with failover), and dispatches to Atlas.
- **Secondary Goal**: ship a flexible global hotkey system (up to 6 custom bindings) for channel open, push-to-talk variants, and wake mute controls.
- **Design principle**: local-first for wake detection and low-latency responsiveness; cloud STT remains available as fallback and quality option.

## 1. User Outcome
- David can say: `Hey Atlas` (or custom wake phrase), pause, see UI arm state (green), speak a longer command, and have Atlas execute after pause endpointing.
- David can override voice flow instantly via global hotkeys:
  - `Open Channel > Whisper API`
  - `Open Channel > Whisper Local`
  - `Mute Wake Word`
  - plus up to 3 additional custom actions.

## 2. Scope
### In-scope
- Always-on local wake listener.
- Arm/capture/endpoint/dispatch pipeline.
- STT route selection per invocation (`api_first` vs `local_first`).
- Global hotkey manager with editable bindings in Settings.
- Runtime observability in JSONL and conversation panes.
- Safe fallback behavior on errors.

### Out-of-scope (v1)
- Speaker identification / diarization.
- Full duplex barge-in with partial response interruption.
- Cloud remote wake detection.
- Multi-user profiles.

## 3. High-Level Architecture
- `WakeEngine` (always-hot, low power): `openWakeWord`.
- `CaptureEngine` (armed mode): short audio ring-buffer + active utterance capture.
- `EndpointEngine`: VAD + trailing silence logic to cut command utterance.
- `TranscribeRouter`: dispatches audio to local/API STT by selected mode with fallback.
- `DispatchEngine`: sends transcript to existing Atlas turn pipeline.
- `HotkeyManager`: global bindings -> action invocations.
- `WakeController` state machine orchestrates transitions and cooldowns.

## 4. Pipeline
1. `IDLE_WAKE`: wake model listens continuously.
2. Wake phrase event detected.
3. UI enters `ARMED` (green indicator).
4. Mic stays hot; capture command speech.
5. Endpoint detects pause (silence tail) or max utterance timeout.
6. Audio chunk sent to `TranscribeRouter`.
7. Transcript validated and dispatched to Atlas.
8. System enters short cooldown, then returns to `IDLE_WAKE`.

## 5. State Machine
- `IDLE_WAKE`
- `ARMED`
- `CAPTURING`
- `TRANSCRIBING`
- `DISPATCHING`
- `COOLDOWN`
- `MUTED_WAKE`
- `ERROR_RECOVERY`

Transition rules:
- Wake word only recognized in `IDLE_WAKE`.
- `MUTED_WAKE` ignores wake events but still accepts hotkeys.
- `ERROR_RECOVERY` auto-resets to `IDLE_WAKE` after bounded retries.

## 6. STT Strategy
### Mode A: API-first
- Primary: OpenAI Whisper API.
- Fallback: local faster-whisper.

### Mode B: Local-first
- Primary: local faster-whisper.
- Fallback: OpenAI Whisper API.

### Model utilization
- Keep local model loaded in-process for repeated turns.
- Recommended:
  - wake detection: `openWakeWord`
  - command transcription: `faster-whisper small` (warm)
  - optional low-power downgrade: `tiny.en`

## 7. Endpointing (Pause Detection)
- Use VAD + trailing silence, not transcript token timing.
- Initial defaults:
  - `min_speech_ms = 500`
  - `trailing_silence_ms = 900`
  - `max_utterance_s = 15`
  - `cooldown_ms = 1200`
- Tune per mic/environment and expose in Settings.
  - Since deployment is single-mic, keep wake detection sensitivity fixed in v1 (no user sensitivity control).

## 8. Hotkey System
### Requirements
- Up to 6 configurable global bindings.
- Persist in `output/ui_settings.json`.
- Resolve conflicts and prevent duplicate assignment.
- Allow enable/disable per binding.
- Backend implementation for global hotkeys: `pynput` (fixed choice for v1).

### Initial action registry
- `open_channel_api`
- `open_channel_local`
- `toggle_wake_mute`
- `push_to_talk_api`
- `push_to_talk_local`
- `stop_current_turn`

### UX
- Hotkey Editor in Settings.
- `Capture` mode button per hotkey (optional v1.1).
- Validation message on invalid or duplicate combos.

## 9. UI/UX Design
- Header status chips:
  - `Wake: On/Muted/Error`
  - `State: Idle/Armed/Capturing/Transcribing`
  - `STT Route: API-first/Local-first`
- Visual activation:
  - Green glow or accent when armed.
- Add explicit `Wake Mode` toggle (`On` / `Off`) in Settings.
- Conversation logs include:
  - wake events
  - endpoint reason (`silence`, `max_utterance`)
  - STT backend used
  - fallback events

## 10. Sub-Agent Utilization Plan
Use deterministic task/sub-agent decomposition for faster delivery and safer integration.

### Sub-agent A: Wake Engine Agent
- Deliverables:
  - `wake_engine.py` for `openWakeWord` loop
  - model loading, sensitivity settings
  - wake event callback contract
- Contract:
  - emits `WakeEvent(timestamp, phrase, score)`

### Sub-agent B: Audio Capture + Endpoint Agent
- Deliverables:
  - ring buffer + active capture controller
  - VAD/silence endpointing module
  - audio segment persistence for diagnostics
- Contract:
  - emits `CaptureResult(path, duration, rms, endpoint_reason)`

### Sub-agent C: STT Router Agent
- Deliverables:
  - route policy implementation (`api_first`, `local_first`)
  - failover handling and timing metrics
  - local model prewarm behavior
- Contract:
  - emits `TranscriptionResult(text, backend_used, latency_ms, fallback_used)`

### Sub-agent D: Hotkey Agent
- Deliverables:
  - global hotkey listener abstraction
  - action registry and invocation layer
  - settings serialization + validation
- Contract:
  - emits `HotkeyAction(action_id, timestamp)`

### Sub-agent E: UI Integration Agent
- Deliverables:
  - Settings controls for wake/STT/hotkeys
  - state indicators and error banners
  - conversation/JSONL surfacing
- Contract:
  - consumes all event contracts and updates UI thread-safe queue

### Sub-agent F: Reliability + QA Agent
- Deliverables:
  - soak tests
  - false trigger benchmarks
  - endpoint latency tests
  - recovery tests for device/API failures
- Contract:
  - produces metrics report and recommended default thresholds

## 11. Data Contracts
- `WakeEvent`: `{timestamp, phrase, score, device_id}`
- `CaptureResult`: `{path, duration_sec, rms, endpoint_reason}`
- `TranscriptionResult`: `{text, backend_used, latency_ms, fallback_used, error?}`
- `DispatchResult`: `{session_id, turn_status, tool_events_count}`

## 12. Observability
- Add `wake_events.jsonl` under `output/logs/`.
- Add `stt_metrics.jsonl` under `output/logs/`.
- Metrics:
  - wake detections/hour
  - false activation estimates
  - average arm->dispatch latency
  - fallback rate (local->api, api->local)
  - dropped capture rate

## 13. Failure Handling
- Mic unavailable: raise banner + auto-retry every N seconds.
- Wake model load failure: disable wake mode but keep manual/hotkeys.
- STT failure: fallback route; if both fail, notify and preserve audio artifact.
- Stuck state watchdog: force reset to `IDLE_WAKE` after timeout.

## 14. Security/Privacy
- Wake and non-trigger audio remain local by default.
- In wake mode v1, captured command segments are transcribed locally only (no API fallback).
- Add explicit user toggle:
  - `wake_mode_enabled` (master on/off control).

## 15. Implementation Milestones
1. **M1**: Wake engine + state machine scaffolding.
2. **M2**: Endpointing and command capture integration.
3. **M3**: STT router with failover + prewarmed local model.
4. **M4**: Global hotkey manager + settings persistence.
5. **M5**: UI indicators + event logs + diagnostics.
6. **M6**: Soak testing + threshold tuning + docs.

## 16. Acceptance Criteria
- Wake detection arms consistently in active office conditions.
- Command utterances dispatch correctly on pause with <2.5s median arm->dispatch (local-first).
- Hotkeys execute reliably globally with no duplicate triggers.
- Wake mute blocks wake events instantly.
- Recovery flow returns to `IDLE_WAKE` automatically after transient errors.

## 17. Rollout Strategy
1. Internal canary:
  - enable always-on mode manually in settings.
2. Shadow logging:
  - run wake detection metrics without dispatch for baseline.
3. Controlled enablement:
  - enable dispatch for wake events with conservative sensitivity.
4. Full default enable (optional):
  - after stable false-positive rate and latency targets.

## 18. Open Decisions
- **Resolved**: no wake sensitivity setting in v1 (single dedicated microphone).
- **Resolved**: multiple wake phrases deferred to v1.1.
- **Resolved**: hotkey backend package is `pynput`.
- **Resolved**: wake mode uses local transcription only in v1 (no API fallback).
- **Resolved**: wake mode is user-toggleable on/off from Settings.
