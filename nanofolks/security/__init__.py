"""Security module for nanofolks.

Provides security scanning and hardening features:
- Skill security scanning
- Secret detection and sanitization
- OS Keyring integration
- Symbolic key references (KeyVault)
- Secure memory buffers (SecureString)
- Audit logging with symbolic references
- Anomaly detection
"""

from nanofolks.security.skill_scanner import (
    SkillSecurityScanner,
    SecurityReport,
    SecurityFinding,
    Severity,
    scan_skill,
    format_report_for_cli,
)

from nanofolks.security.sanitizer import (
    SecretSanitizer,
    SecretMatch,
    sanitize,
    has_secrets,
    mask_logs,
)

from nanofolks.security.keyring_manager import (
    KeyringManager,
    get_keyring_manager,
    is_keyring_available,
)

from nanofolks.security.keyvault import (
    KeyVault,
    get_keyvault,
    resolve_key,
    PROVIDER_KEY_MAP,
)

from nanofolks.security.secure_memory import (
    SecureString,
    SecureMemory,
)

from nanofolks.security.audit_logger import (
    SecureAuditLogger,
    AuditEntry,
    get_audit_logger,
    log_tool_execution,
    log_api_call,
)

from nanofolks.security.anomaly_detector import (
    AnomalyDetector,
    Anomaly,
    get_anomaly_detector,
)


__all__ = [
    # Skill scanning
    "SkillSecurityScanner",
    "SecurityReport",
    "SecurityFinding", 
    "Severity",
    "scan_skill",
    "format_report_for_cli",
    
    # Sanitization
    "SecretSanitizer",
    "SecretMatch",
    "sanitize",
    "has_secrets",
    "mask_logs",
    
    # Keyring
    "KeyringManager",
    "get_keyring_manager",
    "is_keyring_available",
    
    # KeyVault
    "KeyVault",
    "get_keyvault",
    "resolve_key",
    "PROVIDER_KEY_MAP",
    
    # Secure Memory
    "SecureString",
    "SecureMemory",
    
    # Audit Logging
    "SecureAuditLogger",
    "AuditEntry",
    "get_audit_logger",
    "log_tool_execution",
    "log_api_call",
    
    # Anomaly Detection
    "AnomalyDetector",
    "Anomaly",
    "get_anomaly_detector",
]
