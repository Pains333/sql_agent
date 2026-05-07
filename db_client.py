"""
数据库客户端 - 支持 PostgreSQL、MySQL、Oracle
"""

import config


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
        """
        初始化数据库客户端

        Args:
            db_type: 数据库类型 postgresql/mysql/oracle
            host: 数据库主机
            port: 端口号
            user: 用户名
            password: 密码
            database: 默认数据库名
        """
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
        if self.db_type == "postgresql":
            return self._conn.closed != 0
        elif self.db_type == "mysql":
            try:
                self._conn.ping(reconnect=False)
                return False
            except Exception:
                return True
        elif self.db_type == "oracle":
            try:
                self._conn.ping()
                return False
            except Exception:
                return True
        return True

    def _connect(self):
        """建立数据库连接"""
        try:
            if self.db_type == "postgresql":
                import psycopg2
                from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
                self._conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    dbname=self.current_db,
                )
                self._conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

            elif self.db_type == "mysql":
                import pymysql
                self._conn = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.current_db,
                    autocommit=True,
                    charset="utf8mb4",
                )

            elif self.db_type == "oracle":
                import oracledb
                dsn = f"{self.host}:{self.port}/{self.current_db}"
                self._conn = oracledb.connect(
                    user=self.user,
                    password=self.password,
                    dsn=dsn,
                )
                self._conn.autocommit = True

            else:
                raise ValueError(f"不支持的数据库类型: {self.db_type}")

        except Exception as e:
            raise ConnectionError(f"无法连接到 {self.db_type}: {e}")

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def connect_to_db(self, database: str):
        """切换到指定数据库"""
        self.close()
        self.current_db = database
        self._connect()

    # ===========================
    # SQL 执行
    # ===========================

    def execute_query(self, sql_str: str) -> tuple:
        """执行查询 SQL，返回 (columns, rows)"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql_str)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return columns, rows
            return [], []
        except Exception as e:
            raise RuntimeError(f"查询执行失败: {e}")
        finally:
            cursor.close()

    def execute_ddl(self, sql_str: str) -> str:
        """执行 DDL 语句"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql_str)
            return "执行成功"
        except Exception as e:
            raise RuntimeError(f"DDL 执行失败: {e}")
        finally:
            cursor.close()

    def execute_dml(self, sql_str: str) -> str:
        """执行 DML 语句"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql_str)
            rowcount = cursor.rowcount
            return f"执行成功，影响了 {rowcount} 行"
        except Exception as e:
            raise RuntimeError(f"DML 执行失败: {e}")
        finally:
            cursor.close()

    # ===========================
    # 元数据查询（按数据库类型切换）
    # ===========================

    def list_databases(self) -> list:
        """列出所有数据库"""
        if self.db_type == "postgresql":
            _, rows = self.execute_query(
                "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"
            )
        elif self.db_type == "mysql":
            _, rows = self.execute_query("SHOW DATABASES;")
        elif self.db_type == "oracle":
            # Oracle 通常不列出多个 DB，而是列出 schema
            _, rows = self.execute_query(
                "SELECT username FROM all_users ORDER BY username"
            )
        else:
            return []
        return [row[0] for row in rows]

    def list_tables(self, database: str = None) -> list:
        """列出指定数据库中的所有用户表"""
        if database and database != self.current_db:
            if self.db_type != "oracle":
                self.connect_to_db(database)

        if self.db_type == "postgresql":
            _, rows = self.execute_query(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
            )
        elif self.db_type == "mysql":
            _, rows = self.execute_query("SHOW TABLES;")
        elif self.db_type == "oracle":
            _, rows = self.execute_query(
                "SELECT table_name FROM user_tables ORDER BY table_name"
            )
        else:
            return []
        return [row[0] for row in rows]

    def describe_table(self, table_name: str, database: str = None) -> list:
        """
        获取表结构详情

        Returns:
            [(column_name, data_type, constraints), ...]
        """
        if database and database != self.current_db:
            if self.db_type != "oracle":
                self.connect_to_db(database)

        if self.db_type == "postgresql":
            return self._describe_table_pg(table_name)
        elif self.db_type == "mysql":
            return self._describe_table_mysql(table_name)
        elif self.db_type == "oracle":
            return self._describe_table_oracle(table_name)
        return []

    # --- PostgreSQL 表结构查询 ---

    def _describe_table_pg(self, table_name: str) -> list:
        cursor = self.conn.cursor()
        try:
            # 字段信息
            cursor.execute("""
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
            columns_info = cursor.fetchall()
        finally:
            cursor.close()

        # 主键
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT kcu.column_name FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = 'public' AND tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY';
            """, (table_name,))
            pk_columns = {row[0] for row in cursor.fetchall()}
        finally:
            cursor.close()

        # 唯一约束
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT kcu.column_name FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = 'public' AND tc.table_name = %s AND tc.constraint_type = 'UNIQUE';
            """, (table_name,))
            unique_columns = {row[0] for row in cursor.fetchall()}
        finally:
            cursor.close()

        # 外键
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT kcu.column_name, ccu.table_name, ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                WHERE tc.table_schema = 'public' AND tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY';
            """, (table_name,))
            fk_info = {row[0]: f"REFERENCES {row[1]}({row[2]})" for row in cursor.fetchall()}
        finally:
            cursor.close()

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
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"DESCRIBE `{table_name}`;")
            rows = cursor.fetchall()
        finally:
            cursor.close()

        result = []
        for row in rows:
            col_name = row[0]
            col_type = row[1].upper()
            constraints = []
            if row[3] == "PRI":
                constraints.append("PRIMARY KEY")
            if row[3] == "UNI":
                constraints.append("UNIQUE")
            if row[2] == "NO" and row[3] != "PRI":
                constraints.append("NOT NULL")
            if row[4] is not None:
                constraints.append(f"DEFAULT {row[4]}")
            if row[5]:
                constraints.append(row[5].upper())
            result.append((col_name, col_type, ", ".join(constraints) if constraints else ""))
        return result

    # --- Oracle 表结构查询 ---

    def _describe_table_oracle(self, table_name: str) -> list:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT column_name, data_type, data_length, data_precision, data_scale, nullable, data_default
                FROM user_tab_columns WHERE table_name = :1 ORDER BY column_id
            """, [table_name.upper()])
            columns_info = cursor.fetchall()
        finally:
            cursor.close()

        # 主键
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT cols.column_name FROM all_constraints cons
                JOIN all_cons_columns cols ON cons.constraint_name = cols.constraint_name
                WHERE cons.table_name = :1 AND cons.constraint_type = 'P' AND cons.owner = USER
            """, [table_name.upper()])
            pk_columns = {row[0] for row in cursor.fetchall()}
        finally:
            cursor.close()

        result = []
        for col in columns_info:
            col_name = col[0]
            data_type = col[1]
            data_length = col[2]
            precision = col[3]
            scale = col[4]
            nullable = col[5]
            default = col[6]

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
            _, rows = self.execute_query(
                f"SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = '{database}';"
            )
            encoding = rows[0][0] if rows else "UNKNOWN"
        elif self.db_type == "mysql":
            _, rows = self.execute_query(
                f"SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = '{database}';"
            )
            encoding = rows[0][0] if rows else "utf8mb4"
        else:
            encoding = "UNKNOWN"
        return {"name": database, "encoding": encoding}
