# Local News + Weather Playbook

## Objective
Deliver a four-headline regional brief (White Mountains, NH + Connecticut) with authoritative sourcing, tool-efficient workflow, and handoff-ready artifacts (links list + narration audio).

## Preferred Sources To Pull First
1. **WMUR Storm Center** – evening commute + DOT advisories (NH local TV).
2. **NHPR / Concord Monitor** – policy + rescue coverage for White Mountains.
3. **NWS Gray / Caribou discussion** – NOAA zone text for North Conway + Pinkham Notch.
4. **Hartford Courant / CT Insider** – statewide infrastructure + commuting impacts.
5. **CT DOT / CT 511 RSS** – crash + roadway confirmation.
6. **WTNH / NBC CT** – quick video summaries if extra context needed.

Always cite at least two unique outlets per briefing (one NH-focused, one CT-focused), then layer any additional hits from the live search.

## Workflow
1. **Single search session**: use `web.run` once with two queries ("White Mountains NH news", "Connecticut weather commute") and parse headline candidates.
2. **Weather snapshots**: call the built-in `weather` tool for both coordinates simultaneously (`White Mountains, NH`, `Hartford, CT`).
3. **Forecast hook**: hit the NWS API (`https://api.weather.gov/points/{lat},{lon}` -> `forecastHourly`) to quote the next hazard or refreeze window; cite NOAA in the brief.
4. **Link buffer**: stage chosen headlines + URLs inside the notebook/response, then append all to `output/last_brief_links.md` in one write (see helper script below).
5. **Narration draft**: write the spoken paragraph to `tmp/news_brief.txt`; feed that file to the speech CLI to avoid massive inline command literals.
6. **Artifacts**: mention `last_brief_links.md` line numbers and the saved MP3 path in the response.

## Notes
- Stick to 3-4 total headlines; combine related CT commuter updates into one bullet where possible.
- Call out timestamps explicitly (e.g., "Updated 10:20 AM ET, Mar 4").
- If any DOT/511 feed lacks direct article URLs, cite the RSS item and mention "DOT alert".
- If weather is benign, still include overnight expectation from NWS so Dave knows about refreeze or wind shifts.

## Helper Script Reference
Use `scripts/append_brief_links.py` (added alongside this playbook) to take a JSON payload of `{title, url}` rows and append them cleanly to `output/last_brief_links.md` with a single command.
