# Canvas Markdown Auto-Mode Plan

## Context
- Canvas payloads are currently handled as raw JSON body text, and markdown-like content appears as plain text.
- Atlas can emit structured canvas blocks that include markdown formatting and ASCII layouts.
- Current UX does not auto-switch rendering mode when markdown is detected/injected.

## Feature Requirements
- Detect markdown in canvas payload body automatically.
- If markdown is detected, switch canvas view to `markdown mode`.
- `Markdown mode` should use a light background for readability.
- Render markdown with:
  - headings, paragraphs, lists
  - fenced code blocks
  - inline code
  - basic emphasis and links
- Fallback to plain text mode when markdown is not detected.
- Preserve safety:
  - no arbitrary HTML/script execution
  - sanitize/strip unsupported tags

## User Stories
- As David, when Atlas returns a `<canvas>` payload containing markdown, I want it rendered like markdown without extra prompts.
- As David, when payload is plain text or structured text, I want normal canvas rendering and no accidental markdown transforms.
- As David, I want a clear visual distinction between plain canvas mode and markdown mode.

## Proposed Architecture
- `Agreed`: Keep the existing canvas payload ingestion path in `atlas_ui.py`.
- `Proposed`: Add a `CanvasRenderMode` decision function:
  - inputs: raw canvas body string
  - outputs: `plain` or `markdown`
- `Proposed`: Add markdown detector heuristics:
  - fenced code blocks (```), heading lines (`#`), bullet lines (`- ` / `* `), numbered lists, link patterns (`[x](y)`).
  - require a threshold score to avoid false positives.
- `Proposed`: Add markdown renderer pipeline:
  - preferred: lightweight parser library if already available in env
  - fallback: deterministic renderer for core markdown subset
- `Agreed`: Canvas markdown mode uses light background while app remains dark.

## Execution Plan
1. Add render-mode detection utility + tests for positive/negative samples.
2. Refactor canvas UI creation to route through `plain` vs `markdown` render handlers.
3. Implement markdown styling (fonts, spacing, code block frame, list indentation).
4. Add light-theme container style only for markdown canvas windows.
5. Add logging line in conversation/JSONL when mode auto-switch occurs.
6. Regression pass for existing canvas payloads and form-question payloads.

## Technical Notes
- Keep markdown render isolated so future rich modes can be added (e.g., table mode).
- Do not parse/execute raw HTML from markdown.
- Cap rendered payload size to prevent UI freeze on large markdown blobs.

## Test Cases
- Markdown body with headings + lists -> markdown mode, light background, formatted output.
- Body with single hyphen line only -> remain plain mode.
- Body with fenced code block only -> markdown mode and monospace block.
- Mixed plain + markdown text -> markdown mode.
- Very large markdown payload -> renders without lock-up (truncation warning if capped).
- Existing non-markdown canvas JSON -> unchanged behavior.

## Test Methodology
- Manual UI tests from real Atlas outputs in conversation.
- Unit tests for detection heuristic (true/false fixtures).
- Smoke test around canvas window open/close cycles and memory usage.

## Risks
- False-positive markdown detection on plain text.
- Missing markdown parser dependency on some machines.
- Rendering complexity causing inconsistent spacing.

## Mitigations
- Use conservative detection threshold and log selected mode.
- Keep parser optional with deterministic fallback.
- Keep renderer intentionally scoped to common markdown subset first.

## Acceptance Criteria
- Canvas markdown payloads auto-render in markdown mode with light background.
- Plain payloads remain plain mode.
- No executable HTML/JS surfaces.
- Existing canvas features keep working.
