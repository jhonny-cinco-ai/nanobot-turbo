# Security Enhancements Implementation Plan

**Version:** 1.0  
**Date:** 2026-02-16  
**Focus:** Critical Security Improvements (Items 1-4)

## Overview

This document outlines a detailed implementation plan for the four critical security enhancements:

1. **OS Keyring Integration** - Move API keys from plain text config to OS keyring
2. **Symbolic Key References** - Implement `{{provider_key}}` resolution at runtime  
3. **Secure Memory Buffers** - Protect keys in memory with locking and wiping
4. **Enhanced Audit Logging** - Log symbolic references only, add anomaly detection

---

## Phase 1: OS Keyring Integration

### Objective
Move API keys from `~/.nanofolks/config.json` (plain JSON) to OS-native secure storage (macOS Keychain, Windows Credential Manager, Linux Secret Service).

### Architecture

```
Current (Insecure):
┌──────────────────────────────────────┐
│  ~/.nanofolks/config.json            │
│  {                                   │
│    "providers": {                    │
│      "openrouter": {                 │
│        "api_key": "sk-or-v1-..."    │  ← EXPOSED
│      }                               │
│    }                                 │
│  }                                   │
└──────────────────────────────────────┘

Target (Secure):
┌──────────────────────────────────────┐
│  ~/.nanofolks/config.json            │
│  {                                   │
│    "providers": {                    │
│      "openrouter": {                 │
│        "api_key": "__KEYRING__"     │  ← REFERENCE ONLY
│      }                               │
│    }                                 │
│  }                                   │
└──────────────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│  OS Keyring                          │
│  nanofolks/openrouter → sk-or-v1-... │  ← SECURE
└──────────────────────────────────────┘
```

### Implementation

#### 1.1 Create Keyring Manager

**File:** `nanofolks/security/keyring_manager.py`

```python
"""OS Keyring integration for secure API key storage."""

import keyring
from typing import Optional
from dataclasses import dataclass

SERVICE_NAME = "nanofolks.ai"

class KeyringManager:
    """Manages API keys in OS keyring."""
    
    def __init__(self, service: str = SERVICE_NAME):
        self.service = service
    
    def store_key(self, provider: str, api_key: str) -> None:
        """Store API key in keyring."""
        keyring.set_password(self.service, provider, api_key)
    
    def get_key(self, provider: str) -> Optional[str]:
        """Retrieve API key from keyring."""
        return keyring.get_password(self.service, provider)
    
    def delete_key(self, provider: str) -> None:
        """Delete API key from keyring."""
        keyring.delete_password(self.service, provider)
    
    def is_available(self) -> bool:
        """Check if keyring is available."""
        try:
            keyring.set_password(self.service, "__test__", "test")
            keyring.delete_password(self.service, "__test__")
            return True
        except Exception:
            return False
```

#### 1.2 Update Config Loader

**File:** `nanofolks/config/loader.py`

**Changes:**
1. On config load: Check for `__KEYRING__` markers → resolve from keyring
2. On config save: If keyring available, store to keyring instead of file
3. Add migration function to move existing keys to keyring

```python
# New marker for keyring-stored keys
KEYRING_MARKER = "__KEYRING__"

def _resolve_keyring_keys(config: Config) -> Config:
    """Resolve __KEYRING__ markers to actual keys from OS keyring."""
    keyring_mgr = KeyringManager()
    
    for provider_name in ["anthropic", "openai", "openrouter", "deepseek", "groq"]:
        provider = getattr(config.providers, provider_name, None)
        if provider and provider.api_key == KEYRING_MARKER:
            actual_key = keyring_mgr.get_key(provider_name)
            if actual_key:
                provider.api_key = actual_key
    
    return config

def _migrate_to_keyring(config: Config) -> None:
    """Migrate existing plain-text keys to keyring."""
    keyring_mgr = KeyringManager()
    
    for provider_name in ["anthropic", "openai", "openrouter", "deepseek", "groq"]:
        provider = getattr(config.providers, provider_name, None)
        if provider and provider.api_key and provider.api_key != KEYRING_MARKER:
            keyring_mgr.store_key(provider_name, provider.api_key)
            provider.api_key = KEYRING_MARKER
```

#### 1.3 Add CLI Commands

**Commands to add:**
- `nanofolks security migrate-to-keyring` - Move existing keys
- `nanofolks security list-keys` - Show which keys are in keyring
- `nanofolks security remove-key <provider>` - Remove key from keyring

#### 1.4 Add Fallback Storage

For headless/server environments without keyring:

```python
class FallbackKeyStorage:
    """Encrypted file-based storage for servers."""
    
    def __init__(self, data_dir: Path):
        self.key_file = data_dir / ".keys.enc"
        self.master_key = self._derive_master_key()
    
    def _derive_master_key(self) -> bytes:
        """Derive key from machine ID (less secure than password)."""
        machine_id = subprocess.run(
            ["cat", "/etc/machine-id"], capture_output=True
        ).stdout.decode().strip()
        return hashlib.pbkdf2_hmac('sha256', machine_id.encode(), b'nanofolks', 100000)
```

### Test Plan

| Test | Description |
|------|-------------|
| Store/Retrieve | Test keyring store and retrieval |
| Migration | Verify keys migrate correctly |
| Fallback | Test file-based fallback when keyring unavailable |
| Permissions | Verify config file permissions remain 0600 |

---

## Phase 2: Symbolic Key References

### Objective
Implement `{{provider_key}}` symbolic references that resolve at execution time. LLMs see symbolic names, never actual keys.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  ZONE 1: LLM SEES                                         │
│  ├─ Tool descriptions: api_key="{{openrouter_key}}"         │
│  ├─ Context: Available keys: {{openrouter_key}}            │
│  └─ Prompt: Use {{brave_key}} for web search              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  ZONE 2: RESOLUTION AT EXECUTION                          │
│  ├─ ToolExecutor receives: api_key="{{openrouter_key}}"    │
│  ├─ Resolver looks up: {{openrouter_key}} → "sk-or-v1..." │
│  ├─ Makes API call with actual key                         │
│  └─ Key immediately wiped after use                        │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

#### 2.1 Create KeyVault Class

**File:** `nanofolks/security/keyvault.py`

```python
"""Secure key storage and symbolic reference resolution."""

import re
from typing import Optional
from dataclasses import dataclass
from nanofolks.security.keyring_manager import KeyringManager

# Pattern for symbolic references: {{key_name}}
SYMBOLIC_REF_PATTERN = re.compile(r'\{\{(\w+)\}\}')

class KeyVault:
    """Central secure storage for symbolic key references."""
    
    def __init__(self):
        self.keyring = KeyringManager()
        self._cache: dict[str, str] = {}  # Optional in-memory cache
    
    def get_for_execution(self, key_ref: str) -> str:
        """Resolve symbolic reference to actual key at execution time.
        
        Args:
            key_ref: Symbolic reference like "{{openrouter_key}}"
            
        Returns:
            Actual API key string
        """
        # Extract key name from {{brackets}}
        key_name = self._extract_key_name(key_ref)
        
        if not key_name:
            # Not a symbolic reference, return as-is (for debugging)
            return key_ref
        
        # Check cache first
        if key_name in self._cache:
            return self._cache[key_name]
        
        # Get from keyring
        actual_key = self.keyring.get_key(key_name)
        if not actual_key:
            raise ValueError(f"Key not found: {key_ref}")
        
        # Optionally cache for this request
        # self._cache[key_name] = actual_key
        
        return actual_key
    
    def _extract_key_name(self, value: str) -> Optional[str]:
        """Extract key name from {{key_name}} pattern."""
        match = SYMBOLIC_REF_PATTERN.match(value)
        return match.group(1) if match else None
    
    def is_symbolic_ref(self, value: str) -> bool:
        """Check if value is a symbolic reference."""
        return bool(SYMBOLIC_REF_PATTERN.match(value))
    
    def list_references(self) -> list[str]:
        """List all available symbolic key references."""
        # Return list of providers with keys in keyring
        providers = ["openrouter", "anthropic", "openai", "deepseek", "groq"]
        return [f"{{{{p}}}}" for p in providers if self.keyring.get_key(p)]
    
    def clear_cache(self) -> None:
        """Clear any cached keys from memory."""
        self._cache.clear()
```

#### 2.2 Update Tool Execution

**File:** `nanofolks/agent/tools/base.py`

```python
class BaseTool:
    """Base class for all tools with symbolic key resolution."""
    
    def __init__(self):
        self.keyvault = KeyVault()
    
    def _resolve_key(self, value: str) -> str:
        """Resolve symbolic key reference if present."""
        if self.keyvault.is_symbolic_ref(value):
            return self.keyvault.get_for_execution(value)
        return value
```

#### 2.3 Update WebSearchTool

**File:** `nanofolks/agent/tools/web_search.py`

```python
class WebSearchTool(BaseTool):
    """Web search with symbolic key support."""
    
    def __init__(self, api_key: str = "{{brave_key}}"):
        super().__init__()
        self.api_key = api_key  # Now a symbolic reference
    
    async def execute(self, params: dict) -> ToolResult:
        # Resolve key at execution time
        actual_key = self._resolve_key(self.api_key)
        
        try:
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Authorization": f"Bearer {actual_key}"},
                params=params
            )
        finally:
            # Key was in memory only briefly
            pass
        
        return ToolResult(success=True, data=response.json())
```

#### 2.4 Update Provider Configuration

**File:** `nanofolks/config/schema.py`

```python
class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""  # Can be literal key or "{{provider_key}}"
    
    @property
    def is_symbolic(self) -> bool:
        """Check if API key is a symbolic reference."""
        return self.api_key.startswith("{{") and self.api_key.endswith("}}")
```

#### 2.5 Update Context Builder

**File:** `nanofolks/agent/context.py`

```python
def build_system_prompt(self) -> str:
    """Build system prompt with symbolic key references."""
    # Show available keys symbolically
    available_keys = []
    for provider in ["openrouter", "anthropic", "openai"]:
        if self._has_key(provider):
            available_keys.append(f"- {provider}: {{{{{provider}_key}}}")
    
    return f"""# Available API Keys
When calling tools that require API keys, use these symbolic references:
{chr(10).join(available_keys)}

Example: To use web search, pass api_key="{{brave_key}}"
"""
```

### Test Plan

| Test | Description |
|------|-------------|
| Resolution | Verify `{{openrouter_key}}` resolves correctly |
| Context | Verify LLM sees symbolic refs, not actual keys |
| Tool Execution | Verify tools resolve keys at execution time |
| Fallback | Verify literal keys still work |

---

## Phase 3: Secure Memory Buffers

### Objective
Create `SecureString` class that protects API keys in memory with locking and explicit wiping.

### Implementation

#### 3.1 Create SecureString Class

**File:** `nanofolks/security/secure_memory.py`

```python
"""Secure memory allocation for sensitive data."""

import os
import ctypes
import threading
from typing import Optional

class SecureString:
    """Holds sensitive data in protected memory."""
    
    _instances: list = []
    _lock = threading.Lock()
    
    def __init__(self, value: str):
        """Create secure string from regular string."""
        self._value = value.encode('utf-8')
        self._size = len(self._value)
        
        # Lock memory to prevent swapping (Linux/macOS)
        try:
            import ctypes.util
            libc = ctypes.CDLL(ctypes.util.find_library('c'))
            libc.mlock(self._value, self._size)
        except Exception:
            pass  # Fall back if mlock not available
        
        with SecureString._lock:
            SecureString._instances.append(self)
    
    def get(self) -> str:
        """Get the actual string value."""
        return self._value.decode('utf-8')
    
    def wipe(self) -> None:
        """Overwrite memory with zeros and unlock."""
        # Overwrite with zeros
        ctypes.memset(ctypes.addressof(self._value), 0, self._size)
        
        # Unlock memory
        try:
            import ctypes.util
            libc = ctypes.CDLL(ctypes.util.find_library('c'))
            libc.munlock(self._value, self._size)
        except Exception:
            pass
        
        with SecureString._lock:
            if self in SecureString._instances:
                SecureString._instances.remove(self)
    
    def __del__(self):
        """Destructor ensures cleanup."""
        try:
            self.wipe()
        except Exception:
            pass
    
    @classmethod
    def wipe_all(cls) -> None:
        """Wipe all secure strings (emergency cleanup)."""
        with cls._lock:
            for instance in cls._instances[:]:
                instance.wipe()
```

#### 3.2 Update Provider to Use SecureString

**File:** `nanofolks/providers/litellm_provider.py`

```python
from nanofolks.security.secure_memory import SecureString

class LiteLLMProvider(LLMProvider):
    """LLM provider with secure key handling."""
    
    def __init__(self, api_key: str | None = None, ...):
        super().__init__(api_key, api_base)
        
        # Store key securely if provided
        if api_key:
            self._secure_key = SecureString(api_key)
            self.api_key = None  # Don't store plain text
        else:
            self._secure_key = None
    
    def _get_key(self) -> str | None:
        """Get key from secure storage."""
        if self._secure_key:
            return self._secure_key.get()
        return None
    
    def __del__(self):
        """Clean up secure key on destruction."""
        if hasattr(self, '_secure_key') and self._secure_key:
            self._secure_key.wipe()
```

#### 3.3 Update Tool Execution

```python
class SecureToolExecutor:
    """Executor that uses secure memory for keys."""
    
    def execute(self, tool: BaseTool, params: dict) -> ToolResult:
        try:
            return tool.execute(params)
        finally:
            # Emergency wipe all secure strings after tool execution
            SecureString.wipe_all()
```

### Memory Protection Flow

```
┌─────────────────────────────────────────────────────────────┐
│  OLD (Insecure):                                          │
│  api_key = "sk-or-v1-abc123"  →  Plain string in memory   │
│                            ↓                               │
│  Memory dump reveals: sk-or-v1-abc123                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  NEW (Secure):                                             │
│  api_key = SecureString("sk-or-v1-abc123")                 │
│                            ↓                               │
│  Memory locked (mlock) - cannot be swapped to disk        │
│                            ↓                               │
│  After use: .wipe() - overwrites with zeros                │
│                            ↓                               │
│  Memory dump reveals: \x00\x00\x00\x00\x00...             │
└─────────────────────────────────────────────────────────────┘
```

### Test Plan

| Test | Description |
|------|-------------|
| Lock/Unlock | Verify mlock/munlock called correctly |
| Wipe | Verify memory is zeroed after wipe |
| Thread Safety | Verify concurrent access is safe |
| Integration | Verify providers/tools use secure strings |

---

## Phase 4: Enhanced Audit Logging

### Objective
Implement audit logging that only logs symbolic references, with anomaly detection.

### Implementation

#### 4.1 Create Secure Audit Logger

**File:** `nanofolks/security/audit_logger.py`

```python
"""Secure audit logging with symbolic references only."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

@dataclass
class AuditEntry:
    """An audit log entry with symbolic references only."""
    timestamp: str
    operation: str
    key_ref: str  # Symbolic reference like {{openrouter_key}}
    success: bool
    duration_ms: int
    error: Optional[str] = None

class SecureAuditLogger:
    """Audit logger that never exposes actual keys."""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, operation: str, key_ref: str, success: bool, 
            duration_ms: int, error: Optional[str] = None) -> None:
        """Log an operation with symbolic key reference only."""
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation=operation,
            key_ref=key_ref,  # Always symbolic!
            success=success,
            duration_ms=duration_ms,
            error=error
        )
        
        # Append to log file (JSON Lines format)
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(asdict(entry)) + '\n')
    
    def log_tool_execution(self, tool_name: str, key_ref: str,
                          success: bool, duration_ms: int) -> None:
        """Log tool execution with symbolic key reference."""
        self.log(
            operation=f"tool.{tool_name}",
            key_ref=key_ref,
            success=success,
            duration_ms=duration_ms
        )
    
    def log_api_call(self, provider: str, key_ref: str,
                     success: bool, duration_ms: int, 
                     tokens_used: Optional[int] = None) -> None:
        """Log API call with symbolic key reference."""
        self.log(
            operation=f"api.{provider}",
            key_ref=key_ref,
            success=success,
            duration_ms=duration_ms
        )
```

#### 4.2 Add Anomaly Detection

**File:** `nanofolks/security/anomaly_detector.py`

```python
"""Anomaly detection for suspicious activity."""

from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class Anomaly:
    severity: str  # "low", "medium", "high"
    description: str
    key_ref: str

class AnomalyDetector:
    """Detects suspicious patterns in audit logs."""
    
    def __init__(self):
        self.request_counts: dict[str, list[datetime]] = defaultdict(list)
        self.error_counts: dict[str, int] = defaultdict(int)
    
    def check_request_rate(self, key_ref: str, 
                          max_per_minute: int = 60) -> Optional[Anomaly]:
        """Check for suspicious request rates."""
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        
        # Count requests in last minute
        recent = [t for t in self.request_counts[key_ref] if t > one_minute_ago]
        
        if len(recent) > max_per_minute:
            return Anomaly(
                severity="high",
                description=f"Request rate exceeded: {len(recent)}/min (limit: {max_per_minute})",
                key_ref=key_ref
            )
        
        self.request_counts[key_ref].append(now)
        return None
    
    def check_error_rate(self, key_ref: str,
                        max_errors: int = 5) -> Optional[Anomaly]:
        """Check for high error rates."""
        if self.error_counts[key_ref] > max_errors:
            return Anomaly(
                severity="medium",
                description=f"High error rate: {self.error_counts[key_ref]} errors",
                key_ref=key_ref
            )
        return None
    
    def check_large_response(self, key_ref: str, 
                            response_size_mb: float = 10.0) -> Optional[Anomaly]:
        """Check for unusually large responses (potential data exfiltration)."""
        # This would be called when processing responses
        # Implementation depends on tracking response sizes
        return None
```

#### 4.3 Integrate with Tools

```python
class AuditedToolExecutor:
    """Tool executor with audit logging."""
    
    def __init__(self):
        self.audit = SecureAuditLogger(Path.home() / ".nanofolks" / "audit.log")
        self.anomaly = AnomalyDetector()
    
    async def execute(self, tool: BaseTool, params: dict) -> ToolResult:
        start = datetime.utcnow()
        
        # Get symbolic key reference for audit
        key_ref = tool.get_key_ref()  # Returns "{{provider_key}}"
        
        try:
            result = await tool.execute(params)
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            
            self.audit.log_tool_execution(
                tool_name=tool.name,
                key_ref=key_ref,
                success=True,
                duration_ms=int(duration)
            )
            
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            
            self.audit.log_tool_execution(
                tool_name=tool.name,
                key_ref=key_ref,
                success=False,
                duration_ms=int(duration),
                error=str(e)
            )
            
            # Check for anomalies
            anomaly = self.anomaly.check_error_rate(key_ref)
            if anomaly:
                self._alert(anomaly)
            
            raise
```

### Audit Log Example

```json
{"timestamp": "2026-02-16T10:30:00Z", "operation": "tool.web_search", "key_ref": "{{brave_key}}", "success": true, "duration_ms": 245}
{"timestamp": "2026-02-16T10:30:01Z", "operation": "api.openrouter", "key_ref": "{{openrouter_key}}", "success": true, "duration_ms": 1200}
{"timestamp": "2026-02-16T10:30:05Z", "operation": "tool.read_file", "key_ref": "{{openrouter_key}}", "success": false, "duration_ms": 45, "error": "File not found"}

Notice: Actual API keys NEVER appear in logs!
```

### Test Plan

| Test | Description |
|------|-------------|
| Symbolic Only | Verify logs contain no actual keys |
| Anomaly Detection | Verify rate limiting and error alerts |
| Integration | Verify tools and providers log correctly |
| Query | Verify audit logs can be queried for debugging |

---

## Implementation Timeline

### Week 1: OS Keyring Integration

| Day | Task |
|-----|------|
| 1-2 | Create KeyringManager class |
| 3 | Update config loader with keyring resolution |
| 4 | Add CLI migration commands |
| 5 | Add fallback storage, testing |

### Week 2: Symbolic Key References

| Day | Task |
|-----|------|
| 1-2 | Create KeyVault class |
| 2-3 | Update tool base classes |
| 3-4 | Update WebSearchTool and providers |
| 4-5 | Update context builder, testing |

### Week 3: Secure Memory Buffers

| Day | Task |
|-----|------|
| 1-2 | Create SecureString class |
| 3 | Update LiteLLMProvider |
| 4 | Update tool execution |
| 5 | Integration testing |

### Week 4: Enhanced Audit Logging

| Day | Task |
|-----|------|
| 1-2 | Create SecureAuditLogger |
| 2-3 | Implement AnomalyDetector |
| 3-4 | Integrate with tools/providers |
| 5 | Testing, documentation |

---

## Dependencies

| Dependency | Purpose | Package |
|------------|---------|---------|
| Keyring | Cross-platform keyring access | `keyring` |
| ctypes | Low-level memory operations | Built-in |
| threading | Thread-safe cleanup | Built-in |

---

## Success Criteria

1. **Keyring Integration**: ✅ COMPLETED - Keys stored in OS keyring, not config file
2. **Symbolic References**: ✅ COMPLETED - LLMs never see actual API keys
3. **Secure Memory**: ✅ COMPLETED - Keys wiped after use, memory locked
4. **Audit Logs**: ✅ COMPLETED - Only symbolic references logged, anomaly detection works

---

**Document Status:** ✅ COMPLETED  
**Completed:** 2026-02-16  
**Commit:** fccaa01 - Add security enhancements: keyring, KeyVault, SecureString, audit logging

## Implementation Summary

All four phases have been implemented:

| Phase | Feature | Status | Files |
|-------|---------|--------|-------|
| 1 | OS Keyring Integration | ✅ | `security/keyring_manager.py`, `config/loader.py`, `cli/security_commands.py` |
| 2 | Symbolic Key References | ✅ | `security/keyvault.py`, `agent/tools/web.py`, `agent/context.py` |
| 3 | Secure Memory Buffers | ✅ | `security/secure_memory.py`, `providers/litellm_provider.py` |
| 4 | Enhanced Audit Logging | ✅ | `security/audit_logger.py`, `security/anomaly_detector.py` |
