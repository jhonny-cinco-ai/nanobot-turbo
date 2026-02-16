"""OS Keyring integration for secure API key storage.

This module provides secure storage for API keys using the operating system's
native credential storage (macOS Keychain, Windows Credential Manager, or 
Linux Secret Service).

Usage:
    manager = KeyringManager()
    manager.store_key("openrouter", "sk-or-v1-...")
    key = manager.get_key("openrouter")
    manager.delete_key("openrouter")
"""

import keyring
from typing import Optional
from loguru import logger


SERVICE_NAME = "nanofolks.ai"


class KeyringManager:
    """Manages API keys in OS keyring.
    
    Provides a secure abstraction over platform-native credential storage.
    Keys stored in the keyring are never written to disk in plain text.
    """
    
    def __init__(self, service: str = SERVICE_NAME):
        """Initialize the keyring manager.
        
        Args:
            service: The service name for keyring entries (default: "nanofolks.ai")
        """
        self.service = service
    
    def store_key(self, provider: str, api_key: str) -> None:
        """Store API key in the OS keyring.
        
        Args:
            provider: Provider name (e.g., "openrouter", "anthropic")
            api_key: The API key to store securely
            
        Raises:
            keyring.errors.KeyringError: If keyring is unavailable
        """
        try:
            keyring.set_password(self.service, provider, api_key)
            logger.info(f"Stored API key for provider: {provider}")
        except keyring.errors.KeyringError as e:
            logger.error(f"Failed to store key in keyring: {e}")
            raise
    
    def get_key(self, provider: str) -> Optional[str]:
        """Retrieve API key from the OS keyring.
        
        Args:
            provider: Provider name (e.g., "openrouter", "anthropic")
            
        Returns:
            The API key if found, None otherwise
        """
        try:
            key = keyring.get_password(self.service, provider)
            return key
        except keyring.errors.KeyringError as e:
            logger.warning(f"Failed to retrieve key from keyring: {e}")
            return None
    
    def delete_key(self, provider: str) -> bool:
        """Delete API key from the OS keyring.
        
        Args:
            provider: Provider name to delete
            
        Returns:
            True if key was deleted, False if it didn't exist
        """
        try:
            keyring.delete_password(self.service, provider)
            logger.info(f"Deleted API key for provider: {provider}")
            return True
        except keyring.errors.KeyringError:
            return False
    
    def list_keys(self) -> list[str]:
        """List all provider names that have keys stored.
        
        Note: This is a best-effort enumeration and may not work
        on all platforms.
        
        Returns:
            List of provider names with stored keys
        """
        providers = ["anthropic", "openai", "openrouter", "deepseek", "groq", 
                     "zhipu", "dashscope", "gemini", "moonshot", "minimax",
                     "aihubmix", "brave"]
        
        stored = []
        for provider in providers:
            if self.get_key(provider):
                stored.append(provider)
        
        return stored
    
    def is_available(self) -> bool:
        """Check if the OS keyring is available.
        
        Returns:
            True if keyring is available and working, False otherwise
        """
        try:
            # Test with a temporary key
            test_key = "__nanofolks_test_key__"
            keyring.set_password(self.service, "__test__", test_key)
            retrieved = keyring.get_password(self.service, "__test__")
            keyring.delete_password(self.service, "__test__")
            
            return retrieved == test_key
        except Exception as e:
            logger.warning(f"Keyring not available: {e}")
            return False
    
    def has_key(self, provider: str) -> bool:
        """Check if a key exists for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            True if key exists, False otherwise
        """
        return self.get_key(provider) is not None


# Global instance for convenience
_default_keyring_manager: Optional[KeyringManager] = None


def get_keyring_manager() -> KeyringManager:
    """Get the global KeyringManager instance.
    
    Returns:
        The global KeyringManager instance
    """
    global _default_keyring_manager
    if _default_keyring_manager is None:
        _default_keyring_manager = KeyringManager()
    return _default_keyring_manager


def is_keyring_available() -> bool:
    """Check if keyring is available.
    
    Returns:
        True if keyring is available
    """
    return get_keyring_manager().is_available()
