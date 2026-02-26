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

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

try:
    import keyring
    from keyring import backends

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

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
        providers = [
            "anthropic",
            "openai",
            "openrouter",
            "deepseek",
            "groq",
            "zhipu",
            "dashscope",
            "gemini",
            "moonshot",
            "minimax",
            "aihubmix",
            "brave",
        ]

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
            # Test with a temporary key - with timeout to prevent hanging on headless servers
            test_key = "__nanofolks_test_key__"
            import time
            start_time = time.time()
            timeout = 3  # 3 second timeout
            
            # Try to set password with timeout
            while True:
                try:
                    keyring.set_password(self.service, "__test__", test_key)
                    break
                except Exception as e:
                    if "Prompt dismissed" in str(e) or time.time() - start_time > timeout:
                        logger.debug(f"Keyring not available (timeout): {e}")
                        return False
                    time.sleep(0.1)
                    
            retrieved = keyring.get_password(self.service, "__test__")
            keyring.delete_password(self.service, "__test__")

            return retrieved == test_key
        except Exception as e:
            logger.debug(f"Keyring not available: {e}")
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
    import os
    import re

    if not password:
        logger.warning("Password is required to initialize GNOME keyring")
        return False

    try:
        # Check if gnome-keyring-daemon is available
        result = subprocess.run(["which", "gnome-keyring-daemon"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("gnome-keyring-daemon not installed")
            return False

        # Ensure a DBus session exists (required for SecretService)
        if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
            result = subprocess.run(["which", "dbus-launch"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("dbus-launch not installed")
                return False

            dbus = subprocess.run(
                ["dbus-launch", "--sh-syntax"],
                capture_output=True,
                text=True,
            )
            if dbus.returncode != 0:
                logger.warning(f"Failed to start dbus session: {dbus.stderr.strip()}")
                return False

            for match in re.finditer(r"(\w+)=([^;\n]+);", dbus.stdout):
                os.environ[match.group(1)] = match.group(2)

        # Initialize the keyring in the current DBus session (non-interactive)
        proc = subprocess.run(
            ["gnome-keyring-daemon", "--unlock", "--components=secrets", "--daemonize"],
            input=password + "\n",
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            logger.warning(f"gnome-keyring-daemon failed: {proc.stderr.strip()}")
            return False

        # Parse exported environment variables from daemon output
        output = proc.stdout or ""
        control_match = re.search(r"GNOME_KEYRING_CONTROL=([^;\n]+)", output)
        pid_match = re.search(r"GNOME_KEYRING_PID=([^;\n]+)", output)
        if control_match:
            os.environ["GNOME_KEYRING_CONTROL"] = control_match.group(1)
        if pid_match:
            os.environ["GNOME_KEYRING_PID"] = pid_match.group(1)

        # Check if daemon is running by testing the keyring
        try:
            from keyring.backends import SecretService
            backend = SecretService.Keyring()

            # Test if we can actually use it
            backend.set_password("nanofolks", "__test__", "test")
            backend.delete_password("nanofolks", "__test__")

            # Set it as the global backend
            keyring.set_keyring(backend)
            logger.info("GNOME keyring initialized successfully")
            logger.info("Keyring daemon is running in background")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize GNOME keyring: {e}")
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


@dataclass
class KeyringInfo:
    """Information about the system's keyring configuration."""

    os_name: str
    os_detail: str
    keyring_backend: str
    keyring_available: bool
    needs_setup: bool
    setup_instructions: str


def get_keyring_info() -> KeyringInfo:
    """Get detailed information about the system's keyring configuration.

    Returns:
        KeyringInfo with OS, backend, and setup instructions
    """
    os_name = platform.system()
    os_detail = platform.release()

    if not KEYRING_AVAILABLE:
        return KeyringInfo(
            os_name=os_name,
            os_detail=os_detail,
            keyring_backend="Not installed",
            keyring_available=False,
            needs_setup=True,
            setup_instructions="Install keyring: pip install keyring keyrings.alt",
        )

    backend = "Unknown"
    needs_setup = False
    instructions = ""

    try:
        backend = keyring.get_keyring().__class__.__name__
    except Exception:
        pass

    if os_name == "Darwin":
        if backend in ("macOS", "Keyring", "Darwin"):
            backend = "macOS Keychain"
        else:
            backend = f"macOS ({backend})"
        instructions = "Should work automatically. If issues: pip install keyrings.alt"

    elif os_name == "Linux":
        is_headless = (
            os.environ.get("DISPLAY") is None and os.environ.get("WAYLAND_DISPLAY") is None
        )

        if is_headless:
            backend = "GNOME Keyring (headless)"
            needs_setup = True
            instructions = (
                "Headless server detected. Run: nanofolks security init-keyring --password YOUR_PASSWORD\n"
                "Or manually: dbus-run-session -- gnome-keyring-daemon --unlock --components=secrets"
            )
        elif backend in ("SecretService", "Gnome"):
            backend = "GNOME Keyring (Secret Service)"
            instructions = "Should work automatically on GNOME desktop."
        elif backend == "KWallet":
            backend = "KWallet (KDE)"
            instructions = "Should work automatically on KDE desktop."
        else:
            backend = f"Linux ({backend})"
            instructions = "Install: apt install libsecret-1-0 gnome-keyring"

    elif os_name == "Windows":
        backend = "Windows Credential Manager"
        instructions = "Should work automatically."

    try:
        available = is_keyring_available()
    except Exception:
        available = False

    return KeyringInfo(
        os_name=os_name,
        os_detail=os_detail,
        keyring_backend=backend,
        keyring_available=available,
        needs_setup=needs_setup and not available,
        setup_instructions=instructions,
    )
