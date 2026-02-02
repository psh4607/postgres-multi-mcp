"""
Connection Manager
다중 PostgreSQL 데이터베이스 커넥션 풀을 관리하는 모듈
"""

import logging
from typing import Union

from .config_loader import AccessMode
from .config_loader import DatabaseConfig
from .config_loader import get_all_databases
from .config_loader import get_database_config
from .sql import DbConnPool
from .sql import SafeSqlDriver
from .sql import SqlDriver
from .sql import obfuscate_password

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    다중 데이터베이스 커넥션 풀 관리자.

    각 데이터베이스에 대해 lazy initialization으로 커넥션 풀을 생성하고 관리합니다.
    """

    def __init__(self):
        """Initialize the connection manager."""
        self._pools: dict[str, DbConnPool] = {}
        self._configs: dict[str, DatabaseConfig] = {}

    def _get_or_create_pool(self, database_name: str) -> DbConnPool:
        """
        Get existing pool or create a new one for the database.

        Args:
            database_name: Name of the database from config.

        Returns:
            DbConnPool instance.

        Raises:
            ValueError: If database is not found in configuration.
        """
        if database_name in self._pools:
            return self._pools[database_name]

        # Get database config
        db_config = get_database_config(database_name)
        if db_config is None:
            available = self.list_database_names()
            raise ValueError(
                f"Database '{database_name}' not found in configuration. "
                f"Available databases: {available}"
            )

        # Create new pool
        pool = DbConnPool(connection_url=db_config.uri)
        self._pools[database_name] = pool
        self._configs[database_name] = db_config

        logger.info(f"Created connection pool for database '{database_name}'")
        return pool

    async def get_connection(self, database_name: str) -> DbConnPool:
        """
        Get a connection pool for the specified database.

        Args:
            database_name: Name of the database from config.

        Returns:
            Connected DbConnPool instance.

        Raises:
            ValueError: If database is not found in configuration or connection fails.
        """
        pool = self._get_or_create_pool(database_name)

        # Ensure pool is connected
        if not pool.is_valid:
            try:
                await pool.pool_connect()
                logger.info(f"Connected to database '{database_name}'")
            except Exception as e:
                logger.error(
                    f"Failed to connect to database '{database_name}': {obfuscate_password(str(e))}"
                )
                raise

        return pool

    async def get_sql_driver(
        self, database_name: str
    ) -> Union[SqlDriver, SafeSqlDriver]:
        """
        Get the appropriate SQL driver for the specified database.

        The driver type (SqlDriver or SafeSqlDriver) is determined by the
        database's access_mode configuration.

        Args:
            database_name: Name of the database from config.

        Returns:
            SqlDriver or SafeSqlDriver instance.
        """
        pool = await self.get_connection(database_name)
        base_driver = SqlDriver(conn=pool)

        # Get access mode from config
        db_config = self._configs.get(database_name)
        if db_config is None:
            db_config = get_database_config(database_name)

        if db_config and db_config.access_mode == AccessMode.RESTRICTED:
            logger.debug(
                f"Using SafeSqlDriver with restrictions for database '{database_name}'"
            )
            return SafeSqlDriver(sql_driver=base_driver, timeout=30)
        else:
            logger.debug(f"Using unrestricted SqlDriver for database '{database_name}'")
            return base_driver

    def get_access_mode(self, database_name: str) -> AccessMode:
        """
        Get the access mode for a specific database.

        Args:
            database_name: Name of the database.

        Returns:
            AccessMode for the database.

        Raises:
            ValueError: If database is not found.
        """
        db_config = self._configs.get(database_name)
        if db_config is None:
            db_config = get_database_config(database_name)

        if db_config is None:
            raise ValueError(f"Database '{database_name}' not found in configuration")

        return db_config.access_mode

    def list_database_names(self) -> list[str]:
        """
        Get list of all configured database names.

        Returns:
            List of database names.
        """
        return [db.name for db in get_all_databases()]

    def list_databases(self) -> list[dict]:
        """
        Get detailed information about all configured databases.

        Returns:
            List of database info dictionaries.
        """
        databases = get_all_databases()
        result = []

        for db in databases:
            pool = self._pools.get(db.name)
            is_connected = pool.is_valid if pool else False

            result.append(
                {
                    "name": db.name,
                    "description": db.description,
                    "access_mode": db.access_mode.value,
                    "is_connected": is_connected,
                }
            )

        return result

    async def close_all(self) -> None:
        """Close all connection pools."""
        for name, pool in self._pools.items():
            try:
                await pool.close()
                logger.info(f"Closed connection pool for database '{name}'")
            except Exception as e:
                logger.error(f"Error closing pool for database '{name}': {e}")

        self._pools.clear()
        self._configs.clear()

    async def close_connection(self, database_name: str) -> None:
        """
        Close connection pool for a specific database.

        Args:
            database_name: Name of the database.
        """
        if database_name in self._pools:
            try:
                await self._pools[database_name].close()
                del self._pools[database_name]
                if database_name in self._configs:
                    del self._configs[database_name]
                logger.info(f"Closed connection pool for database '{database_name}'")
            except Exception as e:
                logger.error(
                    f"Error closing pool for database '{database_name}': {e}"
                )


# Global connection manager instance
connection_manager = ConnectionManager()
