"""Secure audit logging with symbolic references only.

This module provides audit logging that NEVER exposes actual API keys.
All logs use symbolic references like {{openrouter_key}} instead of
actual key values.

Key Principle:
    - Logs should be safe to share, store, or analyze
    - Actual keys never appear in logs
    - Use symbolic references for tracking key usage
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class AuditEntry:
    """An audit log entry with symbolic references only.
    
    IMPORTANT: This class NEVER stores actual API keys.
    All key references are symbolic like {{openrouter_key}}.
    """
    timestamp: str
    operation: str
    key_ref: str  # Symbolic reference like {{openrouter_key}}
    success: bool
    duration_ms: int
    error: Optional[str] = None
    details: Optional[dict] = None


class SecureAuditLogger:
    """Audit logger that never exposes actual API keys.
    
    This logger provides defense-in-depth by ensuring that even if
    audit logs are compromised, no actual API keys are exposed.
    
    Example:
        >>> audit = SecureAuditLogger()
        >>> audit.log_tool_execution(
        ...     tool_name="web_search",
        ...     key_ref="{{brave_key}}",  # Never actual key!
        ...     success=True,
        ...     duration_ms=245
        ... )
        
    Log output:
        {"timestamp": "2026-02-16T10:30:00Z", "operation": "tool.web_search", 
         "key_ref": "{{brave_key}}", "success": true, "duration_ms": 245}
    """
    
    def __init__(self, log_path: Optional[Path] = None):
        """Initialize the secure audit logger.
        
        Args:
            log_path: Path to the audit log file. Defaults to ~/.nanofolks/audit.log
        """
        if log_path is None:
            log_path = Path.home() / ".nanofolks" / "audit.log"
        
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _write_entry(self, entry: AuditEntry) -> None:
        """Write an entry to the audit log.
        
        Args:
            entry: The audit entry to write
        """
        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(asdict(entry)) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def log(self, operation: str, key_ref: str, success: bool, 
            duration_ms: int, error: Optional[str] = None,
            details: Optional[dict] = None) -> None:
        """Log an operation with symbolic key reference only.
        
        IMPORTANT: key_ref must be a symbolic reference like {{openrouter_key}},
        not an actual API key.
        
        Args:
            operation: The operation being performed (e.g., "tool.web_search")
            key_ref: Symbolic key reference like {{openrouter_key}}
            success: Whether the operation succeeded
            duration_ms: How long the operation took in milliseconds
            error: Optional error message if failed
            details: Additional details about the operation
        """
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            operation=operation,
            key_ref=key_ref,  # Always symbolic!
            success=success,
            duration_ms=duration_ms,
            error=error,
            details=details
        )
        
        self._write_entry(entry)
    
    def log_tool_execution(self, tool_name: str, key_ref: str,
                          success: bool, duration_ms: int,
                          error: Optional[str] = None) -> None:
        """Log tool execution with symbolic key reference.
        
        Args:
            tool_name: Name of the tool being executed
            key_ref: Symbolic key reference like {{brave_key}}
            success: Whether the tool executed successfully
            duration_ms: Execution time in milliseconds
            error: Optional error message
        """
        self.log(
            operation=f"tool.{tool_name}",
            key_ref=key_ref,
            success=success,
            duration_ms=duration_ms,
            error=error
        )
    
    def log_api_call(self, provider: str, key_ref: str,
                     success: bool, duration_ms: int,
                     error: Optional[str] = None,
                     tokens_used: Optional[int] = None) -> None:
        """Log an API call with symbolic key reference.
        
        Args:
            provider: Provider name (e.g., "openrouter", "anthropic")
            key_ref: Symbolic key reference like {{openrouter_key}}
            success: Whether the API call succeeded
            duration_ms: Call duration in milliseconds
            error: Optional error message
            tokens_used: Optional number of tokens used
        """
        details = {"tokens_used": tokens_used} if tokens_used else None
        
        self.log(
            operation=f"api.{provider}",
            key_ref=key_ref,
            success=success,
            duration_ms=duration_ms,
            error=error,
            details=details
        )
    
    def log_key_operation(self, operation: str, key_ref: str,
                          success: bool, 
                          details: Optional[dict] = None) -> None:
        """Log a key management operation.
        
        Args:
            operation: The key operation (e.g., "key.store", "key.retrieve")
            key_ref: Symbolic key reference
            success: Whether the operation succeeded
            details: Additional details
        """
        self.log(
            operation=operation,
            key_ref=key_ref,
            success=success,
            duration_ms=0,  # Key ops are typically fast
            details=details
        )
    
    def get_entries(self, limit: int = 100) -> list[AuditEntry]:
        """Get recent audit entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of audit entries (most recent first)
        """
        if not self.log_path.exists():
            return []
        
        entries = []
        try:
            with open(self.log_path, 'r') as f:
                lines = f.readlines()
            
            for line in reversed(lines[-limit:]):
                try:
                    data = json.loads(line.strip())
                    entries.append(AuditEntry(**data))
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
        
        return entries


# Global audit logger instance
_audit_logger: Optional[SecureAuditLogger] = None


def get_audit_logger() -> SecureAuditLogger:
    """Get the global audit logger instance.
    
    Returns:
        The global SecureAuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecureAuditLogger()
    return _audit_logger


def log_tool_execution(tool_name: str, key_ref: str, 
                       success: bool, duration_ms: int,
                       error: Optional[str] = None) -> None:
    """Convenience function for logging tool execution.
    
    Args:
        tool_name: Name of the tool
        key_ref: Symbolic key reference
        success: Whether execution succeeded
        duration_ms: Execution time
        error: Optional error message
    """
    get_audit_logger().log_tool_execution(tool_name, key_ref, success, duration_ms, error)


def log_api_call(provider: str, key_ref: str,
                 success: bool, duration_ms: int,
                 error: Optional[str] = None,
                 tokens_used: Optional[int] = None) -> None:
    """Convenience function for logging API calls.
    
    Args:
        provider: Provider name
        key_ref: Symbolic key reference  
        success: Whether call succeeded
        duration_ms: Call duration
        error: Optional error message
        tokens_used: Optional tokens used
    """
    get_audit_logger().log_api_call(provider, key_ref, success, duration_ms, error, tokens_used)
