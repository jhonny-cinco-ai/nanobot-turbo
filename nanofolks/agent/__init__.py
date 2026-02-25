"""Agent core module (lazy imports)."""

__all__ = [
    "AgentLoop",
    "ContextBuilder",
    "TurboMemoryStore",
    "SkillsLoader",
    "WorkLog",
    "WorkLogEntry",
    "LogLevel",
    "WorkLogManager",
    "get_work_log_manager",
    "SidekickTaskEnvelope",
    "SidekickResult",
    "SidekickOrchestrator",
    "SidekickLimitError",
]


def __getattr__(name: str):
    if name == "AgentLoop":
        from nanofolks.agent.loop import AgentLoop
        return AgentLoop
    if name == "ContextBuilder":
        from nanofolks.agent.context import ContextBuilder
        return ContextBuilder
    if name == "SkillsLoader":
        from nanofolks.agent.skills import SkillsLoader
        return SkillsLoader
    if name in {"WorkLog", "WorkLogEntry", "LogLevel"}:
        from nanofolks.agent.work_log import LogLevel, WorkLog, WorkLogEntry
        return {"WorkLog": WorkLog, "WorkLogEntry": WorkLogEntry, "LogLevel": LogLevel}[name]
    if name in {"WorkLogManager", "get_work_log_manager"}:
        from nanofolks.agent.work_log_manager import WorkLogManager, get_work_log_manager
        return {"WorkLogManager": WorkLogManager, "get_work_log_manager": get_work_log_manager}[name]
    if name == "TurboMemoryStore":
        from nanofolks.memory.store import TurboMemoryStore
        return TurboMemoryStore
    if name in {"SidekickTaskEnvelope", "SidekickResult", "SidekickOrchestrator", "SidekickLimitError"}:
        from nanofolks.agent.sidekicks import (
            SidekickLimitError,
            SidekickOrchestrator,
            SidekickResult,
            SidekickTaskEnvelope,
        )
        return {
            "SidekickTaskEnvelope": SidekickTaskEnvelope,
            "SidekickResult": SidekickResult,
            "SidekickOrchestrator": SidekickOrchestrator,
            "SidekickLimitError": SidekickLimitError,
        }[name]
    raise AttributeError(f"module 'nanofolks.agent' has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
