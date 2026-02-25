# Web Search + Browser Upgrade Plan

**Purpose:** Add a robust fallback for hard pages and introduce an opt‑in browser tool for authenticated actions.

**Scope:** Python codebase (with a clean path to Go parity later).

**Non‑Goals:** Replace Brave search, build a full scraping product, or require a browser for all fetches.

---

## Current Behavior (Baseline)

- `web_search` uses Brave Search API.
- `web_fetch` uses `httpx + Readability` for extraction.
- No browser tool exists for login/post flows.

---

## Proposed Changes

### 1) Scrapling Fallback in `web_fetch`

**Goal:** Improve extraction on JS‑heavy or anti‑bot pages.

**Behavior:**
1. Try current `web_fetch` (httpx + Readability).
2. If extraction fails or content is too thin, fallback to Scrapling.
3. Scrapling chooses the lightest successful fetcher (HTTP → Stealth → Dynamic).

**Fallback criteria (v1):**
1. HTTP error or timeout from `web_fetch`.
2. Extracted text length below a threshold.
3. Readability returns empty or near‑empty content.

**Output:** Same `web_fetch` JSON payload fields, plus `extractor: "scrapling"` when used.

---

### 2) Agent‑Browser Tool (Opt‑In)

**Goal:** Enable authenticated actions (login/post) when the user explicitly asks.

**Behavior:**
1. Tool is **not** auto‑invoked.
2. The bot requests explicit confirmation for actions that require login or posting.
3. A per‑room session name is used for browser state.

**Session naming:**
- Format: `room:{room_id}`.
- This keeps cookies isolated per room and avoids cross‑room leaks.

**Confirmation rule:**
- Any action that writes data or logs in must ask the user first.

---

## User Experience

- Normal search stays fast with Brave.
- Hard pages automatically get stronger extraction.
- Auth workflows (social posting, dashboards) are possible via explicit user approval.

---

## Security and Privacy

- No automatic logins.
- Domain allowlist for agent‑browser sessions.
- Clear user confirmation before form submissions or posts.
- Per‑room session isolation.

---

## Configuration

Add to config:

| Config | Type | Default | Purpose |
|---|---|---|---|
| `tools.web.scrapling_enabled` | bool | false | Enable Scrapling fallback |
| `tools.web.scrapling_min_chars` | int | 800 | Threshold for thin content |
| `tools.web.scrapling_mode` | string | `auto` | `auto` / `stealth` / `dynamic` |
| `tools.browser.enabled` | bool | false | Enable agent‑browser tool |
| `tools.browser.allowlist` | list | [] | Allowed domains for browser tool |

---

## Implementation Plan (Phased)

### Phase 1: Scrapling Fallback
1. Add Scrapling dependency (optional extra if needed).
2. Add fallback logic to `web_fetch`.
3. Add config flags and defaults.
4. Add tests for fallback conditions.

### Phase 2: Agent‑Browser Tool
1. Implement a new tool wrapper (CLI call to agent‑browser).
2. Add per‑room session naming.
3. Add explicit confirmation flow.
4. Add allowlist enforcement.

---

## Tests

1. `web_fetch` returns Readability output when page is normal.
2. `web_fetch` falls back to Scrapling when content is thin or failed.
3. Agent‑browser tool refuses action without explicit confirmation.
4. Agent‑browser tool enforces allowlist.

---

## Rollout

1. Ship Scrapling behind config flag.
2. Ship agent‑browser behind config flag.
3. Enable per‑team or per‑workspace based on user preference.

---

## Open Questions

1. Which Scrapling fetchers should be enabled by default.
2. Whether agent‑browser runs as a daemon or per‑call.
3. How to surface browser session status in CLI UI.
