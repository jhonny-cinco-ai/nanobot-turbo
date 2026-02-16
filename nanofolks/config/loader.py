"""Configuration loading utilities."""

import json
import os
import stat
from pathlib import Path
from typing import Any
from loguru import logger

from nanofolks.config.schema import Config


# Marker for keys stored in OS keyring
KEYRING_MARKER = "__KEYRING__"

# Providers that support keyring storage
PROVIDERS_WITH_KEYS = [
    "anthropic", "openai", "openrouter", "deepseek", "groq",
    "zhipu", "dashscope", "gemini", "moonshot", "minimax",
    "aihubmix", "brave", "vllm"
]


def get_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / ".nanofolks" / "config.json"


def get_data_dir() -> Path:
     """Get the nanofolks data directory."""
     from nanofolks.utils.helpers import get_data_path
     return get_data_path()


def _ensure_room_initialized(config: Config) -> None:
     """Ensure the default #general room is created on first run.

     Args:
         config: Configuration object with room path
     """
     try:
         from nanofolks.bots.room_manager import RoomManager

         # This will create the default #general room if it doesn't exist
         # RoomManager uses get_data_dir() internally, which respects config
         manager = RoomManager()
         logger.info("Initialized default #general room with Leader")
     except Exception as e:
         # Don't fail if room creation fails - it will be retried on agent start
         print(f"Note: Could not initialize room: {e}")


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.
    
    If keyring is available, keys marked with __KEYRING__ will be
    resolved from the OS keyring.
    
    Args:
        config_path: Optional path to config file. Uses default if not provided.
    
    Returns:
        Loaded configuration object with keys resolved from keyring if available.
    """
    path = config_path or get_config_path()
    is_first_run = not path.exists()
    
    if path.exists():
        # Check and fix permissions if needed
        try:
            current_mode = stat.S_IMODE(os.stat(path).st_mode)
            if current_mode != 0o600:
                logger.warning(
                    f"Config file has insecure permissions: {oct(current_mode)}. "
                    f"Fixing to 0o600 (owner read/write only)..."
                )
                os.chmod(path, 0o600)
        except Exception as e:
            logger.warning(f"Could not verify config permissions: {e}")
        
        try:
            with open(path) as f:
                data = json.load(f)
            data = _migrate_config(data)
            config = Config.model_validate(convert_keys(data))
            
            # Resolve keys from keyring if available
            config = _resolve_keyring_keys(config)
            
            return config
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")
    
    config = Config()
    
    # On first run, ensure room is created
    if is_first_run:
        _ensure_room_initialized(config)
    
    return config


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file with secure permissions.
    
    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure parent directory has secure permissions (0700 = owner only)
    os.chmod(path.parent, 0o700)
    
    # Convert to camelCase format
    data = config.model_dump()
    data = convert_to_camel(data)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    # Enforce secure file permissions (0600 = owner read/write only)
    os.chmod(path, 0o600)
    logger.debug(f"Config saved with secure permissions: {path}")


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")
    return data


def _resolve_keyring_keys(config: Config) -> Config:
    """Resolve __KEYRING__ markers to actual keys from OS keyring.
    
    Args:
        config: Configuration object to resolve
        
    Returns:
        Configuration with keyring markers resolved to actual keys
    """
    try:
        from nanofolks.security.keyring_manager import get_keyring_manager
        
        keyring = get_keyring_manager()
        
        if not keyring.is_available():
            logger.debug("Keyring not available, using config file keys")
            return config
        
        # Resolve provider API keys
        providers = config.providers
        for provider_name in PROVIDERS_WITH_KEYS:
            provider = getattr(providers, provider_name, None)
            if provider and provider.api_key == KEYRING_MARKER:
                actual_key = keyring.get_key(provider_name)
                if actual_key:
                    provider.api_key = actual_key
                    logger.debug(f"Resolved {provider_name} key from keyring")
                else:
                    logger.warning(f"Keyring marker found for {provider_name} but no key in keyring")
        
        # Resolve brave search API key
        if config.tools and config.tools.web and config.tools.web.search:
            if config.tools.web.search.api_key == KEYRING_MARKER:
                actual_key = keyring.get_key("brave")
                if actual_key:
                    config.tools.web.search.api_key = actual_key
                    logger.debug("Resolved brave search key from keyring")
        
        # Resolve other tool API keys as needed
        
    except ImportError:
        logger.debug("Keyring manager not available, using config file keys")
    except Exception as e:
        logger.warning(f"Error resolving keyring keys: {e}")
    
    return config


def _migrate_to_keyring(config: Config, dry_run: bool = False) -> Config:
    """Migrate plain-text API keys to OS keyring.
    
    Args:
        config: Configuration with plain-text keys
        dry_run: If True, don't actually migrate, just return config
        
    Returns:
        Configuration with keys replaced by __KEYRING__ markers
    """
    try:
        from nanofolks.security.keyring_manager import get_keyring_manager
        
        keyring = get_keyring_manager()
        
        if not keyring.is_available():
            logger.warning("Keyring not available, cannot migrate keys")
            return config
        
        migrated = []
        
        # Migrate provider API keys
        providers = config.providers
        for provider_name in PROVIDERS_WITH_KEYS:
            provider = getattr(providers, provider_name, None)
            if provider and provider.api_key and provider.api_key != KEYRING_MARKER:
                if not dry_run:
                    keyring.store_key(provider_name, provider.api_key)
                provider.api_key = KEYRING_MARKER
                migrated.append(provider_name)
        
        # Migrate brave search key
        if config.tools and config.tools.web and config.tools.web.search:
            if config.tools.web.search.api_key and config.tools.web.search.api_key != KEYRING_MARKER:
                if not dry_run:
                    keyring.store_key("brave", config.tools.web.search.api_key)
                config.tools.web.search.api_key = KEYRING_MARKER
                migrated.append("brave")
        
        if migrated:
            logger.info(f"Migrated {len(migrated)} keys to keyring: {', '.join(migrated)}")
        
    except ImportError:
        logger.error("Keyring manager not available")
    except Exception as e:
        logger.error(f"Error migrating keys to keyring: {e}")
    
    return config


def convert_keys(data: Any) -> Any:
    """Convert camelCase keys to snake_case for Pydantic."""
    if isinstance(data, dict):
        return {camel_to_snake(k): convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_keys(item) for item in data]
    return data


def convert_to_camel(data: Any) -> Any:
    """Convert snake_case keys to camelCase."""
    if isinstance(data, dict):
        return {snake_to_camel(k): convert_to_camel(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_camel(item) for item in data]
    return data


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def snake_to_camel(name: str) -> str:
     """Convert snake_case to camelCase."""
     components = name.split("_")
     return components[0] + "".join(x.title() for x in components[1:])
