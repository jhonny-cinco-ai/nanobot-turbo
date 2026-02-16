"""Secure key storage and symbolic reference resolution.

This module implements the KeyVault concept from the security architecture,
providing symbolic key references that resolve at execution time rather
than being exposed to the LLM in plain text.

Key Concept:
    Instead of: api_key = "sk-or-v1-abc123..."
    Use: api_key = "{{openrouter_key}}"
    
The LLM sees {{openrouter_key}}, and the actual key is resolved
at the moment of tool execution.

Architecture:
    ZONE 1 (LLM): Sees {{openrouter_key}}
    ZONE 2 (Execution): Resolves to actual key
    ZONE 3 (Storage): OS Keyring / Encrypted storage
"""

import re
from typing import Optional
from loguru import logger

from nanofolks.security.keyring_manager import KeyringManager, get_keyring_manager


# Pattern for symbolic references: {{key_name}}
SYMBOLIC_REF_PATTERN = re.compile(r'^\{\{(\w+)\}\}$')

# Mapping of provider names to key names
PROVIDER_KEY_MAP = {
    "openrouter": "openrouter_key",
    "anthropic": "anthropic_key",
    "openai": "openai_key",
    "deepseek": "deepseek_key",
    "groq": "groq_key",
    "brave": "brave_key",
    "zhipu": "zhipu_key",
    "dashscope": "dashscope_key",
    "gemini": "gemini_key",
    "moonshot": "moonshot_key",
    "minimax": "minimax_key",
    "aihubmix": "aihubmix_key",
}


class KeyVault:
    """Central secure storage for symbolic key references.
    
    This class provides the core security innovation: symbolic references
    that resolve to actual keys only at execution time. LLMs never see
    the actual API keys.
    
    Example:
        >>> vault = KeyVault()
        >>> vault.store_key("openrouter_key", "sk-or-v1-abc123")
        >>> # LLM sees: {{openrouter_key}}
        >>> actual = vault.get_for_execution("{{openrouter_key}}")
        >>> # actual = "sk-or-v1-abc123"
    """
    
    def __init__(self, keyring: Optional[KeyringManager] = None):
        """Initialize the KeyVault.
        
        Args:
            keyring: Optional KeyringManager instance. Uses global if not provided.
        """
        self.keyring = keyring or get_keyring_manager()
        self._cache: dict[str, str] = {}
    
    def is_symbolic_ref(self, value: str) -> bool:
        """Check if a value is a symbolic reference.
        
        Args:
            value: The value to check
            
        Returns:
            True if the value is a symbolic reference like {{openrouter_key}}
        """
        if not value:
            return False
        return bool(SYMBOLIC_REF_PATTERN.match(value.strip()))
    
    def get_key_name(self, value: str) -> Optional[str]:
        """Extract the key name from a symbolic reference.
        
        Args:
            value: The symbolic reference (e.g., "{{openrouter_key}}")
            
        Returns:
            The key name (e.g., "openrouter_key") or None if not a symbolic ref
        """
        match = SYMBOLIC_REF_PATTERN.match(value.strip())
        return match.group(1) if match else None
    
    def get_for_execution(self, key_ref: str) -> str:
        """Resolve a symbolic reference to the actual API key.
        
        This is the core method that provides secure key resolution.
        The actual key is retrieved only at execution time, never
        exposed to the LLM.
        
        Args:
            key_ref: Symbolic reference like "{{openrouter_key}}" or 
                     provider name like "openrouter"
        
        Returns:
            The actual API key string
            
        Raises:
            ValueError: If the key reference is not found
        """
        if not key_ref:
            raise ValueError("Empty key reference")
        
        key_ref = key_ref.strip()
        
        # Check if it's a symbolic reference {{key_name}}
        if self.is_symbolic_ref(key_ref):
            key_name = self.get_key_name(key_ref)
        else:
            # Assume it's a provider name, convert to key name
            key_name = PROVIDER_KEY_MAP.get(key_ref, f"{key_ref}_key")
        
        # Check cache first (optional - can be disabled for higher security)
        # if key_name in self._cache:
        #     return self._cache[key_name]
        
        # Get from keyring
        actual_key = self.keyring.get_key(key_name)
        
        if not actual_key:
            # Try provider name directly as fallback
            actual_key = self.keyring.get_key(key_ref)
        
        if not actual_key:
            raise ValueError(f"Key not found for reference: {key_ref}")
        
        return actual_key
    
    def resolve_if_symbolic(self, value: str) -> str:
        """Resolve a value if it's a symbolic reference, otherwise return as-is.
        
        This is a convenience method for tool implementations.
        
        Args:
            value: Either a symbolic reference or a literal value
            
        Returns:
            Resolved key if symbolic, original value otherwise
        """
        if self.is_symbolic_ref(value):
            return self.get_for_execution(value)
        return value
    
    def list_references(self) -> list[str]:
        """List all available symbolic key references.
        
        Returns:
            List of symbolic reference strings like ["{{openrouter_key}}", ...]
        """
        references = []
        
        # Get all keys from keyring
        stored_keys = self.keyring.list_keys()
        
        # Also check provider key map for known keys
        for provider, key_name in PROVIDER_KEY_MAP.items():
            if key_name in stored_keys or self.keyring.has_key(key_name):
                references.append(f"{{{{{key_name}}}}}")
            elif provider in stored_keys or self.keyring.has_key(provider):
                references.append(f"{{{{{provider}_key}}}}")
        
        return references
    
    def get_public_view(self) -> dict[str, str]:
        """Get a public view of available keys (for LLM context).
        
        Returns a dictionary mapping key names to their symbolic references.
        This is safe to show to the LLM.
        
        Returns:
            Dictionary like {"openrouter_key": "{{openrouter_key}}", ...}
        """
        view = {}
        
        for provider, key_name in PROVIDER_KEY_MAP.items():
            if self.keyring.has_key(key_name) or self.keyring.has_key(provider):
                view[key_name] = f"{{{{{key_name}}}}}"
        
        return view
    
    def clear_cache(self) -> None:
        """Clear any cached keys from memory.
        
        Call this after tool execution for extra security.
        """
        self._cache.clear()
    
    def add_key(self, key_name: str, api_key: str) -> None:
        """Add a new key to the vault.
        
        Args:
            key_name: Name of the key (e.g., "openrouter_key")
            api_key: The actual API key
        """
        self.keyring.store_key(key_name, api_key)
        logger.info(f"Added key to vault: {key_name}")
    
    def has_key(self, key_ref: str) -> bool:
        """Check if a key exists for the given reference.
        
        Args:
            key_ref: Symbolic reference or key name
            
        Returns:
            True if the key exists
        """
        if self.is_symbolic_ref(key_ref):
            key_name = self.get_key_name(key_ref)
        else:
            key_name = PROVIDER_KEY_MAP.get(key_ref, key_ref)
        
        return self.keyring.has_key(key_name) or self.keyring.has_key(key_ref)


# Global KeyVault instance
_default_keyvault: Optional[KeyVault] = None


def get_keyvault() -> KeyVault:
    """Get the global KeyVault instance.
    
    Returns:
        The global KeyVault instance
    """
    global _default_keyvault
    if _default_keyvault is None:
        _default_keyvault = KeyVault()
    return _default_keyvault


def resolve_key(key_ref: str) -> str:
    """Convenience function to resolve a symbolic key reference.
    
    Args:
        key_ref: Symbolic reference like "{{openrouter_key}}"
        
    Returns:
        The actual API key
    """
    return get_keyvault().get_for_execution(key_ref)
