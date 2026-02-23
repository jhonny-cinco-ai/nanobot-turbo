# Broker Phase 2 — Per-Room Agent Loops

**Status:** Proposal (not yet implemented)  
**Depends on:** Broker Phase 1 (`bus.set_broker()` + `RoomBrokerManager` wired in gateway)  
**Author:** nanofolks engineering  
**Date:** 2026-02-22

---

## Motivation

Phase 1 gives each room a FIFO queue, but all rooms share a single
`AgentLoop`. That means:

- Room B's messages wait for Room A's LLM call to complete
- A slow room (e.g. one doing web search) blocks all other rooms
- Memory / session context is shared across rooms in the same loop instance

Phase 2 removes that bottleneck by giving each room its **own dedicated
`AgentLoop`**, so rooms process messages truly in parallel.

| | Phase 1 (current) | Phase 2 |
|---|---|---|
| Per-room FIFO | ✅ | ✅ |
| Parallel room processing | ❌ (sequential) | ✅ |
| Per-room session isolation | Partial | Full |
| Memory footprint | Low (1 loop) | Higher (N loops) |
| LLM connection overhead | 1× | 1× per active room |

---

## Design

### Core idea

`RoomMessageBroker` already has an `agent_loop` field and calls
`agent_loop.process_inbound(msg)`. Phase 1 injects the **same** loop into
every broker via `agent_loop_factory=lambda: agent`. Phase 2 changes the
factory to produce a **fresh `AgentLoop`** per room.

```
Phase 1:  all brokers → same AgentLoop instance
Phase 2:  broker(room-A) → AgentLoop-A
          broker(room-B) → AgentLoop-B
          broker(room-C) → AgentLoop-C
```

### `RoomBrokerManager` changes

Replace the shared `agent_loop_factory` with a **per-room factory** that
receives `room_id` so each loop can be tailored to its room:

```python
# New signature
class RoomBrokerManager:
    def __init__(
        self,
        room_agent_loop_factory: Callable[[str], AgentLoop],  # receives room_id
        storage=None,
    ): ...
```

When `route_message()` creates a new broker for an unknown room, it calls
`room_agent_loop_factory(room_id)` instead of the global lambda:

```python
async def route_message(self, message: MessageEnvelope) -> bool:
    room_id = message.room_id
    async with self._lock:
        if room_id not in self._brokers:
            loop = self.room_agent_loop_factory(room_id)   # ← per-room
            await loop._connect_mcp()                       # warm up
            broker = RoomMessageBroker(room_id=room_id)
            broker.set_agent_loop(loop)
            await broker.start()
            self._brokers[room_id] = broker
            self._loops[room_id] = loop
```

### `gateway()` changes

Build a factory closure that creates a fully-initialised `AgentLoop` for
any given room:

```python
def make_room_agent_loop(room_id: str) -> AgentLoop:
    return AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        # ... all other params same as today ...
        session_manager=create_session_manager(config.workspace_path, config),
        bot_name=f"leader-{room_id}",   # optional: distinct name per room
    )

broker_manager = RoomBrokerManager(
    room_agent_loop_factory=make_room_agent_loop,
)
bus.set_broker(broker_manager)
```

Remove `agent.run()` from `asyncio.gather()` — the global loop is no longer
needed (each broker owns its own, started on demand).

Keep the global `agent` for:
- Cron jobs (`on_cron_job` calls `agent.process_direct()`)
- CLI `chat` command (uses `process_direct()` directly, doesn't touch broker)

### Lifecycle and resource management

| Concern | Approach |
|---|---|
| Loop startup cost | Lazy: loop created on first message to that room |
| MCP connections | `_connect_mcp()` called once when broker creates the loop |
| Idle rooms | Add `RoomBrokerManager.evict_idle(timeout)` — stops broker + loop if no messages for N minutes |
| Graceful shutdown | `stop_all()` already stops all brokers; extend to also call `loop.stop()` per room |
| Memory pressure | Eviction + configurable `max_active_rooms` cap |

---

## Migration from Phase 1

Phase 1 and Phase 2 share the same public interface. The change is entirely
inside `RoomBrokerManager` and `gateway()`. No channel drivers, no
`BaseChannel`, no `MessageBus` changes needed.

**Steps:**
1. Update `RoomBrokerManager.__init__` to accept `room_agent_loop_factory`
   (keep `agent_loop_factory` as deprecated fallback for backward compatibility)
2. Update `gateway()` to pass `make_room_agent_loop` factory
3. Remove global `agent.run()` from `asyncio.gather()`
4. Add `evict_idle()` scheduling if desired
5. Add `max_active_rooms` guard to `route_message()`

---

## When to do this

Trigger Phase 2 when:
- 10+ concurrent rooms are regularly active simultaneously
- LLM latency for one room visibly affects response times in others
- Memory budget allows (each room loop holds session cache in RAM)

For most teams, **Phase 1 is sufficient** because rooms are rarely all
active at the same instant and the per-room FIFO already prevents
cross-room message interleaving.
