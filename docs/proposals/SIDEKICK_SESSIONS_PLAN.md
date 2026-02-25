# Sidekick Sessions Plan

**Purpose**: Add sidekicks as helper agents for every bot (not just the leader) to keep room context light while enabling parallel, focused work.

**Philosophy**: The team is the main voice. Sidekicks are focused helpers that return results to their parent bot, which then reports to the room in its own voice.

---

## Goals

- Allow any bot to spawn 1+ sidekicks for a task.
- Keep room context conversational and clean.
- Pass only minimal task context to sidekicks.
- Return a merged summary and artifacts to the room via the parent bot.
- Preserve team personality in the main room (sidekicks do not speak there).

## Non-Goals

- Replace team bots with sidekicks.
- Add new user-facing commands for sidekicks in v1.
- Persist long-term sidekick sessions across restarts.

---

## Core Concept

- **Room**: Human-facing conversation + coordination.
- **Bot**: Owns a task, can split and delegate.
- **Sidekick**: Short-lived helper session with scoped context and output requirements.

---

## Architecture Overview

### New Concepts

- **SidekickTaskEnvelope**: Task brief passed to a sidekick.
- **SidekickSession**: A minimal session context used for a single task.
- **SidekickResult**: Summary + artifacts returned to parent bot.
- **SidekickOrchestrator**: Helper class for spawning, awaiting, and merging.

### Ownership Rules

- Sidekicks are always owned by a parent bot.
- Sidekicks never post directly to the room.
- Parent bot summarizes and reports to the room.

---

## Data Model

### SidekickTaskEnvelope

- `task_id`
- `parent_bot_id`
- `room_id`
- `goal`
- `inputs` (snippets, file paths, links)
- `constraints` (time, token budget, tools)
- `output_format` (summary, checklist, patch, etc.)

### SidekickResult

- `task_id`
- `status` (success, partial, failed)
- `summary`
- `artifacts` (files, snippets, links)
- `notes` (risks, follow-ups)

---

## Flow

1. Leader assigns a task to a bot.
2. Bot decides to split work.
3. Bot spawns N sidekicks in parallel.
4. Sidekicks work with minimal context.
5. Sidekicks return results to the bot.
6. Bot merges results into a final response.
7. Bot posts final response to the room.

---

## Context Strategy

- Sidekicks receive a **context packet**, not full room history.
- Context packet is built by parent bot:
  - Short problem statement
  - Relevant snippets or files
  - Required output format

---

## Limits and Controls

- `max_sidekicks_per_bot` (default: 3)
- `max_sidekicks_per_room` (default: 6)
- `sidekick_max_tokens` (default: smaller than main bots)
- `sidekick_timeout_seconds` (default: 120)
- Enforce limits at runtime; define behavior when limits are hit (reject, queue, or degrade).

---

## Tooling Integration

- Sidekicks can use tools based on parent bot permissions.
- Optional: restrict tool set to safe subset by default.
- Sidekicks must honor secret masking and protected path rules.

---

## Bot Instructions Update

- Add a **Sidekick Usage** section to bot internal templates (IDENTITY/ROLE/TEAM).
- Guidance should include:
  - When to split work into sidekicks.
  - How to write a context packet.
  - How to merge sidekick outputs.
  - How to report results back to the room in the bot’s voice.

--- 

## UI and UX

- Room only shows the parent bot response.
- Optional note in response: "(Used 2 sidekicks)".
- No user-facing sidekick commands initially.
- Show a **real-time status bar hint** while sidekicks run (e.g., "Activity: Marcus running 2 sidekicks...").

---

## Logging and Trace (No Room Context Impact)

- Sidekick logs are stored as **small traces** inside the parent bot work log.
- Each trace captures:
  - `task_id`, `parent_bot_id`, `status`, `duration`
  - `summary` (short)
  - `artifacts_count`
- Sidekick traces **do not** enter the room message history.
- Optional later: write a compact `sidekick_report.md` under the room workspace for audit/debug.

--- 

## Phased Implementation

### Phase 1: Core Types + Minimal Orchestrator

- Add `SidekickTaskEnvelope` and `SidekickResult` dataclasses.
- Add `SidekickOrchestrator` with spawn/await/merge utilities.
- Add config defaults for limits and budgets.
- Add guardrails: sidekicks cannot spawn sidekicks.

### Phase 2: BotInvoker Integration

- Allow bots to spawn sidekicks in the bot invoker flow.
- Add minimal context packet builder.
- Enforce context packet size limits.
- Ensure provider/model selection is deterministic (inherit from parent).

### Phase 3: Merge and Report

- Add a standard merge step in bots.
- Ensure final response only from parent bot.
- Handle partial failures and timeouts gracefully.
- Define deterministic merge order for multi-result summaries.

### Phase 4: Safety and Observability

- Add logging for sidekick creation and completion.
- Add failure handling and partial results.
- Add correlation IDs (`task_id`, `room_id`, `bot_id`) for traces.
- Ensure sidekick sessions are cleaned up after completion.

---

## Open Questions

- Should sidekicks have a distinct system prompt or just reuse bot prompt?
- Should sidekick results be stored in memory or only in the parent bot response?
- Do we allow sidekicks to spawn sub-sidekicks (no for v1)?
- What should happen when concurrency limits are hit (queue vs. degrade)?
- Should sidekicks ever use a cheaper model than the parent bot (future)?

---

## Failure Modes and Fallbacks

- If spawning fails: parent bot proceeds solo and reports fallback.
- If timeout occurs: return partial results with a note.
- If some sidekicks fail: merge what succeeded and mark missing coverage.

---

## Testing (Must-Haves)

- Concurrency cap enforcement (per bot and per room).
- Timeout handling and cleanup.
- Partial failure merge behavior.
- No sidekick messages appear in room history.

---

## Exit Criteria

- Any bot can spawn sidekicks and merge results.
- Room context stays clean with no sidekick messages.
- Sidekick limits and budgets are enforced.
- Parent bot always produces final response.
