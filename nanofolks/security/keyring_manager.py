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

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

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
            RuntimeError: If keyring is unavailable
        """
        if not KEYRING_AVAILABLE:
            raise RuntimeError("keyring package not installed. Run: pip install keyring")

        try:
            keyring.set_password(self.service, provider, api_key)
            logger.info(f"Stored API key for provider: {provider}")
        except Exception as e:
            logger.error(f"Failed to store key in keyring: {e}")
            raise

    def get_key(self, provider: str) -> Optional[str]:
        """Retrieve API key from the OS keyring.

        Args:
            provider: Provider name (e.g., "openrouter", "anthropic")

        Returns:
            The API key if found, None otherwise
        """
        if not KEYRING_AVAILABLE:
            logger.warning("keyring package not installed. API keys will not be available.")
            return None

        try:
            key = keyring.get_password(self.service, provider)
            return key
        except Exception as e:
            logger.warning(f"Failed to retrieve key from keyring: {e}")
            return None

    def delete_key(self, provider: str) -> bool:
        """Delete API key from the OS keyring.

        Args:
            provider: Provider name to delete

        Returns:
            True if key was deleted, False if it didn't exist
        """
        if not KEYRING_AVAILABLE:
            return False

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


def init_gnome_keyring(password: str) -> bool:
    """Initialize GNOME keyring on headless Linux.

    This enables secure keyring storage on headless servers by starting
    the GNOME keyring daemon with the provided password.

    Args:
        password: The password to unlock the keyring (required).

    Returns:
        True if keyring was initialized successfully, False otherwise

    Example:
        # With password (for automation):
        init_gnome_keyring("my-secret-password")
    """
    import subprocess

    if not password:
        logger.warning("Password is required to initialize GNOME keyring")
        return False

    try:
        # Check if gnome-keyring-daemon is available
        result = subprocess.run(
            ["which", "gnome-keyring-daemon"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.warning("gnome-keyring-daemon not installed")
            return False

        # Check if dbus-run-session is available
        result = subprocess.run(
            ["which", "dbus-run-session"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.warning("dbus-run-session not installed")
            return False

        # Initialize the keyring - pipe password to stdin
        cmd = ["dbus-run-session", "--", "gnome-keyring-daemon", "--unlock"]
        
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(input=password + "\n", timeout=10)

        if proc.returncode == 0:
            # Set the keyring backend to SecretService
            import keyring
            from keyring.backends import SecretService
            keyring.set_keyring(SecretService.Keyring())
            logger.info("GNOME keyring initialized successfully")
            return True
        else:
            logger.warning(f"Failed to initialize GNOME keyring: {stderr}")
            return False

    except FileNotFoundError as e:
        logger.warning(f"Required command not found: {e}")
        return False
    except Exception as e:
        logger.warning(f"Failed to initialize GNOME keyring: {e}")
        return False


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
