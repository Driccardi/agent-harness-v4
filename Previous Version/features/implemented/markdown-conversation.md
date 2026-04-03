# Markdown Conversation Rendering

## Context & Background
- Atlas UI currently writes plain text to the conversation pane; markdown syntax shows up literally, which hurts readability for summaries coming from tools and agents.
- Prior UI work (copy/paste, mic hotkeys) showed that improving the pane directly is high-leverage because every agent turn flows through it.
- Dave requested on 2026-03-04 for Atlas to both design and implement markdown support so richer formatting (bold, italics, code, lists, links) renders in the desktop app without breaking logs/export.

## Feature Requirements
### Functional
1. Parse agent/user output for a safe markdown subset: headings, bold/italic, inline/ block code, unordered + ordered lists, links, and blockquotes.
2. Render formatted text inside the existing `ctk.CTkTextbox` without flicker; new turns should stream in while preserving formatting for previous lines.
3. Maintain a plain-text copy for logs, session JSONL, and clipboard exports.
4. Provide a toggle in Settings so Dave can disable markdown rendering quickly if troubleshooting.

### Non-functional
- Zero additional latency beyond parsing overhead (<5 ms per turn on dev hardware).
- No external network calls; everything runs locally.
- Sanitization required: no HTML injection, no arbitrary file renders.

## User Stories / Acceptance Criteria
- As Dave, when Atlas answers with markdown (e.g., bullet lists, code blocks), I see the formatted result in the conversation pane immediately.
- Copying text out of the pane should yield the raw markdown (so pasted docs keep structure).
- When I disable the toggle and replay a turn, the output reverts to plain text.

## Technical Architecture
- **Agreed:** Use `markdown-it-py` to convert markdown -> a structured AST we control (no HTML rendering).  
- **Agreed:** Map AST nodes to Tk text tags (e.g., `tag_bold`, `tag_code`, `tag_link`) and predefine fonts/colors for each.
- **Proposed:** Cache parsed segments per turn so that rerenders (e.g., resizing window) do not re-parse.
- **Proposed:** Extend `log_conversation` so it writes to both the plain buffer and a new renderer helper that applies tags.
- **Agreed:** Settings toggle stored in `settings.json`; when disabled, renderer short-circuits to plain text.

## Execution Plan
1. **Parser/Rich Text Engine (0.5 day):**
   - Add `markdown_renderer.py` with helpers: `parse_segments(markdown_text) -> list[Segment]`.
   - Define supported tags + CTk textbox configurations (fonts, colors, spacing).
2. **UI Integration (0.5 day):**
   - Update `AtlasUI.log_conversation` to call renderer when toggle on; ensure streaming updates still append correctly.
   - Handle edge cases (multi-line code blocks, nested lists) by inserting newline + indent sequences.
3. **Settings & Persistence (0.25 day):**
   - Add checkbox to Settings pane, persist via `_save_settings`, and expose CLI flag for headless runs.
4. **Docs & Testing (0.25 day):**
   - README section describing supported markdown + how to disable.
   - Manual test script that dumps sample markdown into the pane.

## Technical Architecture Decisions (Agreed vs Proposed)
- **Agreed:** Rendering happens entirely inside Tk, so we avoid embedding a browser.
- **Agreed:** Links remain text-only but styled/underlined; clicking copies URL to clipboard (future enhancement).
- **Proposed:** Use a lightweight caching dict `{message_id: segments}` to avoid double parsing when reflowing text; revisit if memory becomes an issue.

## Test Cases
1. Bold/italic emphasis renders correctly alongside plain text.
2. Inline code uses monospaced font + background tint; block code preserves indentation.
3. Nested unordered lists indent properly and survive copy/paste.
4. Links display underlined text; copying yields `[label](url)` markdown.
5. Toggle off -> subsequent turns insert plain text; toggle on again -> new turns render formatted while old entries stay as inserted (acceptable).
6. Session JSONL + clipboard exports remain raw markdown.

## Test Methodology
- Manual: run `scripts/dev/inject_markdown.py` (to be added) to feed deterministic markdown examples; capture screenshots.
- Automated (future): unit-test parser by asserting AST -> segment mapping for sample markdown strings.

## Risks / Dependencies / Rollout
- **Risks:** Tk text widget tags can conflict if overlapping ranges aren''t applied carefully; need deterministic insertion order. Large messages might introduce slight lag; mitigate by chunking.
- **Dependencies:** `markdown-it-py` (add to `requirements.txt`).
- **Rollout:** ship behind toggle defaulting to ON (since Dave requested). If regressions appear, disable toggle or set `settings["markdown_chat"] = False`.
- **Rollback:** remove renderer helper and uninstall dependency; no persistent data migration required.
