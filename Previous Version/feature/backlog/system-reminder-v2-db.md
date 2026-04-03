# System Reminder V2 (DB-backed + Keyword Rules) Feature Plan

## Context and Background
- Current system reminders are hardcoded in `atlas_ui.py` and injected every turn/action turn.
- This makes it difficult to:
  - add/update reminders without code edits,
  - scope reminders by keywords,
  - control priority/order,
  - audit changes over time.
- Goal: move reminders to a database-backed model queried before turn prompt construction.

## Feature Requirements
### Functional
1. Move system reminders into a persistent table.
2. Support two reminder modes:
- `always`: included every turn.
- `keyword`: included only when keyword/phrase rules match current user input (and/or action text).
3. Support enable/disable and priority ordering.
4. Add CRUD management in Settings UI:
- create reminder,
- edit title/body/mode/keywords/priority/enabled,
- delete reminder,
- test-match preview on sample input.
5. Keep one immutable fallback baseline reminder in code if DB is unavailable.
6. Show reminder debug panel in UI (optional toggle): which reminders were included for the turn.

### Non-Functional
- Query + assembly must be fast and non-blocking.
- Missing/corrupt reminder rows must not break turn execution.
- Reminder application order must be deterministic.

## Data Model
### Proposed Table: `system_reminders`
- `id` (PK)
- `name` (short label)
- `body` (full reminder text, supports XML-like tags)
- `mode` (`always` | `keyword`)
- `keywords_json` (array of keyword rules; empty for `always`)
- `match_scope` (`user_turn` | `action_turn` | `both`)
- `priority` (integer, lower first)
- `is_enabled` (bool)
- `created_at`
- `updated_at`
- `created_by` (optional)
- `updated_by` (optional)

### Keyword Rule Format (JSON)
```json
{
  "match_type": "contains",
  "value": "spotify",
  "case_sensitive": false
}
```
Supported `match_type` (V2):
- `contains`
- `regex` (guarded, safe timeout)

## Prompt Assembly (V2)
1. Build turn context (`user_text` and turn kind: user/action).
2. Query enabled reminders from DB.
3. Select applicable reminders:
- include all `always` matching scope,
- include `keyword` entries where any rule matches.
4. Sort by `priority`, then `id`.
5. Concatenate into one `<system_reminder_bundle>` block.
6. Inject bundle into prompt in place of current monolithic hardcoded reminder.
7. If DB read fails, use hardcoded fallback baseline reminder.

## UI/Settings CRUD
### Settings Additions
- New tab/section: `System Reminders`.
- Grid/list columns:
  - `Enabled`
  - `Name`
  - `Mode`
  - `Scope`
  - `Priority`
- Actions:
  - `Add`
  - `Edit`
  - `Clone`
  - `Delete`
  - `Test Match`

### Validation Rules
- `name` required.
- `body` required.
- `mode=keyword` requires at least one rule.
- duplicate priority allowed, stable tie-break by id.

## Architecture Decisions
- `Agreed`: Store reminders in DB table, not in flat files.
- `Agreed`: Keep fallback baseline reminder in code for resilience.
- `Agreed`: Include reminder matching for both user turns and action turns.
- `Proposed`: Add reminder change audit table in V2.1 if needed.

## Execution Plan
### Phase 1: Data + Service Layer
1. Add `system_reminders` table and lightweight repository methods.
2. Seed DB with current monolithic reminder as one `always` entry.
3. Add reminder retrieval + keyword matching utility.

### Phase 2: Prompt Integration
1. Replace `_system_reminder_text()` usage with DB-backed bundle builder.
2. Keep fallback path to legacy hardcoded text.
3. Add per-turn debug logging of matched reminder IDs/names.

### Phase 3: Settings CRUD
1. Add Settings UI panel for reminders.
2. Implement CRUD handlers with validation.
3. Add test-match preview tool in Settings panel.

### Phase 4: Hardening
1. Add tests for matching/order/fallback behavior.
2. Add migration/seed script.
3. Add docs and operator playbook.

## Acceptance Criteria
1. Operator can add a new `always` reminder in Settings and see it applied next turn without code changes.
2. Operator can add a `keyword` reminder (e.g., `spotify`) and it only appears on matching turns.
3. If reminder DB access fails, turn still executes with fallback baseline reminder.
4. Action turns apply reminders scoped to `action_turn`/`both`.

## Test Cases
| ID | Test | Type | Pass Criteria |
|---|---|---|---|
| SR2-T1 | Always reminder inclusion | Integration | Included on all user turns |
| SR2-T2 | Keyword reminder inclusion | Integration | Included only on matches |
| SR2-T3 | Scope filter | Integration | Action-only reminders excluded from user turns |
| SR2-T4 | Priority ordering | Unit | Deterministic reminder order |
| SR2-T5 | DB failure fallback | Integration | Hardcoded fallback is used, no turn crash |
| SR2-T6 | Settings CRUD | UI/Integration | Add/edit/delete persists and reflects immediately |

## Risks and Mitigations
- Risk: prompt bloat with too many reminders.
  - Mitigation: priority cap + max combined reminder size.
- Risk: over-broad keyword rules.
  - Mitigation: test-match preview and rule diagnostics.
- Risk: malformed regex.
  - Mitigation: validate/compile regex on save.

## Rollout and Rollback
### Rollout
1. Ship behind flag: `SYSTEM_REMINDER_V2_ENABLED`.
2. Seed with one baseline reminder.
3. Gradually split baseline into focused reminders.

### Rollback
- Disable `SYSTEM_REMINDER_V2_ENABLED` and use legacy `_system_reminder_text()` path.
