"""Tests for the work logs system."""

import json
import pytest
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from nanobot.agent.work_log import WorkLog, WorkLogEntry, LogLevel, RoomType, WorkspaceType
from nanobot.agent.work_log_manager import WorkLogManager, get_work_log_manager, reset_work_log_manager


class TestLogLevel:
    """Test LogLevel enum."""
    
    def test_log_level_values(self):
        """Test that all log levels have correct values."""
        assert LogLevel.INFO.value == "info"
        assert LogLevel.THINKING.value == "thinking"
        assert LogLevel.DECISION.value == "decision"
        assert LogLevel.CORRECTION.value == "correction"
        assert LogLevel.UNCERTAINTY.value == "uncertainty"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.TOOL.value == "tool"


class TestWorkLogEntry:
    """Test WorkLogEntry dataclass."""
    
    def test_create_basic_entry(self):
        """Test creating a basic work log entry."""
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=1,
            category="test",
            message="Test message"
        )
        
        assert entry.step == 1
        assert entry.level == LogLevel.INFO
        assert entry.category == "test"
        assert entry.message == "Test message"
        assert entry.details == {}
        assert entry.confidence is None
        assert entry.duration_ms is None
    
    def test_create_entry_with_details(self):
        """Test creating entry with details and confidence."""
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.DECISION,
            step=2,
            category="routing",
            message="Classified as medium tier",
            details={"tier": "medium", "model": "gpt-4"},
            confidence=0.95,
            duration_ms=150
        )
        
        assert entry.confidence == 0.95
        assert entry.duration_ms == 150
        assert entry.details["tier"] == "medium"
    
    def test_is_tool_entry(self):
        """Test detecting tool entries."""
        regular_entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=1,
            category="general",
            message="Test"
        )
        
        tool_entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.TOOL,
            step=2,
            category="tool_execution",
            message="Executed web_search",
            tool_name="web_search",
            tool_input={"query": "test"},
            tool_output={"results": []},
            tool_status="success"
        )
        
        assert not regular_entry.is_tool_entry()
        assert tool_entry.is_tool_entry()
    
    def test_to_dict(self):
        """Test serialization to dict."""
        entry = WorkLogEntry(
            timestamp=datetime(2026, 2, 12, 10, 30, 0),
            level=LogLevel.DECISION,
            step=1,
            category="routing",
            message="Test",
            confidence=0.85
        )
        
        data = entry.to_dict()
        
        assert data["step"] == 1
        assert data["level"] == "decision"
        assert data["confidence"] == 0.85
        assert "timestamp" in data


class TestWorkLog:
    """Test WorkLog dataclass."""
    
    def test_create_work_log(self):
        """Test creating a work log."""
        log = WorkLog(
            session_id="test-session",
            query="Hello world",
            start_time=datetime.now()
        )
        
        assert log.session_id == "test-session"
        assert log.query == "Hello world"
        assert log.entries == []
        assert log.end_time is None
    
    def test_add_entry(self):
        """Test adding entries to work log."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now()
        )
        
        entry1 = log.add_entry(
            level=LogLevel.INFO,
            category="general",
            message="First entry"
        )
        
        entry2 = log.add_entry(
            level=LogLevel.DECISION,
            category="routing",
            message="Second entry",
            confidence=0.9
        )
        
        assert len(log.entries) == 2
        assert entry1.step == 1
        assert entry2.step == 2
        assert log.entries[0].message == "First entry"
        assert log.entries[1].message == "Second entry"
    
    def test_add_tool_entry(self):
        """Test adding tool entries."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now()
        )
        
        entry = log.add_tool_entry(
            tool_name="web_search",
            tool_input={"query": "test"},
            tool_output={"results": ["a", "b"]},
            tool_status="success",
            duration_ms=250
        )
        
        assert entry.is_tool_entry()
        assert entry.tool_name == "web_search"
        assert entry.level == LogLevel.TOOL
        assert entry.duration_ms == 250
    
    def test_get_entries_by_level(self):
        """Test filtering entries by level."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now()
        )
        
        log.add_entry(LogLevel.INFO, "test", "Info message")
        log.add_entry(LogLevel.ERROR, "test", "Error message")
        log.add_entry(LogLevel.INFO, "test", "Another info")
        
        info_entries = log.get_entries_by_level(LogLevel.INFO)
        error_entries = log.get_entries_by_level(LogLevel.ERROR)
        
        assert len(info_entries) == 2
        assert len(error_entries) == 1
    
    def test_get_entries_by_category(self):
        """Test filtering entries by category."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now()
        )
        
        log.add_entry(LogLevel.INFO, "routing", "Routing info")
        log.add_entry(LogLevel.INFO, "memory", "Memory info")
        log.add_entry(LogLevel.INFO, "routing", "More routing")
        
        routing_entries = log.get_entries_by_category("routing")
        
        assert len(routing_entries) == 2
    
    def test_get_errors(self):
        """Test getting error entries."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now()
        )
        
        log.add_entry(LogLevel.INFO, "test", "Info")
        log.add_entry(LogLevel.ERROR, "test", "Error 1")
        log.add_entry(LogLevel.ERROR, "test", "Error 2")
        
        errors = log.get_errors()
        
        assert len(errors) == 2
        assert all(e.level == LogLevel.ERROR for e in errors)
    
    def test_get_decisions(self):
        """Test getting decision entries."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now()
        )
        
        log.add_entry(LogLevel.INFO, "test", "Info")
        log.add_entry(LogLevel.DECISION, "routing", "Decision 1")
        log.add_entry(LogLevel.DECISION, "memory", "Decision 2")
        
        decisions = log.get_decisions()
        
        assert len(decisions) == 2
    
    def test_get_tool_calls(self):
        """Test getting tool call entries."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now()
        )
        
        log.add_entry(LogLevel.INFO, "test", "Info")
        log.add_tool_entry("tool1", {}, "result", "success", 100)
        log.add_tool_entry("tool2", {}, "result", "success", 200)
        
        tools = log.get_tool_calls()
        
        assert len(tools) == 2
    
    def test_get_duration_ms(self):
        """Test calculating duration."""
        start = datetime.now()
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=start
        )
        
        # Should be None while in progress
        assert log.get_duration_ms() is None
        
        # Set end time
        from datetime import timedelta
        log.end_time = start + timedelta(seconds=5)
        
        duration = log.get_duration_ms()
        assert duration is not None
        assert 4000 <= duration <= 6000  # Approximately 5 seconds
    
    def test_to_json(self):
        """Test JSON serialization."""
        log = WorkLog(
            session_id="test-session",
            query="test query",
            start_time=datetime.now()
        )
        
        log.add_entry(LogLevel.INFO, "test", "Test")
        log.end_time = datetime.now()
        log.final_output = "Test output"
        
        json_str = log.to_json()
        
        assert "test-session" in json_str
        assert "test query" in json_str
        assert "Test output" in json_str


class TestWorkLogManager:
    """Test WorkLogManager functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_work_logs.db"
            yield db_path
    
    @pytest.fixture
    def manager(self, temp_db):
        """Create a WorkLogManager with temp database."""
        reset_work_log_manager()
        mgr = WorkLogManager()
        mgr.db_path = temp_db
        mgr._init_db()
        return mgr
    
    def test_start_session(self, manager):
        """Test starting a work log session."""
        log = manager.start_session("test-session", "Test query")
        
        assert log.session_id == "test-session"
        assert log.query == "Test query"
        assert manager.current_log is not None
    
    def test_log_entry(self, manager):
        """Test logging an entry."""
        manager.start_session("test", "test")
        
        entry = manager.log(
            level=LogLevel.INFO,
            category="test",
            message="Test message"
        )
        
        assert entry is not None
        assert entry.step == 1
        assert len(manager.current_log.entries) == 1
    
    def test_log_tool(self, manager):
        """Test logging a tool execution."""
        manager.start_session("test", "test")
        
        entry = manager.log_tool(
            tool_name="web_search",
            tool_input={"query": "test"},
            tool_output={"results": []},
            tool_status="success",
            duration_ms=100
        )
        
        assert entry is not None
        assert entry.tool_name == "web_search"
        assert entry.tool_status == "success"
    
    def test_end_session(self, manager):
        """Test ending a work log session."""
        manager.start_session("test", "test")
        manager.log(LogLevel.INFO, "test", "Test")
        
        manager.end_session("Final output")
        
        assert manager.current_log is None
    
    def test_get_last_log(self, manager):
        """Test retrieving the last log."""
        # Create and end a session
        manager.start_session("session-1", "Query 1")
        manager.log(LogLevel.INFO, "test", "Entry 1")
        manager.end_session("Output 1")
        
        # Create another session
        manager.start_session("session-2", "Query 2")
        manager.log(LogLevel.INFO, "test", "Entry 2")
        manager.end_session("Output 2")
        
        # Get last log
        last_log = manager.get_last_log()
        
        assert last_log is not None
        assert last_log.session_id == "session-2"
        assert len(last_log.entries) == 1
    
    def test_get_log_by_session(self, manager):
        """Test retrieving a specific session."""
        manager.start_session("specific-session", "Specific query")
        manager.log(LogLevel.INFO, "test", "Test entry")
        manager.end_session("Test output")
        
        log = manager.get_log_by_session("specific-session")
        
        assert log is not None
        assert log.session_id == "specific-session"
        assert log.query == "Specific query"
    
    def test_get_formatted_log_summary(self, manager):
        """Test getting formatted summary."""
        manager.start_session("test", "Test query")
        manager.log(LogLevel.DECISION, "routing", "Classified as medium tier")
        manager.log_tool("web_search", {}, {"results": []}, "success", 150)
        manager.end_session("Test output")
        
        formatted = manager.get_formatted_log("summary")
        
        assert "Work Log Summary" in formatted
        assert "Test query" in formatted
        assert "medium tier" in formatted
    
    def test_get_formatted_log_detailed(self, manager):
        """Test getting detailed formatted log."""
        manager.start_session("test", "Test query")
        manager.log(LogLevel.INFO, "test", "Test entry")
        manager.end_session("Output")
        
        formatted = manager.get_formatted_log("detailed")
        
        assert "Detailed Work Log" in formatted
        assert "test" in formatted.lower()
    
    def test_disabled_logging(self, manager):
        """Test that disabled manager doesn't log."""
        disabled_manager = WorkLogManager(enabled=False)
        
        log = disabled_manager.start_session("test", "test")
        entry = disabled_manager.log(LogLevel.INFO, "test", "Test")
        
        # Should return dummy log but not save
        assert log is not None
        assert entry is None
    
    def test_multiple_sessions(self, manager):
        """Test handling multiple sessions."""
        for i in range(3):
            manager.start_session(f"session-{i}", f"Query {i}")
            manager.log(LogLevel.INFO, "test", f"Entry {i}")
            manager.end_session(f"Output {i}")
        
        # Get last should be session-2
        last = manager.get_last_log()
        assert last.session_id == "session-2"
    
    def test_log_persistence(self, manager):
        """Test that logs persist to database."""
        # Create first manager and log
        manager.start_session("persist-test", "Persist query")
        manager.log(LogLevel.INFO, "test", "Persist entry")
        manager.end_session("Persist output")
        
        # Create new manager instance (simulating restart)
        reset_work_log_manager()
        new_manager = WorkLogManager()
        new_manager.db_path = manager.db_path
        
        # Should retrieve the log
        log = new_manager.get_log_by_session("persist-test")
        
        assert log is not None
        assert log.query == "Persist query"
        assert len(log.entries) == 1


class TestWorkLogManagerFormatting:
    """Test WorkLogManager formatting functions."""
    
    @pytest.fixture
    def populated_manager(self):
        """Create a manager with a populated log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            reset_work_log_manager()
            mgr = WorkLogManager()
            mgr.db_path = db_path
            mgr._init_db()
            
            mgr.start_session("test", "Test query about Python programming")
            mgr.log(LogLevel.INFO, "general", "Processing user message")
            mgr.log(
                LogLevel.DECISION,
                "routing",
                "Classified as medium tier",
                details={"tier": "medium", "model": "gpt-4"},
                confidence=0.92,
                duration_ms=150
            )
            mgr.log(
                LogLevel.TOOL,
                "memory",
                "Retrieved 450 characters of memory context",
                duration_ms=80
            )
            mgr.log_tool(
                "web_search",
                {"query": "Python best practices"},
                {"results": ["PEP 8", "Clean Code"]},
                "success",
                230
            )
            mgr.log(
                LogLevel.WARNING,
                "general",
                "Low confidence on entity extraction",
                confidence=0.45
            )
            mgr.end_session("Here's what I found about Python...")
            
            yield mgr
    
    def test_summary_format(self, populated_manager):
        """Test summary format includes key decisions."""
        formatted = populated_manager.get_formatted_log("summary")
        
        assert "Work Log Summary" in formatted
        assert "Python programming" in formatted
        assert "medium tier" in formatted
        assert "web_search" in formatted
    
    def test_detailed_format(self, populated_manager):
        """Test detailed format includes all information."""
        formatted = populated_manager.get_formatted_log("detailed")
        
        assert "Detailed Work Log" in formatted
        assert "DECISION" in formatted
        assert "92%" in formatted or "0.92" in formatted
        assert "150ms" in formatted
    
    def test_debug_format(self, populated_manager):
        """Test debug format is valid JSON."""
        import json
        
        formatted = populated_manager.get_formatted_log("debug")
        
        # Should be valid JSON
        data = json.loads(formatted)
        assert "session_id" in data
        assert "entries" in data
        assert len(data["entries"]) == 5


class TestWorkLogIntegration:
    """Integration tests for work logs with other components."""
    
    @pytest.fixture
    def temp_manager(self):
        """Create a temporary manager for integration tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "integration.db"
            reset_work_log_manager()
            mgr = WorkLogManager()
            mgr.db_path = db_path
            mgr._init_db()
            yield mgr
            reset_work_log_manager()
    
    def test_full_session_lifecycle(self, temp_manager):
        """Test a complete session from start to finish."""
        # Start session
        log = temp_manager.start_session(
            "cli:test-session",
            "What's the weather in Tokyo?"
        )
        
        # Log routing decision
        temp_manager.log(
            LogLevel.DECISION,
            "routing",
            "Classified as simple tier",
            details={"tier": "simple", "model": "gpt-3.5"},
            confidence=0.95,
            duration_ms=120
        )
        
        # Log memory retrieval
        temp_manager.log(
            LogLevel.INFO,
            "memory",
            "No relevant memory found",
            duration_ms=50
        )
        
        # Log tool execution
        temp_manager.log_tool(
            "web_search",
            {"query": "Tokyo weather today"},
            {"temperature": "22°C", "condition": "sunny"},
            "success",
            340
        )
        
        # Log response
        temp_manager.log(
            LogLevel.INFO,
            "general",
            "Response generated successfully",
            details={"response_length": 150}
        )
        
        # End session
        temp_manager.end_session(
            "It's 22°C and sunny in Tokyo today!"
        )
        
        # Verify by retrieving
        retrieved = temp_manager.get_last_log()
        assert retrieved is not None
        assert retrieved.session_id == "cli:test-session"
        assert len(retrieved.entries) == 4
        assert "Tokyo" in retrieved.final_output
    
    def test_error_handling(self, temp_manager):
        """Test that errors don't break logging."""
        temp_manager.start_session("error-test", "Test")
        
        # Log an error
        temp_manager.log(
            LogLevel.ERROR,
            "tool_execution",
            "Tool web_search failed: Timeout",
            details={"error": "Timeout after 30s"}
        )
        
        temp_manager.end_session("Sorry, I encountered an error")
        
        # Should still be retrievable
        log = temp_manager.get_last_log()
        errors = log.get_errors()
        
        assert len(errors) == 1
        assert "Timeout" in errors[0].message


class TestGlobalWorkLogManager:
    """Test the global singleton work log manager."""
    
    def test_singleton_pattern(self):
        """Test that get_work_log_manager returns same instance."""
        reset_work_log_manager()
        
        mgr1 = get_work_log_manager()
        mgr2 = get_work_log_manager()
        
        assert mgr1 is mgr2
    
    def test_reset_creates_new_instance(self):
        """Test that reset creates a new instance."""
        mgr1 = get_work_log_manager()
        reset_work_log_manager()
        mgr2 = get_work_log_manager()
        
        assert mgr1 is not mgr2


class TestMultiAgentFields:
    """Test multi-agent extension fields in WorkLog and WorkLogEntry."""
    
    def test_work_log_entry_multi_agent_defaults(self):
        """Test that multi-agent fields have correct defaults for single-bot."""
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=1,
            category="test",
            message="Test message"
        )
        
        assert entry.workspace_id == "default"
        assert entry.workspace_type == RoomType.OPEN
        assert entry.participants == ["nanobot"]
        assert entry.bot_name == "nanobot"
        assert entry.bot_role == "primary"
        assert entry.triggered_by == "user"
        assert entry.coordinator_mode is False
        assert entry.escalation is False
        assert entry.mentions == []
        assert entry.response_to is None
        assert entry.shareable_insight is False
        assert entry.insight_category is None
    
    def test_work_log_entry_with_workspace_context(self):
        """Test creating entry with full workspace context."""
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=1,
            category="test",
            message="Test message",
            workspace_id="#project-refactor",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher", "coder"],
            bot_name="researcher",
            bot_role="specialist",
            triggered_by="@nanobot"
        )
        
        assert entry.workspace_id == "#project-refactor"
        assert entry.workspace_type == RoomType.PROJECT
        assert entry.participants == ["nanobot", "researcher", "coder"]
        assert entry.bot_name == "researcher"
        assert entry.bot_role == "specialist"
        assert entry.triggered_by == "@nanobot"
    
    def test_is_bot_conversation(self):
        """Test detecting bot-to-bot communication."""
        # User-triggered entry (not bot conversation)
        entry1 = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=1,
            category="test",
            message="User query",
            triggered_by="user"
        )
        assert entry1.is_bot_conversation() is False
        
        # Bot-triggered entry
        entry2 = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=2,
            category="test",
            message="Researcher responding",
            triggered_by="@researcher"
        )
        assert entry2.is_bot_conversation() is True
        
        # Coordinator mode entry
        entry3 = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.COORDINATION,
            step=3,
            category="coordination",
            message="Auto-delegating task",
            coordinator_mode=True
        )
        assert entry3.is_bot_conversation() is True
    
    def test_is_multi_agent_entry(self):
        """Test detecting multi-agent specific entries."""
        # Single-bot entry (defaults)
        entry1 = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=1,
            category="test",
            message="Test"
        )
        assert entry1.is_multi_agent_entry() is False
        
        # Multi-agent entry
        entry2 = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=2,
            category="test",
            message="Test",
            workspace_id="#project-alpha",
            participants=["nanobot", "researcher"]
        )
        assert entry2.is_multi_agent_entry() is True
    
    def test_work_log_with_workspace(self):
        """Test WorkLog with workspace context."""
        log = WorkLog(
            session_id="workspace-session",
            query="Refactor auth module",
            start_time=datetime.now(),
            workspace_id="#project-refactor",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher", "coder"],
            coordinator="nanobot"
        )
        
        assert log.workspace_id == "#project-refactor"
        assert log.workspace_type == RoomType.PROJECT
        assert log.coordinator == "nanobot"
        assert "researcher" in log.participants
    
    def test_add_entry_inherits_workspace_context(self):
        """Test that entries inherit workspace context from parent log."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now(),
            workspace_id="#project-alpha",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "coder"],
            coordinator="nanobot"
        )
        
        entry = log.add_entry(
            level=LogLevel.DECISION,
            category="routing",
            message="Delegating to coder",
            bot_name="nanobot",
            triggered_by="user"
        )
        
        assert entry.workspace_id == "#project-alpha"
        assert entry.workspace_type == RoomType.PROJECT
        assert "coder" in entry.participants
        assert entry.coordinator_mode is True
    
    def test_add_bot_message_multi_agent(self):
        """Test adding bot-to-bot messages."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now(),
            workspace_id="#project-refactor",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher", "coder"],
            coordinator="nanobot"
        )
        
        # Nanobot delegates to researcher
        entry = log.add_bot_message(
            bot_name="nanobot",
            message="@researcher Analyze auth security",
            mentions=["@researcher"],
            response_to=None
        )
        
        assert entry.category == "bot_conversation"
        assert "@researcher" in entry.mentions
        assert entry.bot_name == "nanobot"
        assert entry.triggered_by == "nanobot"
        assert entry.coordinator_mode is True
        
        # Researcher responds
        response = log.add_bot_message(
            bot_name="researcher",
            message="Found 2 security issues",
            response_to=entry.step,
            mentions=[]
        )
        
        assert response.response_to == entry.step
        assert response.bot_name == "researcher"
    
    def test_add_escalation(self):
        """Test adding escalation entries."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now(),
            workspace_id="#coordination-website",
            workspace_type=RoomType.COORDINATION,
            participants=["nanobot", "researcher", "coder", "creative"],
            coordinator="nanobot"
        )
        
        entry = log.add_escalation(
            reason="Design conflict between coder and creative",
            bot_name="nanobot"
        )
        
        assert entry.escalation is True
        assert entry.coordinator_mode is True
        assert entry.level == LogLevel.COORDINATION
        assert entry.category == "escalation"
    
    def test_get_entries_by_bot(self):
        """Test filtering entries by bot name."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now(),
            workspace_id="#project-alpha",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher"]
        )
        
        log.add_entry(LogLevel.INFO, "test", "Entry from nanobot", bot_name="nanobot")
        log.add_entry(LogLevel.INFO, "test", "Entry from researcher", bot_name="researcher")
        log.add_entry(LogLevel.INFO, "test", "Another from nanobot", bot_name="nanobot")
        
        nanobot_entries = log.get_entries_by_bot("nanobot")
        researcher_entries = log.get_entries_by_bot("researcher")
        
        assert len(nanobot_entries) == 2
        assert len(researcher_entries) == 1
    
    def test_get_bot_conversations(self):
        """Test getting bot-to-bot conversation entries."""
        log = WorkLog(
            session_id="test",
            query="test",
            start_time=datetime.now(),
            workspace_id="#project-alpha",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher"],
            coordinator="nanobot"
        )
        
        log.add_entry(LogLevel.INFO, "test", "User message", triggered_by="user")
        log.add_bot_message("nanobot", "@researcher Check this", mentions=["@researcher"])
        log.add_bot_message("researcher", "Got it", response_to=2)
        
        conversations = log.get_bot_conversations()
        
        # When coordinator_mode is active, all entries are considered bot conversations
        # In this case: user message (coordinator active), nanobot message, researcher message
        assert len(conversations) == 3
        
        # Verify the actual bot-to-bot messages
        bot_messages = [e for e in conversations if e.category == "bot_conversation"]
        assert len(bot_messages) == 2
    
    def test_to_dict_includes_multi_agent_fields(self):
        """Test that to_dict includes multi-agent fields."""
        entry = WorkLogEntry(
            timestamp=datetime(2026, 2, 12, 10, 0, 0),
            level=LogLevel.DECISION,
            step=1,
            category="routing",
            message="Delegated to specialist",
            workspace_id="#project-alpha",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher"],
            bot_name="researcher",
            bot_role="specialist",
            triggered_by="@nanobot",
            coordinator_mode=True,
            mentions=["@researcher"],
            shareable_insight=True,
            insight_category="task_delegation"
        )
        
        data = entry.to_dict()
        
        assert data["workspace_id"] == "#project-alpha"
        assert data["workspace_type"] == "project"
        assert data["participants"] == ["nanobot", "researcher"]
        assert data["bot_name"] == "researcher"
        assert data["bot_role"] == "specialist"
        assert data["triggered_by"] == "@nanobot"
        assert data["coordinator_mode"] is True
        assert data["mentions"] == ["@researcher"]
        assert data["shareable_insight"] is True
        assert data["insight_category"] == "task_delegation"


class TestMultiAgentPersistence:
    """Test persistence of multi-agent work logs."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_multi_agent.db"
            yield db_path
    
    @pytest.fixture
    def manager(self, temp_db):
        """Create a WorkLogManager with temp database."""
        reset_work_log_manager()
        mgr = WorkLogManager()
        mgr.db_path = temp_db
        mgr._init_db()
        return mgr
    
    def test_save_and_load_multi_agent_log(self, manager):
        """Test saving and loading a multi-agent log."""
        # Create log with workspace context
        log = WorkLog(
            session_id="multi-agent-test",
            query="Build website",
            start_time=datetime.now(),
            workspace_id="#project-website",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher", "coder", "creative"],
            coordinator="nanobot"
        )
        
        # Add entries with different bots
        log.add_entry(LogLevel.THINKING, "coordination", "Planning website build", bot_name="nanobot")
        log.add_bot_message("nanobot", "@researcher Analyze competitors", mentions=["@researcher"])
        log.add_bot_message("researcher", "Found 3 competitors with React", response_to=2)
        log.add_entry(LogLevel.DECISION, "coordination", "Choosing React stack", bot_name="nanobot", confidence=0.9)
        
        # Save to DB via manager - first create work_logs row with multi-agent fields
        manager.current_log = log
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                """INSERT INTO work_logs 
                   (id, session_id, query, start_time, workspace_id, workspace_type, participants_json, coordinator) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (log.session_id, log.session_id, log.query, log.start_time.isoformat(),
                 log.workspace_id, log.workspace_type.value, 
                 json.dumps(log.participants), log.coordinator)
            )
        
        for entry in log.entries:
            manager._save_entry(entry)
        
        log.end_time = datetime.now()
        log.final_output = "Website plan complete"
        
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                "UPDATE work_logs SET end_time = ?, final_output = ?, entry_count = ? WHERE session_id = ?",
                (log.end_time.isoformat(), log.final_output, len(log.entries), log.session_id)
            )
        
        # Load back
        loaded = manager.get_log_by_session("multi-agent-test")
        
        assert loaded is not None
        assert loaded.workspace_id == "#project-website"
        assert loaded.workspace_type == RoomType.PROJECT
        assert loaded.coordinator == "nanobot"
        assert "researcher" in loaded.participants
        assert len(loaded.entries) == 4
        
        # Check entry multi-agent fields
        entry = loaded.entries[1]  # Bot message
        assert entry.category == "bot_conversation"
        assert entry.bot_name == "nanobot"
        assert "@researcher" in entry.mentions
        
        # Check coordinator mode preserved
        coord_entry = loaded.entries[3]
        assert coord_entry.coordinator_mode is True
        assert coord_entry.confidence == 0.9
    
    def test_get_last_log_multi_agent(self, manager):
        """Test retrieving last log preserves multi-agent fields."""
        # Create first session (single-bot)
        log1 = WorkLog(
            session_id="single-bot",
            query="Simple query",
            start_time=datetime.now()
        )
        log1.add_entry(LogLevel.INFO, "test", "Test")
        
        # Use start_session to properly create DB entry
        manager.start_session("single-bot", "Simple query")
        manager.current_log = log1
        for entry in log1.entries:
            manager._save_entry(entry)
        manager.end_session("Done")
        
        # Create second session (multi-agent)
        log2 = WorkLog(
            session_id="multi-agent",
            query="Complex project",
            start_time=datetime.now(),
            workspace_id="#project-alpha",
            workspace_type=RoomType.PROJECT,
            participants=["nanobot", "researcher"],
            coordinator="nanobot"
        )
        log2.add_entry(LogLevel.INFO, "test", "Multi-agent test")
        
        # Use start_session to properly create DB entry
        manager.start_session("multi-agent", "Complex project")
        manager.current_log = log2
        
        # Update work_logs with multi-agent fields
        with sqlite3.connect(manager.db_path) as conn:
            conn.execute(
                """UPDATE work_logs 
                   SET workspace_id = ?, workspace_type = ?, participants_json = ?, coordinator = ?
                   WHERE session_id = ?""",
                (log2.workspace_id, log2.workspace_type.value, 
                 json.dumps(log2.participants), log2.coordinator, log2.session_id)
            )
        
        for entry in log2.entries:
            manager._save_entry(entry)
        manager.end_session("Done")
        
        # Get last should be multi-agent
        last = manager.get_last_log()
        
        assert last.session_id == "multi-agent"
        assert last.workspace_id == "#project-alpha"
        assert last.coordinator == "nanobot"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
