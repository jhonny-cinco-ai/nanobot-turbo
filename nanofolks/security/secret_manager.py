"""Unified secret manager for storage + symbolic resolution."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from nanofolks.security.keyvault import KeyVault
from nanofolks.security.secret_store import SecretStore, get_secret_store
from nanofolks.security.symbolic_converter import SymbolicConverter


class SecretManager:
    """Single entry point for secret storage and resolution."""

    def __init__(self, store: Optional[SecretStore] = None):
        self._store = store or get_secret_store()
        self._vault = KeyVault(self._store)
        self._converter = SymbolicConverter()

    def is_symbolic_ref(self, value: str) -> bool:
        return self._vault.is_symbolic_ref(value)

    def resolve_symbolic(self, value: str, session_id: Optional[str] = None) -> Optional[str]:
        return self._converter.resolve(value, session_id)

    def resolve_for_execution(self, value: str, session_id: Optional[str] = None) -> str:
        """Resolve a value that may be symbolic, provider name, or literal key."""
        if not value:
            return value
        if self.is_symbolic_ref(value):
            resolved = self.resolve_symbolic(value, session_id=session_id)
            if resolved:
                return resolved
        # Try provider-name lookup via keyvault; fall back to literal
        try:
            return self._vault.get_for_execution(value)
        except Exception:
            return value

    def store_key(self, key: str, value: str) -> None:
        self._store.set(key, value)

    def get_key(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def delete_key(self, key: str) -> bool:
        return self._store.delete(key)

    def list_keys(self) -> list[str]:
        return self._store.list_keys()

    def has_key(self, key: str) -> bool:
        return self._store.has(key)

    def convert_to_symbolic(self, text: str, session_id: Optional[str] = None):
        return self._converter.convert(text, session_id=session_id)


_default_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    global _default_secret_manager
    if _default_secret_manager is None:
        _default_secret_manager = SecretManager()
    return _default_secret_manager
