# Always-On Wake Implementation Backlog

Source PRD: `plan/features/backlog/always-on-wake.md`

## Build Status
- Overall: in_progress
- Owner: Atlas engineering stack
- Priority: high

## Milestones
- M1 Wake engine + state machine scaffolding: in_progress
- M2 Endpointing + command capture integration: in_progress
- M3 STT routing (local wake mode, model prewarm): in_progress
- M4 Global hotkey manager + settings persistence: in_progress
- M5 UI indicators + logs/diagnostics: in_progress
- M6 Soak tests + tuning + docs: pending

## Task Queue
- [x] Add `wake_mode_enabled` setting and runtime toggle wiring.
- [x] Add `WakeController` state machine (`IDLE_WAKE`, `ARMED`, `CAPTURING`, `TRANSCRIBING`, `DISPATCHING`, `COOLDOWN`, `MUTED_WAKE`, `ERROR_RECOVERY`).
- [x] Implement `wake_engine.py` scaffolding (v1 lexical wake matcher; `openWakeWord` compatibility probe retained for upgrade path).
- [x] Integrate mic frame ingest path for wake detection loop.
- [x] Implement capture buffering + endpoint logic (VAD + trailing silence).
- [x] Add deterministic route for wake-command transcription: local-only in v1.
- [x] Prewarm local `faster-whisper small` for command utterance transcribe.
- [x] Add dispatch adapter from wake pipeline into existing Atlas turn flow.
- [x] Implement global `pynput` hotkey manager with action registry.
- [x] Wire 6 configurable bindings from settings.
- [x] Add hotkey conflict validation.
- [x] Add UI indicators for wake state and active route.
- [x] Add logs: `output/logs/wake_events.jsonl` and `output/logs/stt_metrics.jsonl`.
- [x] Add watchdog for stuck wake states and auto-reset behavior.
- [ ] Add QA soak script and baseline metrics collection.

## Acceptance Gate
- [ ] Wake phrase arms reliably on dedicated office mic.
- [ ] Pause endpointing reliably captures full command and dispatches.
- [ ] Wake mute blocks triggers immediately.
- [ ] Hotkeys are globally recognized and conflict-free.
- [ ] Local wake mode runs without API fallback in v1.
