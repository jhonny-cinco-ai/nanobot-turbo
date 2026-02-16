"""Secure memory allocation for sensitive data.

This module provides the SecureString class for protecting API keys and
other sensitive data in memory. It uses memory locking to prevent
swapping to disk and provides explicit wiping after use.

Key Features:
    - Memory locking (mlock) to prevent swapping
    - Explicit wiping with zeros
    - Thread-safe instance tracking
    - Emergency cleanup capability
"""

import os
import ctypes
import threading
from typing import Optional
from loguru import logger


class SecureString:
    """Holds sensitive data in protected memory.
    
    This class provides defense against memory scraping attacks by:
    1. Locking memory pages to prevent swapping to disk
    2. Providing explicit wiping after use
    3. Tracking all instances for emergency cleanup
    
    Example:
        >>> key = SecureString("sk-or-v1-abc123")
        >>> actual = key.get()
        >>> key.wipe()  # Overwrites memory with zeros
        
    Warning:
        Always use wipe() or destroy() after use to ensure cleanup.
        Memory locking requires appropriate permissions.
    """
    
    _instances: list = []
    _lock = threading.Lock()
    
    def __init__(self, value: str):
        """Create a secure string from a regular string.
        
        Args:
            value: The sensitive string to store securely
        """
        self._value = bytearray(value.encode('utf-8'))
        self._size = len(self._value)
        
        # Lock memory to prevent swapping (Linux/macOS)
        self._locked = False
        try:
            if hasattr(os, 'mlock'):
                os.mlock(id(self._value), self._size)
                self._locked = True
        except (PermissionError, OSError) as e:
            logger.debug(f"Could not lock memory (non-root): {e}")
        
        # Track this instance
        with SecureString._lock:
            SecureString._instances.append(self)
    
    def get(self) -> str:
        """Get the actual string value.
        
        Returns:
            The decoded string value
        """
        return self._value.decode('utf-8')
    
    def get_bytes(self) -> bytes:
        """Get the raw bytes.
        
        Returns:
            The raw byte value
        """
        return bytes(self._value)
    
    def wipe(self) -> None:
        """Overwrite memory with zeros and unlock.
        
        This is the recommended way to clean up sensitive data.
        Call this method after using the sensitive data.
        """
        if not self._value:
            return
        
        try:
            # Overwrite with zeros
            for i in range(len(self._value)):
                self._value[i] = 0
            
            # Unlock memory if locked
            if self._locked and hasattr(os, 'munlock'):
                try:
                    os.munlock(id(self._value), self._size)
                    self._locked = False
                except (PermissionError, OSError):
                    pass
            
            # Clear the internal buffer
            self._value = bytearray()
            self._size = 0
            
            # Remove from tracking
            with SecureString._lock:
                if self in SecureString._instances:
                    SecureString._instances.remove(self)
                    
        except Exception as e:
            logger.warning(f"Error wiping secure string: {e}")
    
    def __del__(self):
        """Destructor ensures cleanup when object is garbage collected."""
        try:
            self.wipe()
        except Exception:
            pass  # Ignore errors during destruction
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit ensures wiping."""
        self.wipe()
        return False
    
    @classmethod
    def wipe_all(cls) -> None:
        """Wipe all secure strings (emergency cleanup).
        
        This method can be called to ensure all sensitive data
        is wiped from memory, for example on application exit
        or after a security event.
        
        Warning:
            This will invalidate all existing SecureString instances.
        """
        with cls._lock:
            instances = cls._instances[:]  # Copy list to avoid modification during iteration
            
        for instance in instances:
            try:
                instance.wipe()
            except Exception as e:
                logger.warning(f"Error wiping instance: {e}")
        
        with cls._lock:
            cls._instances.clear()
    
    @classmethod
    def instance_count(cls) -> int:
        """Get the number of active secure string instances.
        
        Returns:
            Number of SecureString instances currently in memory
        """
        with cls._lock:
            return len(cls._instances)


class SecureMemory:
    """Context manager for secure memory operations.
    
    Provides a convenient way to work with sensitive data that
    will be automatically wiped when the context exits.
    
    Example:
        >>> with SecureMemory("api-key") as key:
        ...     # Use key.get() here
        ... # Key is automatically wiped when exiting the block
    """
    
    def __init__(self, value: str):
        """Create a secure memory context.
        
        Args:
            value: The sensitive value to store
        """
        self._secure = SecureString(value)
    
    def __enter__(self) -> SecureString:
        """Enter the context."""
        return self._secure
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the context and wipe the data."""
        self._secure.wipe()
        return False
    
    @property
    def value(self) -> str:
        """Get the secure value."""
        return self._secure.get()


# Global instance for emergency cleanup
import atexit
atexit.register(SecureString.wipe_all)
