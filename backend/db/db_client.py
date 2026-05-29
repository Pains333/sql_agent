"""
数据库客户端 - 支持 PostgreSQL、MySQL、Oracle
统一封装连接管理、SQL 执行、元数据查询
"""

from typing import Optional

from backend.core import config
from backend.core.exceptions import DatabaseConnectionError, DatabaseExecutionError
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class DBClient:
    """多数据库操作封装，支持 PostgreSQL / MySQL / Oracle"""

    def __init__(
        self,
        db_type: str = "postgresql",
        host: str = "",
        port: int = 0,
        user: str = "",
        password: str = "",
        database: str = "",
    ):
        self.db_type = db_type.lower()
        self.host = host or config.PG_HOST
        self.port = port or config.DB_DEFAULT_PORTS.get(self.db_type, 5432)
        self.user = user
        self.password = password
        self.current_db = database or config.DB_DEFAULT_NAMES.get(self.db_type, "postgres")
        self._conn = None

    @property
    def conn(self):
        """获取当前数据库连接，如果不存在则创建"""
        if self._conn is None or self._is_closed():
            self._connect()
        return self._conn

    def _is_closed(self) -> bool:
        """检查连接是否已关闭"""
        if self._conn is None:
            return True
        try:
            if self.db_type == "postgresql":
                return self._conn.closed != 0
            # MySQL / Oracle 都可以用 ping 检查
            self._conn.ping(reconnect=False) if self.db_type == "mysql" else self._conn.ping()
            return False
        except Exception:
            return True

    def _connect(self) -> None:
        """建立数据库连接"""
        try:
            if self.db_type == "postgresql":
                import psycopg2
                from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
                self._conn = psycopg2.connect(
                    host=self.host, port=self.port,
                    user=self.user, password=self.password,
                    dbname=self.current_db,
                )
                self._conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

            elif self.db_type == "mysql":
                import pymysql
                self._conn = pymysql.connect(
                    host=self.host, port=self.port,
                    user=self.user, password=self.password,
                    database=self.current_db,
                    autocommit=True, charset="utf8mb4",
                )

            elif self.db_type == "oracle":
                import oracledb
                dsn = f"{self.host}:{self.port}/{self.current_db}"
                self._conn = oracledb.connect(
                    user=self.user, password=self.password, dsn=dsn,
                )
                self._conn.autocommit = True

            else:
                raise ValueError(f"不支持的数据库类型: {self.db_type}")

            logger.info("已连接到 %s (数据库: %s)", self.db_type, self.current_db)

        except Exception as e:
            raise DatabaseConnectionError(f"无法连接到 {self.db_type}: {e}") from e

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            try:
                self._conn.close()
                logger.info("数据库连接已关闭")
            except Exception:
                pass
            self._conn = None

    def connect_to_db(self, database: str) -> None:
        """切换到指定数据库"""
        self.close()
        self.current_db = database
        self._connect()

    def _ensure_database(self, database: Optional[str]) -> None:
        """如果 database 与当前数据库不同，自动切换连接（Oracle 除外）"""
        if database and database != self.current_db and self.db_type != "oracle":
            self.connect_to_db(database)

    # ===========================
    # 统一 Cursor 执行
    # ===========================

    def _execute_with_cursor(
        self,
        sql: str,
        params: Optional[tuple] = None,
        *,
        fetch: bool = False,
    ):
        """
        统一的 cursor 执行模式，自动管理 cursor 生命周期

        Args:
            sql: SQL 语句
            params: 参数化查询参数
            fetch: True 返回 (columns, rows)，False 返回 rowcount

        Returns:
            fetch=True: (columns, rows) 元组
            fetch=False: 受影响的行数 (int)
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, params or ())
            if fetch:
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    return columns, rows
                return [], []
            return cursor.rowcount
        except Exception as e:
            raise DatabaseExecutionError(f"SQL 执行失败: {e}") from e
        finally:
            cursor.close()

    def execute_many(self, sql: str, values_list: list) -> int:
        """
        批量执行 SQL（executemany）

        Args:
            sql: 带占位符的 SQL 语句
            values_list: 参数列表

        Returns:
            插入的行数
        """
        cursor = self.conn.cursor()
        try:
            cursor.executemany(sql, values_list)
            return len(values_list)
        except Exception as e:
            raise DatabaseExecutionError(f"批量执行失败: {e}") from e
        finally:
            cursor.close()

    def _fetchall(self, sql: str, params=None) -> list:
        """执行查询并返回所有结果行（便捷方法）"""
        _, rows = self._execute_with_cursor(sql, params, fetch=True)
        return rows

    # ===========================
    # SQL 执行（公共 API）
    # ===========================

    def execute_query(self, sql_str: str) -> tuple:
        """执行查询 SQL，返回 (columns, rows)"""
        return self._execute_with_cursor(sql_str, fetch=True)

    def execute_ddl(self, sql_str: str) -> str:
        """执行 DDL 语句"""
        self._execute_with_cursor(sql_str)
        return "执行成功"

    def execute_dml(self, sql_str: str) -> str:
        """执行 DML 语句，返回受影响行数"""
        rowcount = self._execute_with_cursor(sql_str)
        return f"执行成功，影响了 {rowcount} 行"

    # ===========================
    # 元数据查询
    # ===========================

    def list_databases(self) -> list:
        """列出所有数据库"""
        queries = {
            "postgresql": "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;",
            "mysql": "SHOW DATABASES;",
            "oracle": "SELECT username FROM all_users ORDER BY username",
        }
        sql = queries.get(self.db_type)
        if not sql:
            return []
        _, rows = self.execute_query(sql)
        return [row[0] for row in rows]

    def list_tables(self, database: str = None) -> list:
        """列出指定数据库中的所有用户表"""
        self._ensure_database(database)

        queries = {
            "postgresql": "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;",
            "mysql": "SHOW TABLES;",
            "oracle": "SELECT table_name FROM user_tables ORDER BY table_name",
        }
        sql = queries.get(self.db_type)
        if not sql:
            return []
        _, rows = self.execute_query(sql)
        return [row[0] for row in rows]

    def describe_table(self, table_name: str, database: str = None) -> list:
        """
        获取表结构详情

        Returns:
            [(column_name, data_type, constraints), ...]
        """
        self._ensure_database(database)

        describe_methods = {
            "postgresql": self._describe_table_pg,
            "mysql": self._describe_table_mysql,
            "oracle": self._describe_table_oracle,
        }
        method = describe_methods.get(self.db_type)
        return method(table_name) if method else []

    # --- PostgreSQL 表结构查询 ---

    def _describe_table_pg(self, table_name: str) -> list:
        columns_info = self._fetchall("""
            SELECT c.column_name, c.data_type, c.character_maximum_length,
                   c.numeric_precision, c.numeric_scale, c.is_nullable, c.column_default,
                   CASE WHEN c.data_type = 'integer' AND c.column_default LIKE 'nextval%%' THEN 'SERIAL'
                        WHEN c.data_type = 'bigint' AND c.column_default LIKE 'nextval%%' THEN 'BIGSERIAL'
                        WHEN c.character_maximum_length IS NOT NULL THEN c.data_type || '(' || c.character_maximum_length || ')'
                        WHEN c.numeric_precision IS NOT NULL AND c.data_type = 'numeric' THEN 'NUMERIC(' || c.numeric_precision || ',' || COALESCE(c.numeric_scale, 0) || ')'
                        ELSE UPPER(c.data_type)
                   END AS full_type
            FROM information_schema.columns c
            WHERE c.table_schema = 'public' AND c.table_name = %s
            ORDER BY c.ordinal_position;
        """, (table_name,))

        pk_columns = {row[0] for row in self._fetchall("""
            SELECT kcu.column_name FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_schema = 'public' AND tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY';
        """, (table_name,))}

        unique_columns = {row[0] for row in self._fetchall("""
            SELECT kcu.column_name FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_schema = 'public' AND tc.table_name = %s AND tc.constraint_type = 'UNIQUE';
        """, (table_name,))}

        fk_info = {row[0]: f"REFERENCES {row[1]}({row[2]})" for row in self._fetchall("""
            SELECT kcu.column_name, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_schema = 'public' AND tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY';
        """, (table_name,))}

        result = []
        for col in columns_info:
            col_name, full_type, is_nullable, col_default = col[0], col[7], col[5], col[6]
            constraints = []
            if col_name in pk_columns:
                constraints.append("PRIMARY KEY")
            if col_name in unique_columns:
                constraints.append("UNIQUE")
            if is_nullable == "NO" and col_name not in pk_columns:
                constraints.append("NOT NULL")
            if col_name in fk_info:
                constraints.append(fk_info[col_name])
            if col_default and 'nextval' not in str(col_default):
                constraints.append(f"DEFAULT {col_default}")
            result.append((col_name, full_type, ", ".join(constraints) if constraints else ""))
        return result

    # --- MySQL 表结构查询 ---

    def _describe_table_mysql(self, table_name: str) -> list:
        columns_info = self._fetchall("""
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY,
                   COLUMN_DEFAULT, EXTRA
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION;
        """, (table_name,))

        result = []
        for row in columns_info:
            col_name, col_type, is_nullable, column_key, column_default, extra = row[:6]
            constraints = []
            if column_key == "PRI":
                constraints.append("PRIMARY KEY")
            if column_key == "UNI":
                constraints.append("UNIQUE")
            if is_nullable == "NO" and column_key != "PRI":
                constraints.append("NOT NULL")
            if column_default is not None:
                constraints.append(f"DEFAULT {column_default}")
            if extra:
                constraints.append(extra.upper())
            result.append((col_name, col_type.upper(), ", ".join(constraints) if constraints else ""))
        return result

    # --- Oracle 表结构查询 ---

    def _describe_table_oracle(self, table_name: str) -> list:
        columns_info = self._fetchall("""
            SELECT column_name, data_type, data_length, data_precision, data_scale, nullable, data_default
            FROM user_tab_columns WHERE table_name = :1 ORDER BY column_id
        """, [table_name.upper()])

        pk_columns = {row[0] for row in self._fetchall("""
            SELECT cols.column_name FROM all_constraints cons
            JOIN all_cons_columns cols ON cons.constraint_name = cols.constraint_name
            WHERE cons.table_name = :1 AND cons.constraint_type = 'P' AND cons.owner = USER
        """, [table_name.upper()])}

        result = []
        for col in columns_info:
            col_name, data_type, data_length, precision, scale, nullable, default = col[:7]

            if precision is not None and data_type == "NUMBER":
                full_type = f"NUMBER({precision},{scale or 0})"
            elif data_type in ("VARCHAR2", "CHAR", "NVARCHAR2"):
                full_type = f"{data_type}({data_length})"
            else:
                full_type = data_type

            constraints = []
            if col_name in pk_columns:
                constraints.append("PRIMARY KEY")
            if nullable == "N" and col_name not in pk_columns:
                constraints.append("NOT NULL")
            if default and default.strip():
                constraints.append(f"DEFAULT {default.strip()}")
            result.append((col_name, full_type, ", ".join(constraints) if constraints else ""))
        return result

    # ===========================
    # 数据库信息
    # ===========================

    def get_database_info(self, database: str) -> dict:
        """获取数据库详细信息"""
        if self.db_type == "postgresql":
            rows = self._fetchall(
                "SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = %s;",
                (database,)
            )
            encoding = rows[0][0] if rows else "UNKNOWN"
        elif self.db_type == "mysql":
            rows = self._fetchall(
                "SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s;",
                (database,)
            )
            encoding = rows[0][0] if rows else "utf8mb4"
        else:
            encoding = "UNKNOWN"
        return {"name": database, "encoding": encoding}
