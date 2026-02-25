---
title: "Local Client + Managed LLM Gateway (Thin UI Wrapper)"
status: "proposed"
owner: "nanofolks"
last_updated: "2026-02-25"
---

# Local Client + Managed LLM Gateway (Thin UI Wrapper)

## Summary
Ship a local, privacy‑preserving client that handles files, tools, and orchestration, while a managed backend provides LLM inference, model selection, and billing. The macOS Swift app is a thin UI wrapper around the local runtime.

## Goals
- Zero provider setup for the user.
- Keep file access and sensitive data local by default.
- Centralize model selection, quotas, and billing.
- Preserve current architecture and velocity (no full rewrite).

## Non‑Goals
- Full Swift rewrite of core orchestration.
- Server access to local files or direct OS resources.
- Multi‑tenant collaboration in v1.

## Core Components
**1) Local Runtime (existing core)**
- Runs the agent loop, tools, memory, routines, and broker.
- Owns file system access, shell execution, skills, and local APIs.
- Exposes a local IPC/HTTP API for the UI.

**2) Thin UI Wrapper (Swift)**
- Provides native UX, onboarding, and settings.
- Talks to the local runtime for status and local tool actions.
- Talks to the remote LLM gateway for auth/session management if needed.

**3) Managed LLM Gateway (cloud)**
- Owns model routing, provider selection, quotas, and billing.
- Provides inference API and usage reporting.
- Returns responses and tool calls; never accesses local files.

## Data Flow (Happy Path)
1. User enters prompt in macOS app.
2. UI sends prompt to local runtime.
3. Local runtime builds context from local files/memory and sanitizes secrets.
4. Local runtime calls LLM gateway with the prepared prompt and tool schema.
5. Gateway returns model response/tool calls.
6. Local runtime executes local tools and sends tool results back to gateway.
7. Final response returned to local runtime, then to UI.

## Security Model
- Local runtime is the only component with file/tool access.
- Gateway receives only the minimum necessary context (no raw file system access).
- Secrets are converted to symbolic references before leaving the device.
- All network calls use TLS; auth tokens are short‑lived and scoped.

## Billing & Quotas
- Gateway enforces usage limits per account.
- Client shows usage remaining and warnings.
- Model selection is fully server‑side for predictable costs.

## Product Tiering Options (Examples)
**Option A: Flat Monthly**
- One plan with a monthly token cap.
- Simple onboarding and predictable costs.

**Option B: Tiered Plans**
- Basic / Pro / Team with increasing token caps and faster models.
- Optional add‑ons for higher‑end models or longer context.

**Option C: Hybrid**
- Base plan with included tokens + usage overages.
- “Burst packs” for temporary capacity increases.

## Offline Behavior
- Local runtime can still operate for non‑LLM tasks (file ops, notes, local skills).
- LLM calls fail gracefully with a clear “offline” message.

## API Contracts (High Level)
**Local Runtime API**
- `POST /local/message` → process message via local runtime
- `GET /local/status` → health, queue depth, memory stats
- `POST /local/tools/run` → run approved local tool

**LLM Gateway API**
- `POST /llm/chat` → LLM completion
- `POST /llm/tool_result` → tool results for continuation
- `GET /llm/usage` → usage/limits

## API Contracts (Detailed, Proposed)
**Auth**
- `Authorization: Bearer <user_token>`
- Short‑lived access tokens with refresh.

**LLM Gateway**
- `POST /llm/chat`
  - Request: `session_id`, `messages`, `tools`, `tool_choice`, `metadata`, `client_caps`
  - Response: `message`, `tool_calls`, `usage`, `model`, `request_id`
- `POST /llm/tool_result`
  - Request: `session_id`, `tool_call_id`, `tool_name`, `result`
  - Response: `message`, `tool_calls`, `usage`, `model`, `request_id`
- `GET /llm/usage`
  - Response: `period`, `tokens_used`, `tokens_remaining`, `limit`, `reset_at`

**Local Runtime**
- `POST /local/message`
  - Request: `room_id`, `content`, `attachments`, `client_metadata`
  - Response: `message`, `room_state`, `context_usage`
- `POST /local/tools/run`
  - Request: `tool_name`, `args`, `approval_token`
  - Response: `result`, `status`
- `GET /local/status`
  - Response: `health`, `queue_depth`, `memory_stats`, `version`

## Gateway Provider Options (Reminder)
We can use OpenRouter or Vercel AI Gateway as the upstream LLM gateway. Both provide unified access with routing/fallback, but with different pricing and operational tradeoffs. citeturn0search2turn1search2

**OpenRouter (Pros)**
- Large model/provider catalog. citeturn0search3
- OpenAI‑compatible / drop‑in SDK support. citeturn1search6turn1search8
- Routing/fallback options for reliability. citeturn0search2
- Zero‑data‑retention (ZDR) controls available per request. citeturn1search9

**OpenRouter (Cons)**
- Platform fee (5.5%) on top of provider pricing. citeturn0search3

**Vercel AI Gateway (Pros)**
- Unified API with budgets, usage monitoring, load balancing, and automatic provider fallbacks. citeturn1search2
- No markup on list pricing and BYOK pricing. citeturn0search0turn0search7
- OpenAI‑compatible endpoints and SDK compatibility. citeturn1search1
- Public model discovery endpoint for dynamic model lists. citeturn1search0

**Vercel AI Gateway (Cons)**
- Billing is tied to Vercel AI Gateway credits (free tier then paid credits). citeturn0search0

## Why Thin UI Wrapper (vs Full Rewrite)
**Pros**
- Faster path to v1 with fewer regressions.
- Keeps parity with current behavior and tooling.
- Native UX without duplicating core logic.

**Cons**
- Two runtimes to ship (Swift UI + local core).
- Local runtime lifecycle management needed (start/stop/updates).

## Rollout Plan
1. Ship local runtime + Swift UI wrapper.
2. Add managed LLM gateway and switch inference to cloud.
3. Harden telemetry, quotas, and token accounting.
4. Iterate on native UX without core rewrites.
