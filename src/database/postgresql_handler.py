"""PostgreSQL database handler.

This module provides PostgreSQL database operations for JLTSQL.
"""

import io
from typing import Any, Dict, List, Optional

try:
    import pg8000.native
    DRIVER = "pg8000"
except ImportError:
    try:
        import psycopg
        from psycopg.rows import dict_row
        DRIVER = "psycopg"
    except ImportError:
        raise ImportError(
            "No PostgreSQL driver available. "
            "Install pg8000 (pure Python, works on Win32): pip install pg8000 "
            "Or install psycopg (requires libpq): pip install psycopg"
        )

from src.database.base import BaseDatabase, DatabaseError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PostgreSQLDatabase(BaseDatabase):
    """PostgreSQL database handler.

    Provides PostgreSQL-specific database operations for enterprise-grade
    storage of JV-Data.

    Configuration keys:
        - host: Database host (default: localhost)
        - port: Database port (default: 5432)
        - database: Database name
        - user: Database user
        - password: Database password
        - sslmode: SSL mode (default: prefer)
        - connect_timeout: Connection timeout in seconds (default: 10)

    Examples:
        >>> config = {
        ...     "host": "localhost",
        ...     "database": "keiba",
        ...     "user": "postgres",
        ...     "password": "secret"
        ... }
        >>> db = PostgreSQLDatabase(config)
        >>> with db:
        ...     db.create_table("test", "CREATE TABLE test (id SERIAL PRIMARY KEY)")
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize PostgreSQL database handler.

        Args:
            config: Database configuration
        """
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "keiba")
        self.user = config.get("user", "postgres")
        self.password = config.get("password", "")
        self.sslmode = config.get("sslmode", "prefer")
        self.connect_timeout = config.get("connect_timeout", 10)
        self._pk_cache: Dict[str, List[str]] = {}

    def get_db_type(self) -> str:
        """Get database type identifier.

        Returns:
            Database type string ('postgresql')
        """
        return "postgresql"

    def _quote_identifier(self, identifier: str) -> str:
        """Convert identifier to PostgreSQL-compatible form (lowercase, unquoted).

        PostgreSQL lowercases unquoted identifiers. To ensure compatibility
        with schemas that don't quote column names, we use lowercase unquoted
        identifiers instead of quoting them.

        Args:
            identifier: Column or table name

        Returns:
            Lowercase identifier (unquoted)
        """
        return identifier.lower()

    def _get_primary_key_columns(self, table_name: str) -> List[str]:
        """Extract PRIMARY KEY columns from table schema (cached).

        Queries the information_schema to get primary key columns for a table.
        Results are cached per table name to avoid repeated metadata queries.

        Args:
            table_name: Name of table

        Returns:
            List of primary key column names (lowercase)
        """
        cache_key = table_name.lower()
        if cache_key in self._pk_cache:
            return self._pk_cache[cache_key]

        try:
            sql = """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = ?::regclass
                AND i.indisprimary
                ORDER BY array_position(i.indkey, a.attnum)
            """
            rows = self.fetch_all(sql, (table_name.lower(),))
            # Handle both dict rows (psycopg) and list rows (pg8000.native)
            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append(row.get('attname', '').lower())
                elif isinstance(row, (list, tuple)):
                    # pg8000.native returns list of lists
                    result.append(str(row[0]).lower() if row else '')
                else:
                    result.append(str(row).lower())
            self._pk_cache[cache_key] = result
            return result
        except Exception as e:
            logger.warning(f"Could not get primary key for {table_name}: {e}")
            self._pk_cache[cache_key] = []
            return []

    def _convert_placeholders_and_params(self, sql: str, parameters: Optional[tuple] = None):
        """Convert ? placeholders and parameters for PostgreSQL driver compatibility.

        pg8000.native uses :param1, :param2, :param3 named parameters with dict.
        psycopg uses %s placeholders with tuple.

        Args:
            sql: SQL string with ? placeholders
            parameters: Optional parameters tuple

        Returns:
            Tuple of (converted_sql, converted_parameters)
        """
        if DRIVER == "pg8000":
            # Convert ? to :param1, :param2, :param3, ... for pg8000.native
            parts = sql.split("?")
            if len(parts) == 1:
                return (sql, parameters or ())  # No placeholders

            result = parts[0]
            for i in range(1, len(parts)):
                result += f":param{i}" + parts[i]

            # Convert tuple to dict
            if parameters:
                params_dict = {f"param{i+1}": val for i, val in enumerate(parameters)}
                return (result, params_dict)
            else:
                return (result, {})
        else:  # psycopg
            # Convert ? to %s for psycopg
            converted_sql = sql.replace("?", "%s")
            return (converted_sql, parameters or ())

    def connect(self) -> None:
        """Establish PostgreSQL database connection.

        Raises:
            DatabaseError: If connection fails
        """
        try:
            if DRIVER == "pg8000":
                # pg8000.native returns dict-like results by default
                self._connection = pg8000.native.Connection(
                    user=self.user,
                    password=self.password,
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    timeout=self.connect_timeout,  # Add timeout parameter
                )
                self._cursor = None  # pg8000.native doesn't use cursors

            else:  # psycopg
                # Build connection string
                conn_str = (
                    f"host={self.host} "
                    f"port={self.port} "
                    f"dbname={self.database} "
                    f"user={self.user} "
                    f"password={self.password} "
                    f"sslmode={self.sslmode} "
                    f"connect_timeout={self.connect_timeout}"
                )

                self._connection = psycopg.connect(
                    conn_str,
                    row_factory=dict_row,
                )
                self._cursor = self._connection.cursor()

            logger.info(
                f"Connected to PostgreSQL database: {self.host}:{self.port}/{self.database}",
                driver=DRIVER
            )

        except Exception as e:
            raise DatabaseError(f"Failed to connect to PostgreSQL database: {e}")

    def disconnect(self) -> None:
        """Close PostgreSQL database connection."""
        if self._cursor:
            self._cursor.close()
            self._cursor = None

        if self._connection:
            self._connection.close()
            self._connection = None

        logger.info("Disconnected from PostgreSQL database")

    def execute(self, sql: str, parameters: Optional[tuple] = None) -> int:
        """Execute SQL statement.

        Args:
            sql: SQL statement
            parameters: Optional parameters

        Returns:
            Number of affected rows

        Raises:
            DatabaseError: If execution fails
        """
        if not self._connection:
            raise DatabaseError("Database not connected")

        try:
            # Convert SQL and parameters for PostgreSQL driver compatibility
            sql, params = self._convert_placeholders_and_params(sql, parameters)

            if DRIVER == "pg8000":
                # pg8000.native uses connection.run() for execution with dict params
                self._connection.run(sql, **params) if isinstance(params, dict) else self._connection.run(sql)
                return self._connection.row_count
            else:  # psycopg
                if params:
                    self._cursor.execute(sql, params)
                else:
                    self._cursor.execute(sql)
                return self._cursor.rowcount

        except Exception as e:
            logger.error(f"SQL execution failed: {sql[:100]}", error=str(e))
            if self._connection:
                self.rollback()
            raise DatabaseError(f"SQL execution failed: {e}")

    def executemany(self, sql: str, parameters_list: List[tuple]) -> int:
        """Execute SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement
            parameters_list: List of parameter tuples

        Returns:
            Number of affected rows

        Raises:
            DatabaseError: If execution fails
        """
        if not self._connection:
            raise DatabaseError("Database not connected")

        try:
            if DRIVER == "pg8000":
                # pg8000 doesn't have executemany, execute individually
                total_rows = 0
                for params in parameters_list:
                    # Convert SQL and parameters for each execution
                    converted_sql, converted_params = self._convert_placeholders_and_params(sql, params)
                    if isinstance(converted_params, dict):
                        self._connection.run(converted_sql, **converted_params)
                    else:
                        self._connection.run(converted_sql)
                    total_rows += self._connection.row_count
                return total_rows
            else:  # psycopg
                # Convert once for psycopg
                converted_sql, _ = self._convert_placeholders_and_params(sql, ())
                self._cursor.executemany(converted_sql, parameters_list)
                return self._cursor.rowcount

        except Exception as e:
            logger.error(f"SQL executemany failed: {sql[:100]}", error=str(e))
            if self._connection:
                self.rollback()
            raise DatabaseError(f"SQL executemany failed: {e}")

    def fetch_one(self, sql: str, parameters: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch single row.

        Args:
            sql: SQL query
            parameters: Optional parameters

        Returns:
            Dictionary mapping column names to values, or None

        Raises:
            DatabaseError: If query fails
        """
        if not self._connection:
            raise DatabaseError("Database not connected")

        try:
            # Convert SQL and parameters for PostgreSQL driver compatibility
            sql, params = self._convert_placeholders_and_params(sql, parameters)

            if DRIVER == "pg8000":
                # pg8000.native returns list of lists, need to convert to dict
                if isinstance(params, dict):
                    rows = self._connection.run(sql, **params)
                else:
                    rows = self._connection.run(sql)
                if not rows:
                    return None
                # Get column names from connection.columns
                columns = [col['name'] for col in self._connection.columns] if self._connection.columns else []
                if columns and rows:
                    return dict(zip(columns, rows[0]))
                return rows[0] if rows else None
            else:  # psycopg
                if params:
                    self._cursor.execute(sql, params)
                else:
                    self._cursor.execute(sql)
                row = self._cursor.fetchone()
                return row if row else None

        except Exception as e:
            logger.error(f"SQL query failed: {sql[:100]}", error=str(e))
            if self._connection:
                self.rollback()
            raise DatabaseError(f"SQL query failed: {e}")

    def fetch_all(self, sql: str, parameters: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows.

        Args:
            sql: SQL query
            parameters: Optional parameters

        Returns:
            List of dictionaries

        Raises:
            DatabaseError: If query fails
        """
        if not self._connection:
            raise DatabaseError("Database not connected")

        try:
            # Convert SQL and parameters for PostgreSQL driver compatibility
            sql, params = self._convert_placeholders_and_params(sql, parameters)

            if DRIVER == "pg8000":
                # pg8000.native returns list of lists, need to convert to dicts
                if isinstance(params, dict):
                    rows = self._connection.run(sql, **params)
                else:
                    rows = self._connection.run(sql)
                if not rows:
                    return []
                # Get column names from connection.columns
                columns = [col['name'] for col in self._connection.columns] if self._connection.columns else []
                if columns:
                    return [dict(zip(columns, row)) for row in rows]
                return rows  # Return as-is if no column info
            else:  # psycopg
                if params:
                    self._cursor.execute(sql, params)
                else:
                    self._cursor.execute(sql)
                rows = self._cursor.fetchall()
                return rows if rows else []

        except Exception as e:
            logger.error(f"SQL query failed: {sql[:100]}", error=str(e))
            if self._connection:
                self.rollback()
            raise DatabaseError(f"SQL query failed: {e}")

    def create_table(self, table_name: str, schema: str) -> None:
        """Create table from SQL schema.

        Args:
            table_name: Name of table to create
            schema: SQL CREATE TABLE statement

        Raises:
            DatabaseError: If creation fails
        """
        try:
            self.execute(schema)
            logger.info(f"Created table: {table_name}")

        except DatabaseError:
            raise

    def table_exists(self, table_name: str) -> bool:
        """Check if table exists.

        Args:
            table_name: Name of table to check

        Returns:
            True if table exists, False otherwise
        """
        try:
            sql = """
                SELECT tablename
                FROM pg_tables
                WHERE tablename = ?
            """
            row = self.fetch_one(sql, (table_name.lower(),))
            return row is not None

        except DatabaseError:
            return False

    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table column information.

        Args:
            table_name: Name of table

        Returns:
            List of column information dictionaries

        Raises:
            DatabaseError: If query fails
        """
        try:
            sql = """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = ?
                ORDER BY ordinal_position
            """
            return self.fetch_all(sql, (table_name.lower(),))

        except DatabaseError:
            raise

    def analyze(self, table_name: Optional[str] = None) -> None:
        """Analyze table(s) to update statistics.

        Args:
            table_name: Optional table name (analyzes all tables if None)

        Raises:
            DatabaseError: If analyze fails
        """
        try:
            if table_name:
                self.execute(f"ANALYZE {table_name}")
                logger.info(f"Analyzed table: {table_name}")
            else:
                self.execute("ANALYZE")
                logger.info("Analyzed all tables")

        except DatabaseError:
            raise

    def vacuum(self, table_name: Optional[str] = None) -> None:
        """Vacuum table(s) to reclaim space.

        Args:
            table_name: Optional table name (vacuums all tables if None)

        Raises:
            DatabaseError: If vacuum fails
        """
        try:
            # Vacuum requires autocommit mode
            if DRIVER == "pg8000":
                # pg8000.native is always in autocommit mode
                if table_name:
                    self.execute(f"VACUUM {table_name}")
                    logger.info(f"Vacuumed table: {table_name}")
                else:
                    self.execute("VACUUM")
                    logger.info("Vacuumed all tables")
            else:  # psycopg
                old_autocommit = self._connection.autocommit
                self._connection.autocommit = True

                if table_name:
                    self.execute(f"VACUUM {table_name}")
                    logger.info(f"Vacuumed table: {table_name}")
                else:
                    self.execute("VACUUM")
                    logger.info("Vacuumed all tables")

                self._connection.autocommit = old_autocommit

        except DatabaseError:
            raise

    def commit(self) -> None:
        """Commit current transaction.

        pg8000.native is always in autocommit mode and doesn't require explicit commits.
        psycopg requires explicit commits.

        Raises:
            DatabaseError: If commit fails
        """
        if not self._connection:
            raise DatabaseError("Database not connected")

        try:
            if DRIVER == "pg8000":
                # pg8000.native is in autocommit mode, no commit needed
                pass
            else:  # psycopg
                self._connection.commit()
                logger.debug("Transaction committed")

        except Exception as e:
            raise DatabaseError(f"Failed to commit transaction: {e}")

    def rollback(self) -> None:
        """Rollback current transaction.

        pg8000.native is always in autocommit mode and doesn't support rollback.
        psycopg supports rollback.

        Raises:
            DatabaseError: If rollback fails
        """
        if not self._connection:
            raise DatabaseError("Database not connected")

        try:
            if DRIVER == "pg8000":
                # pg8000.native is in autocommit mode, no rollback possible
                logger.warning("pg8000.native doesn't support rollback (autocommit mode)")
            else:  # psycopg
                self._connection.rollback()
                logger.debug("Transaction rolled back")

        except Exception as e:
            raise DatabaseError(f"Failed to rollback transaction: {e}")

    def insert(self, table_name: str, data: Dict[str, Any], use_replace: bool = True) -> int:
        """Insert single row into table.

        PostgreSQL uses INSERT ... ON CONFLICT ... DO UPDATE instead of INSERT OR REPLACE.

        Args:
            table_name: Name of table
            data: Dictionary mapping column names to values
            use_replace: If True, use ON CONFLICT DO UPDATE (default: True)

        Returns:
            Number of rows inserted/updated (1 on success)

        Raises:
            DatabaseError: If insert fails
        """
        if not data:
            raise DatabaseError("No data provided for insert")

        columns = list(data.keys())
        values = list(data.values())
        placeholders = ", ".join(["?" for _ in columns])
        # Quote column names (lowercase for PostgreSQL)
        quoted_columns = [self._quote_identifier(col) for col in columns]

        if use_replace:
            # Get primary key columns for this table
            pk_columns = self._get_primary_key_columns(table_name)

            if pk_columns:
                # Build ON CONFLICT DO UPDATE clause
                # UPDATE all columns except primary key columns
                update_columns = [col for col in quoted_columns if col.lower() not in pk_columns]
                if update_columns:
                    update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
                    pk_list = ", ".join(pk_columns)
                    sql = f"INSERT INTO {table_name} ({', '.join(quoted_columns)}) VALUES ({placeholders}) ON CONFLICT ({pk_list}) DO UPDATE SET {update_set}"
                else:
                    # All columns are primary keys, just use DO NOTHING
                    pk_list = ", ".join(pk_columns)
                    sql = f"INSERT INTO {table_name} ({', '.join(quoted_columns)}) VALUES ({placeholders}) ON CONFLICT ({pk_list}) DO NOTHING"
            else:
                # No primary key found, fall back to DO NOTHING to avoid errors
                logger.warning(f"No primary key found for {table_name}, using DO NOTHING")
                sql = f"INSERT INTO {table_name} ({', '.join(quoted_columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        else:
            sql = f"INSERT INTO {table_name} ({', '.join(quoted_columns)}) VALUES ({placeholders})"

        return self.execute(sql, tuple(values))

    @staticmethod
    def _format_copy_value(value) -> str:
        """Format a value for PostgreSQL COPY TEXT format.

        Args:
            value: Value to format

        Returns:
            Formatted string for COPY stream
        """
        if value is None:
            return "\\N"
        s = str(value)
        s = s.replace("\\", "\\\\")
        s = s.replace("\t", "\\t")
        s = s.replace("\n", "\\n")
        s = s.replace("\r", "\\r")
        return s

    def _build_copy_stream(self, data_list: List[Dict[str, Any]], columns: List[str]) -> io.BytesIO:
        """Build a BytesIO stream for COPY FROM STDIN.

        Args:
            data_list: List of record dictionaries
            columns: Ordered list of column names

        Returns:
            BytesIO stream with tab-separated COPY data
        """
        lines = []
        for row in data_list:
            fields = [self._format_copy_value(row.get(col)) for col in columns]
            lines.append("\t".join(fields))
        content = "\n".join(lines) + "\n"
        return io.BytesIO(content.encode("utf-8"))

    def copy_upsert(self, table_name: str, data_list: List[Dict[str, Any]], columns: List[str] = None) -> int:
        """Bulk upsert using PostgreSQL COPY via a staging table.

        Flow:
          1. CREATE TEMP TABLE _staging (LIKE target INCLUDING DEFAULTS)
          2. COPY _staging FROM STDIN (fast bulk load, no constraint checks)
          3. INSERT INTO target SELECT FROM _staging ON CONFLICT DO UPDATE
          4. DROP TABLE _staging (guaranteed via finally)

        Args:
            table_name: Target table name
            data_list: List of record dictionaries
            columns: Optional column list (inferred from first record if None)

        Returns:
            Number of rows upserted

        Raises:
            DatabaseError: If operation fails
        """
        if not data_list:
            return 0

        if not self._connection:
            raise DatabaseError("Database not connected")

        if columns is None:
            columns = list(data_list[0].keys())

        staging = f"_staging_{table_name.lower().replace('.', '_')}"
        quoted_columns = [self._quote_identifier(col) for col in columns]
        columns_clause = ", ".join(quoted_columns)

        try:
            # 1. Create staging table WITHOUT constraints
            # LIKE ... INCLUDING DEFAULTS inherits NOT NULL from PK columns,
            # which causes COPY to fail for rows with NULL PKs (e.g., H1 Total rows).
            # Use CREATE TABLE AS SELECT ... WHERE false to get columns only.
            self._connection.run(f"DROP TABLE IF EXISTS {staging}")
            self._connection.run(
                f"CREATE TEMP TABLE {staging} AS SELECT * FROM {table_name} WHERE false"
            )

            # 2. COPY into staging (chunked to avoid MemoryError on 32-bit Python)
            copy_sql = f"COPY {staging} ({columns_clause}) FROM STDIN"
            chunk_size = 5000
            for i in range(0, len(data_list), chunk_size):
                chunk = data_list[i:i + chunk_size]
                stream = self._build_copy_stream(chunk, columns)
                self._connection.run(copy_sql, stream=stream)

            # 3. Upsert: INSERT ... ON CONFLICT DO UPDATE
            pk_columns = self._get_primary_key_columns(table_name)
            if pk_columns:
                update_columns = [col for col in quoted_columns if col.lower() not in set(pk_columns)]
                pk_list = ", ".join(pk_columns)

                if update_columns:
                    update_set = ", ".join(
                        [f"{col} = EXCLUDED.{col}" for col in update_columns]
                    )
                    conflict_clause = f"ON CONFLICT ({pk_list}) DO UPDATE SET {update_set}"
                else:
                    conflict_clause = f"ON CONFLICT ({pk_list}) DO NOTHING"

                # Filter out NULL PKs in the SELECT
                pk_lower = {p.lower() for p in pk_columns}
                not_null_conditions = " AND ".join(
                    [f"{col} IS NOT NULL" for col in quoted_columns if col.lower() in pk_lower]
                )
                where_clause = f"WHERE {not_null_conditions}" if not_null_conditions else ""

                # DISTINCT ON (pk) で同一バッチ内の重複PKを排除
                # （差分データで同レースが複数回出現する場合の対策）
                distinct_clause = f"DISTINCT ON ({pk_list})"
                upsert_sql = (
                    f"INSERT INTO {table_name} ({columns_clause}) "
                    f"SELECT {distinct_clause} {columns_clause} FROM {staging} {where_clause} "
                    f"ORDER BY {pk_list} "
                    f"{conflict_clause}"
                )
            else:
                upsert_sql = (
                    f"INSERT INTO {table_name} ({columns_clause}) "
                    f"SELECT {columns_clause} FROM {staging}"
                )

            self._connection.run(upsert_sql)
            row_count = self._connection.row_count

            logger.debug(
                "COPY upsert completed",
                table=table_name,
                rows=row_count,
            )
            return row_count

        except Exception as e:
            logger.error(
                f"COPY upsert failed for {table_name}",
                error=str(e),
                error_repr=repr(e),
                error_type=type(e).__name__,
                rows=len(data_list),
                columns=len(columns),
            )
            raise DatabaseError(f"COPY upsert failed: {repr(e)}")

        finally:
            try:
                self._connection.run(f"DROP TABLE IF EXISTS {staging}")
            except Exception:
                pass

    def insert_many(self, table_name: str, data_list: List[Dict[str, Any]], use_replace: bool = True) -> int:
        """Insert multiple rows into table using multi-row VALUES bulk insert.

        For pg8000, builds a single INSERT with multiple VALUE rows:
          INSERT INTO t (c1,c2) VALUES (:r0c0,:r0c1), (:r1c0,:r1c1), ...
        This is dramatically faster than executing individual INSERTs.

        Args:
            table_name: Name of table
            data_list: List of dictionaries with same keys
            use_replace: If True, use ON CONFLICT DO UPDATE (default: True)

        Returns:
            Number of rows inserted/updated

        Raises:
            DatabaseError: If insert fails
        """
        if not data_list:
            raise DatabaseError("No data provided for insert")

        # Use first row to determine columns
        columns = list(data_list[0].keys())
        # Quote column names (lowercase for PostgreSQL)
        quoted_columns = [self._quote_identifier(col) for col in columns]

        # Build ON CONFLICT clause
        conflict_clause = ""
        if use_replace:
            pk_columns = self._get_primary_key_columns(table_name)

            if pk_columns:
                update_columns = [col for col in quoted_columns if col.lower() not in pk_columns]
                if update_columns:
                    update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
                    pk_list = ", ".join(pk_columns)
                    conflict_clause = f" ON CONFLICT ({pk_list}) DO UPDATE SET {update_set}"
                else:
                    pk_list = ", ".join(pk_columns)
                    conflict_clause = f" ON CONFLICT ({pk_list}) DO NOTHING"
            else:
                logger.warning(f"No primary key found for {table_name}, using DO NOTHING")
                conflict_clause = " ON CONFLICT DO NOTHING"

        columns_clause = ", ".join(quoted_columns)

        # Filter out rows with NULL values in PRIMARY KEY columns
        # (PostgreSQL rejects NULL in PK; one bad row would fail the entire batch)
        if use_replace and pk_columns:
            pk_col_set = set(pk_columns)
            original_count = len(data_list)
            data_list = [
                row for row in data_list
                if all(row.get(col) is not None for col in columns
                       if self._quote_identifier(col) in pk_col_set)
            ]
            skipped = original_count - len(data_list)
            if skipped:
                logger.debug(f"Skipped {skipped} rows with NULL PK values for {table_name}")
            if not data_list:
                return 0

        if DRIVER == "pg8000":
            # Multi-row VALUES bulk insert for pg8000
            # Optimal: ~600 params per statement (balances SQL size vs round trips)
            params_per_row = len(columns)
            max_rows_per_batch = max(1, min(600 // max(params_per_row, 1), len(data_list)))

            # Pre-compute PK column indices for dedup (avoids per-batch overhead)
            pk_col_indices = []
            if use_replace and pk_columns:
                pk_lower = {p.lower() for p in pk_columns}
                pk_col_indices = [i for i, col in enumerate(columns)
                                  if self._quote_identifier(col).lower() in pk_lower]

            total_rows = 0
            for batch_start in range(0, len(data_list), max_rows_per_batch):
                batch = data_list[batch_start:batch_start + max_rows_per_batch]

                # Deduplicate within sub-batch: keep last occurrence of each PK
                # (PostgreSQL rejects ON CONFLICT DO UPDATE affecting the same row twice)
                if pk_col_indices and len(batch) > 1:
                    seen = {}
                    for idx, row in enumerate(batch):
                        pk_key = tuple(row.get(columns[i]) for i in pk_col_indices)
                        seen[pk_key] = idx
                    if len(seen) < len(batch):
                        batch = [batch[i] for i in sorted(seen.values())]

                # Build VALUES (:r0c0, :r0c1), (:r1c0, :r1c1), ...
                value_rows = []
                all_params = {}
                for row_idx, row_data in enumerate(batch):
                    row_placeholders = []
                    for col_idx, col in enumerate(columns):
                        param_name = f"r{row_idx}c{col_idx}"
                        row_placeholders.append(f":{param_name}")
                        all_params[param_name] = row_data.get(col)
                    value_rows.append(f"({', '.join(row_placeholders)})")

                values_clause = ", ".join(value_rows)
                sql = f"INSERT INTO {table_name} ({columns_clause}) VALUES {values_clause}{conflict_clause}"

                try:
                    self._connection.run(sql, **all_params)
                    total_rows += len(batch)
                except Exception as e:
                    logger.error(f"Bulk insert failed for {table_name}", error=str(e))
                    raise DatabaseError(f"Bulk insert failed: {e}")

            return total_rows
        else:
            # psycopg path: use executemany with %s placeholders
            placeholders = ", ".join(["%s" for _ in columns])
            sql = f"INSERT INTO {table_name} ({columns_clause}) VALUES ({placeholders}){conflict_clause}"

            parameters_list = [
                tuple(row.get(col) for col in columns) for row in data_list
            ]

            try:
                self._cursor.executemany(sql, parameters_list)
                return self._cursor.rowcount
            except Exception as e:
                logger.error(f"SQL executemany failed: {sql[:100]}", error=str(e))
                if self._connection:
                    self.rollback()
                raise DatabaseError(f"SQL executemany failed: {e}")
