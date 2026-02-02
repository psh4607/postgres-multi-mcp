"""
Database Configuration Loader
다중 데이터베이스 설정을 YAML 파일에서 로드하고 관리하는 유틸리티
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class AccessMode(str, Enum):
    """SQL access modes for database connections."""

    UNRESTRICTED = "unrestricted"  # Full read/write access
    RESTRICTED = "restricted"  # Read-only with safety features


@dataclass
class DatabaseConfig:
    """Single database configuration."""

    name: str
    uri: str
    description: Optional[str] = None
    access_mode: AccessMode = AccessMode.RESTRICTED

    def __post_init__(self):
        """Validate and convert access_mode if needed."""
        if isinstance(self.access_mode, str):
            self.access_mode = AccessMode(self.access_mode)


@dataclass
class DatabasesConfig:
    """Container for all database configurations."""

    databases: list[DatabaseConfig]


# Default config file search paths (in order of priority)
DEFAULT_CONFIG_PATHS = [
    Path.home() / ".cursor" / "databases.yaml",  # User-level config
    Path.cwd() / ".cursor" / "databases.yaml",   # Project-level config
    Path.cwd() / "databases.yaml",               # Current directory (for Docker)
]


def _find_config_file() -> str:
    """Find the first existing config file from default paths."""
    # Check environment variable first
    env_path = os.environ.get("DATABASES_CONFIG_PATH")
    if env_path:
        return env_path

    # Search through default paths
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return str(path)

    # Return the first default path (will show warning if not found)
    return str(DEFAULT_CONFIG_PATHS[0])


# Configuration file path
CONFIG_FILE_PATH = _find_config_file()

# Cached configuration
_cached_config: Optional[DatabasesConfig] = None


def load_databases_config(config_path: Optional[str] = None) -> DatabasesConfig:
    """
    Load database configurations from YAML file.

    Args:
        config_path: Optional path to config file. Uses DATABASES_CONFIG_PATH env var or default if not provided.

    Returns:
        DatabasesConfig object containing all database configurations.
    """
    global _cached_config

    path = config_path or CONFIG_FILE_PATH

    # Return cached config if available and path hasn't changed
    if _cached_config is not None and config_path is None:
        return _cached_config

    try:
        if not os.path.exists(path):
            logger.warning(
                f"Database config file not found at {path}, using empty config"
            )
            _cached_config = DatabasesConfig(databases=[])
            return _cached_config

        with open(path, encoding="utf-8") as f:
            config_content = yaml.safe_load(f)

        if not config_content:
            logger.warning("Empty database config file")
            _cached_config = DatabasesConfig(databases=[])
            return _cached_config

        databases_raw = config_content.get("databases", [])

        if not isinstance(databases_raw, list):
            logger.warning('Invalid database config: "databases" must be a list')
            _cached_config = DatabasesConfig(databases=[])
            return _cached_config

        # Parse and validate each database configuration
        databases: list[DatabaseConfig] = []
        for db_config in databases_raw:
            if not isinstance(db_config, dict):
                logger.warning(f"Skipping invalid database config: {db_config}")
                continue

            name = db_config.get("name")
            uri = db_config.get("uri")

            if not name or not uri:
                logger.warning(
                    f"Skipping database config missing name or uri: {db_config}"
                )
                continue

            try:
                access_mode_str = db_config.get("access_mode", "restricted")
                access_mode = AccessMode(access_mode_str)
            except ValueError:
                logger.warning(
                    f"Invalid access_mode '{access_mode_str}' for database '{name}', defaulting to 'restricted'"
                )
                access_mode = AccessMode.RESTRICTED

            databases.append(
                DatabaseConfig(
                    name=name,
                    uri=uri,
                    description=db_config.get("description"),
                    access_mode=access_mode,
                )
            )

        logger.info(f"Loaded {len(databases)} database configurations from {path}")
        _cached_config = DatabasesConfig(databases=databases)
        return _cached_config

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML config: {e}")
        _cached_config = DatabasesConfig(databases=[])
        return _cached_config
    except Exception as e:
        logger.error(f"Failed to load database config: {e}")
        _cached_config = DatabasesConfig(databases=[])
        return _cached_config


def get_database_config(database_name: str) -> Optional[DatabaseConfig]:
    """
    Get configuration for a specific database by name.

    Args:
        database_name: Name of the database to find.

    Returns:
        DatabaseConfig if found, None otherwise.
    """
    config = load_databases_config()
    for db in config.databases:
        if db.name == database_name:
            return db
    return None


def get_database_names() -> list[str]:
    """
    Get list of all configured database names.

    Returns:
        List of database names.
    """
    config = load_databases_config()
    return [db.name for db in config.databases]


def get_all_databases() -> list[DatabaseConfig]:
    """
    Get all database configurations.

    Returns:
        List of DatabaseConfig objects.
    """
    config = load_databases_config()
    return config.databases


def clear_config_cache() -> None:
    """Clear the cached configuration. Useful for testing or hot-reload."""
    global _cached_config
    _cached_config = None


def reload_config() -> DatabasesConfig:
    """
    Reload configuration from file, clearing the cache first.

    Returns:
        Freshly loaded DatabasesConfig.
    """
    clear_config_cache()
    return load_databases_config()
