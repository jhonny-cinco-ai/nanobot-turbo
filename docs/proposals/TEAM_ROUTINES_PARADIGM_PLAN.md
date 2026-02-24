# Team Routines Paradigm Plan

Note: In this document, **cron** refers to the internal routines scheduler engine, and **crew_routines** refers to the crew routines engine. Both are internal; user-facing terminology is **routines**.

**Status**: Proposed  
**Owner**: Nanofolks Core  
**Scope**: Python codebase (with direct path to Go port)

---

## Why This Plan

The current model is partially unified:
- `when` is mostly unified (scheduler/routines)
- `what` is still split (crew_routines files/checks vs scheduled jobs)

This creates a confusing mental model and a fragile backend. For Nanofolks' target users, this is too technical.

This plan defines a clean paradigm:
- One backend concept: `routines`
- One user-facing language: `team routines` and `your routines`
- Team "alive" behavior stays, but crew_routines/cron stop being first-class concepts

---

## Product Language (User-Facing)

- **Your routines**: user-owned reminders and recurring automations
- **Team routines**: system-owned proactive behaviors (alive/check-in behaviors)
- **Team energy**: proactive level (`quiet`, `balanced`, `active`) that adjusts team routine cadence

User-facing terms to remove:
- `cron`
- `crew_routines`

---

## Target Architecture

### 1) Single Routine Model

Every scheduled action uses one model:

- `id`
- `scope`: `user` | `system`
- `target_type`: `team` | `bot` | `room`
- `target_id`: e.g. `leader`, `researcher`, `project-alpha`
- `intent`: `reminder` | `check_in` | `maintenance` | `project_pulse` | ...
- `schedule`: one-time, interval, expression
- `payload`: message/action data
- `enabled`
- `metadata`

### 2) Single Runtime Pipeline

1. `RoutineStore` persists routines
2. `RoutineScheduler` computes due executions
3. `RoutineExecutor` executes by `intent + target`
4. `RoutineMetrics` emits unified telemetry

No separate runtime scheduler loops for crew_routines.

### 3) Team Alive Behavior

Team alive behavior is represented as `scope=system` routines:
- Can target whole team, specific bot, or room
- Are user-controllable (via chat/CLI), but remain system-owned
- Team energy modifies cadence defaults

---

## Backend Decisions

1. Keep one scheduling implementation
- Reuse existing scheduler internals as `routines` engine
- Remove duplicate scheduling paths

2. Remove split control planes
- No separate "crew_routines scheduler controls" vs "cron controls"
- One routines API for create/update/list/remove/enable/disable/run

3. Keep team identity docs focused on behavior, not timing
- Team/bot markdown docs define style and behavioral instructions
- Scheduling lives in routine records, not mixed across file types

4. No long-term dual-path compatibility
- Migration period allowed
- Final state has one truth only

---

## Implementation Phases

### Phase 1: Routine Domain Finalization

- Finalize shared routine schema (`scope`, `target_type`, `intent`)
- Introduce `RoutineService` naming at service boundary
- Add migration-capable storage versioning

### Phase 2: Team Routine Migration

- Convert current team alive jobs/checks into `scope=system` routines
- Route existing crew_routines tick execution through `RoutineExecutor`
- Keep behavior parity while removing separate timing loops

### Phase 3: Interface Unification

- Chat tools use a single routines tool surface
- CLI exposes `nanofolks routines ...` only
- Add team-energy controls in CLI/config/chat

### Phase 4: Legacy Removal

- Remove user-facing `crew_routines` and `cron` commands
- Remove duplicated scheduler pathways and stale metrics names
- Update docs, onboarding, and help text to routines terminology only

---

## Proposed Module Layout (Python)

- `nanofolks/routines/models.py`
- `nanofolks/routines/store.py`
- `nanofolks/routines/scheduler.py`
- `nanofolks/routines/executor.py`
- `nanofolks/routines/service.py`
- `nanofolks/routines/migrations.py`
- `nanofolks/agent/tools/routines.py`

De-emphasize and eventually retire:
- `nanofolks/routines_engine/*` (moved/aliased then removed)
- `nanofolks/crew_routines/*` scheduling responsibilities (execution logic may be reused under routines executor)

---

## Onboarding and Default Tasks

### CLI Onboarding Changes

- Remove `crew_routines` file creation during onboarding.
- Replace with routine defaults in the new `routines` store.
- Seed `team energy` as `balanced` by default during onboarding.
- Allow edits later via `nanofolks configure` or by AI request in CLI chat.

### Default Team Routines (Bootstrap)

On first run, seed a small set of system routines that make the team feel alive:

1. **Team Check-In**  
   - `scope=system`, `target_type=team`, `intent=check_in`  
   - Cadence: derived from team energy

2. **Room Pulse** (per active room)  
   - `scope=system`, `target_type=room`, `intent=project_pulse`  
   - Cadence: derived from team energy, with quiet hours honored

3. **Specialist Focus** (per bot)  
   - `scope=system`, `target_type=bot`, `intent=maintenance`  
   - Cadence: low frequency by default, adjusted by team energy

### Default User Routines

No user routines should be created automatically. They remain user-driven only.

---

## AI Behavior Contract

The assistant should infer operation type from plain language:

- "Remind me tomorrow at 6" -> create `scope=user` routine
- "Reduce team check-ins" -> update `scope=system` team routine cadence
- "Have researcher monitor competitors daily" -> create/update `scope=system`, `target_type=bot`, `target_id=researcher`

No user requirement to understand internal scheduler terms.

---

## Metrics and Observability

Replace split metric namespaces with unified names:

- `routines.job.started`
- `routines.job.completed`
- `routines.job.failed`
- `routines.jobs.total`
- `routines.team.executions`
- `routines.user.executions`

Dashboard and CLI metrics should group by `scope` and `target_type`.

---

## Risks and Mitigations

- Risk: behavior regressions in proactive team actions  
  Mitigation: parity tests for current team alive scenarios before cutover

- Risk: migration bugs causing missed jobs  
  Mitigation: migration dry-run validator + execution replay checks

- Risk: hidden terminology leaks (`cron`/`crew_routines`)  
  Mitigation: lint/check for forbidden user-facing terms in docs and CLI help

---

## Test Plan

1. Unit tests
- routine model validation
- schedule computation
- scope/target routing

2. Integration tests
- chat -> routines tool -> scheduler -> executor
- team routine execution for team/bot/room targets
- migration from legacy store

3. Docker smoke tests
- add/list/run/update/remove routines
- adjust team energy and verify cadence effects

---

## Implementation Checklist

| Item | Progress | Status |
|---|---|---|
| Final routine schema (`scope`, `target_type`, `intent`) | 0% | Not started |
| Routines service boundary finalized (`RoutineService`) | 0% | Not started |
| Team alive behaviors represented as `scope=system` routines | 0% | Not started |
| Unified routines tool for AI chat | 0% | Not started |
| CLI routines-only surface complete | 0% | Not started |
| Team energy control wired to cadence | 0% | Not started |
| Legacy runtime path removal (`cron`/crew_routines schedulers) | 0% | Not started |
| Metrics namespace migrated to `routines.*` | 0% | Not started |
| Docs/onboarding terminology cleanup complete | 0% | Not started |
| Docker and integration tests passing after cutover | 0% | Not started |

---

## Exit Criteria

- Users can manage both personal and team proactive behavior through one concept: routines
- Team remains "alive" with no crew_routines/cron mental model required
- Backend has one scheduler/runtime truth
- No split-path scheduling logic remains
