"""Symbolic credential conversion for secure message handling.

This module converts detected credentials in user messages to symbolic
references that are resolved at tool execution time.

Example:
    >>> converter = SymbolicConverter()
    >>> text = "Create repo with token ghp_abc123..."
    >>> result = converter.convert(text)
    >>> # result.text = "Create repo with token {{github_token}}..."
    >>> # result.credentials = [{'key_ref': 'github_token', 'value': 'ghp_abc123'}]
"""

from dataclasses import dataclass
from typing import Optional

from loguru import logger

from nanofolks.security.credential_detector import CredentialDetector, CredentialMatch
from nanofolks.security.secret_store import SecretStore, get_secret_store


@dataclass
class ConversionResult:
    """Result of converting credentials to symbolic references."""
    text: str
    credentials: list[dict]
    warnings: list[str]


class SymbolicConverter:
    """Converts detected credentials to symbolic references.

    This is the core of the credential protection system. It:
    1. Detects credentials in text
    2. Stores them securely in KeyVault
    3. Replaces them with symbolic references

    The LLM never sees the actual credentials.
    """

    def __init__(self):
        """Initialize the converter."""
        self.detector = CredentialDetector()
        self.store: SecretStore = get_secret_store()
        self._session_keys: dict[str, str] = {}  # Temporary session-based keys

    def convert(self, text: str, session_id: Optional[str] = None) -> ConversionResult:
        """Convert credentials in text to symbolic references.

        Args:
            text: The text containing credentials
            session_id: Optional session ID for temporary key scoping

        Returns:
            ConversionResult with converted text and stored credentials
        """
        if not text:
            return ConversionResult(text=text, credentials=[], warnings=[])

        # Detect credentials
        credentials = self.detector.detect(text)

        if not credentials:
            return ConversionResult(text=text, credentials=[], warnings=[])

        # Convert credentials to symbolic references
        converted_text = text
        stored_credentials = []
        warnings = []

        # Process from end to start to preserve positions
        for cred in reversed(credentials):
            # Generate symbolic reference
            key_ref = self._generate_key_ref(cred, session_id)

            # Store in session keys (temporary) or secret store
            self._store_credential(key_ref, cred.value, session_id)

            # Replace in text (from end to preserve positions)
            converted_text = (
                converted_text[:cred.start] +
                key_ref +
                converted_text[cred.end:]
            )

            stored_credentials.append({
                'key_ref': key_ref,
                'value': cred.value[:10] + '...',  # Only store preview
                'service': cred.service,
                'type': cred.credential_type
            })

            logger.debug(f"Converted {cred.credential_type} to {key_ref}")

        # Log warning about what was detected
        services = set(c.service for c in credentials)
        warnings.append(f"Credentials detected and converted: {', '.join(services)}")

        return ConversionResult(
            text=converted_text,
            credentials=stored_credentials,
            warnings=warnings
        )

    def _generate_key_ref(self, cred: CredentialMatch, session_id: Optional[str]) -> str:
        """Generate a symbolic reference for a credential.

        Args:
            cred: The credential match
            session_id: Optional session ID

        Returns:
            Symbolic reference like {{github_token}} or {{session_github_token}}
        """
        # For session-scoped keys, include a unique suffix
        if session_id:
            # Use short session ID
            session_suffix = session_id[:8]
            return f"{{{{{cred.service}_{cred.credential_type}_{session_suffix}}}}}"

        return f"{{{{{cred.service}_{cred.credential_type}}}}}"

    def _store_credential(self, key_ref: str, value: str, session_id: Optional[str]) -> None:
        """Store credential in session or secret store.

        Args:
            key_ref: The symbolic reference
            value: The actual credential value
            session_id: Optional session ID for scoping
        """
        # Extract key name from {{brackets}}
        key_name = key_ref.strip("{}")

        if session_id:
            # Store in session-scoped keys (temporary, in-memory)
            self._session_keys[key_name] = value
            logger.debug(f"Stored session key: {key_name}")
        else:
            # Ask user if they want to persist (for now, just log)
            logger.info(f"Credential detected: {key_name} (consider storing in secret store)")

    def resolve(self, key_ref: str, session_id: Optional[str] = None) -> Optional[str]:
        """Resolve a symbolic reference to its actual value.

        Args:
            key_ref: The symbolic reference (e.g., {{github_token}})
            session_id: Optional session ID

        Returns:
            The actual credential value, or None if not found
        """
        # Extract key name
        key_name = key_ref.strip("{}")

        # First check session keys
        if key_name in self._session_keys:
            return self._session_keys[key_name]

        # Then check secret store
        return self.store.get(key_name)

    def clear_session_keys(self, session_id: Optional[str] = None) -> None:
        """Clear session-scoped keys.

        Args:
            session_id: Optional specific session to clear, or None for all
        """
        if session_id:
            # Clear keys for specific session
            prefix = f"{session_id[:8]}_"
            keys_to_remove = [k for k in self._session_keys if prefix in k]
            for k in keys_to_remove:
                del self._session_keys[k]
        else:
            # Clear all session keys
            self._session_keys.clear()

    def is_symbolic_ref(self, value: str) -> bool:
        """Check if a value is a symbolic reference.

        Args:
            value: The value to check

        Returns:
            True if it's a symbolic reference
        """
        return value.strip().startswith("{{") and value.strip().endswith("}}")


# Global converter instance
_converter: Optional[SymbolicConverter] = None


def get_symbolic_converter() -> SymbolicConverter:
    """Get the global symbolic converter instance.

    Returns:
        The global SymbolicConverter instance
    """
    global _converter
    if _converter is None:
        _converter = SymbolicConverter()
    return _converter


def convert_to_symbolic(text: str, session_id: Optional[str] = None) -> ConversionResult:
    """Convenience function to convert credentials to symbolic references.

    Args:
        text: Text containing credentials
        session_id: Optional session ID

    Returns:
        ConversionResult with converted text
    """
    return get_symbolic_converter().convert(text, session_id)


def resolve_symbolic(key_ref: str, session_id: Optional[str] = None) -> Optional[str]:
    """Convenience function to resolve a symbolic reference.

    Args:
        key_ref: The symbolic reference
        session_id: Optional session ID

    Returns:
        The actual value
    """
    return get_symbolic_converter().resolve(key_ref, session_id)
