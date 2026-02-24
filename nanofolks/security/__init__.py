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

from nanofolks.security.anomaly_detector import (
    Anomaly,
    AnomalyDetector,
    get_anomaly_detector,
)
from nanofolks.security.audit_logger import (
    AuditEntry,
    SecureAuditLogger,
    get_audit_logger,
    log_api_call,
    log_tool_execution,
)
from nanofolks.security.keyring_manager import (
    KeyringManager,
    get_keyring_manager,
    is_keyring_available,
)
from nanofolks.security.keyvault import (
    PROVIDER_KEY_MAP,
    KeyVault,
    get_keyvault,
    resolve_key,
)
from nanofolks.security.secret_store import (
    KeyringSecretStore,
    SecretStore,
    get_secret_store,
)
from nanofolks.security.secret_manager import (
    SecretManager,
    get_secret_manager,
)
from nanofolks.security.sanitizer import (
    SecretMatch,
    SecretSanitizer,
    has_secrets,
    mask_logs,
    sanitize,
)
from nanofolks.security.secure_memory import (
    SecureMemory,
    SecureString,
)
from nanofolks.security.skill_scanner import (
    SecurityFinding,
    SecurityReport,
    Severity,
    SkillSecurityScanner,
    format_report_for_cli,
    scan_skill,
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

    # Secret Store
    "SecretStore",
    "KeyringSecretStore",
    "get_secret_store",
    "SecretManager",
    "get_secret_manager",

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
