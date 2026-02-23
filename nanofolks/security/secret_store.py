"""Unified secret storage interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from nanofolks.security.keyring_manager import KeyringManager, get_keyring_manager


class SecretStore(ABC):
    """Abstract interface for secret storage."""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Retrieve a secret by key."""
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store a secret by key."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a secret by key."""
        raise NotImplementedError

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all known secret keys."""
        raise NotImplementedError

    @abstractmethod
    def has(self, key: str) -> bool:
        """Check if a secret exists."""
        raise NotImplementedError


class KeyringSecretStore(SecretStore):
    """SecretStore backed by OS keyring via KeyringManager."""

    def __init__(self, manager: Optional[KeyringManager] = None):
        self._manager = manager or get_keyring_manager()

    def get(self, key: str) -> Optional[str]:
        return self._manager.get_key(key)

    def set(self, key: str, value: str) -> None:
        self._manager.store_key(key, value)

    def delete(self, key: str) -> bool:
        return self._manager.delete_key(key)

    def list_keys(self) -> list[str]:
        return self._manager.list_keys()

    def has(self, key: str) -> bool:
        return self._manager.has_key(key)


_default_secret_store: Optional[SecretStore] = None


def get_secret_store() -> SecretStore:
    """Get the global SecretStore instance."""
    global _default_secret_store
    if _default_secret_store is None:
        _default_secret_store = KeyringSecretStore()
    return _default_secret_store

