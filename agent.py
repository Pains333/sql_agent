"""
SQL Agent 核心逻辑
协调 LLM、数据库客户端和 Skill 管理器
"""

import re
from llm_client import LLMClient
from db_client import DBClient
from skill_manager import SkillManager
from prompts import build_system_prompt


# 需要用户确认的危险操作
DDL_ACTIONS = {"create_db", "drop_db", "create_table", "drop_table", "alter_table"}
# DDL 中特别危险的操作
DANGEROUS_ACTIONS = {"drop_db", "drop_table"}


class SQLAgent:
    """SQL Agent 核心类"""

    def __init__(
        self,
        model_type: str = "local",
        model_name: str = "",
        api_base_url: str = "",
        api_key: str = "",
        api_model: str = "",
        db_type: str = "postgresql",
        db_host: str = "",
        db_port: int = 0,
        db_user: str = "",
        db_password: str = "",
    ):
        """
        初始化 SQL Agent

        Args:
            model_type: "local" (Ollama) 或 "api" (OpenAI 兼容)
            model_name: 本地模型名称
            api_base_url: API 地址
            api_key: API Key
            api_model: API 模型名称
            db_type: 数据库类型 postgresql/mysql/oracle
            db_host: 数据库主机
            db_port: 端口号
            db_user: 用户名
            db_password: 密码
        """
        self.db_type = db_type

        # 初始化 LLM
        if model_type == "api":
            self.llm = LLMClient(
                mode="api",
                base_url=api_base_url,
                model=api_model,
                api_key=api_key,
            )
        else:
            self.llm = LLMClient(
                mode="local",
                model=model_name,
            )

        # 初始化数据库客户端
        self.db = DBClient(
            db_type=db_type,
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
        )

        self.skill = SkillManager()

    def get_current_db(self) -> str:
        """获取当前连接的数据库名"""
        return self.db.current_db

    def switch_database(self, database: str) -> str:
        """
        切换数据库

        Args:
            database: 目标数据库名

        Returns:
            切换结果消息
        """
        try:
            self.db.connect_to_db(database)
            return f"已切换到数据库: {database}"
        except Exception as e:
            return f"切换数据库失败: {e}"

    def scan_all_databases(self) -> str:
        """
        扫描数据库所有结构，写入 skill.md

        Returns:
            扫描结果摘要
        """
        try:
            # 重置 skill.md
            self.skill.write(
                "# 数据库元信息\n\n> 此文件由 SQL Agent 自动维护，记录所有数据库和表的结构信息。\n"
            )

            current_db = self.db.current_db
            scanned_tables = 0

            if self.db_type == "oracle":
                # Oracle: 扫描当前用户下的所有表
                db_info = {"name": current_db, "encoding": "AL32UTF8"}
                self.skill.add_database(current_db, db_info.get("encoding", "UNKNOWN"))
                tables = self.db.list_tables()
                for table in tables:
                    try:
                        columns = self.db.describe_table(table)
                        self.skill.add_table(current_db, table, columns)
                        scanned_tables += 1
                    except Exception:
                        pass
            else:
                # PostgreSQL / MySQL: 扫描所有数据库及其表
                databases = self.db.list_databases()
                # 过滤系统数据库
                system_dbs = {
                    "template0", "template1",  # PostgreSQL
                    "information_schema", "performance_schema", "sys",  # MySQL
                }
                databases = [db for db in databases if db not in system_dbs]

                for db_name in databases:
                    try:
                        db_info = self.db.get_database_info(db_name)
                        self.skill.add_database(db_name, db_info.get("encoding", "UTF8"))

                        # 切换到该数据库并读取表
                        self.db.connect_to_db(db_name)
                        tables = self.db.list_tables()
                        for table in tables:
                            try:
                                columns = self.db.describe_table(table)
                                self.skill.add_table(db_name, table, columns)
                                scanned_tables += 1
                            except Exception:
                                pass
                    except Exception:
                        pass

                # 切换回原始数据库
                try:
                    self.db.connect_to_db(current_db)
                except Exception:
                    pass

            return f"扫描完成：发现 {len(databases) if self.db_type != 'oracle' else 1} 个数据库，{scanned_tables} 张表"

        except Exception as e:
            return f"扫描失败: {e}"

    def think(self, user_input: str) -> dict:
        """
        第一阶段：调用 LLM 分析用户输入，生成执行计划
        此方法不涉及用户交互，可安全在 spinner 中运行

        Args:
            user_input: 用户的自然语言输入

        Returns:
            思考结果字典（包含 action, sql, explanation 等）
        """
        result = {
            "success": False,
            "action": "",
            "sql": "",
            "explanation": "",
            "result": None,
            "error": "",
            "target_db": "",
            "target_table": "",
        }

        try:
            # 1. 构建系统提示词，注入当前数据库状态
            skill_context = self.skill.get_summary()
            system_prompt = build_system_prompt(
                skill_context, self.db.current_db, self.db_type
            )

            # 2. 调用 LLM
            response = self.llm.chat(user_input, system_prompt)

            # 3. 解析 LLM 响应
            parsed = self.llm.parse_json_response(response)
            action = parsed.get("action", "chat")
            sql = parsed.get("sql", "").strip()
            explanation = parsed.get("explanation", "")
            target_db = parsed.get("database", "").strip()

            result["action"] = action
            result["sql"] = sql
            result["explanation"] = explanation
            result["target_db"] = target_db
            result["target_table"] = parsed.get("target_table", "").strip()

            # import_file action: 标记成功，由 server 层处理实际导入
            if action == "import_file":
                result["success"] = True
                result["result"] = explanation
            # 纯对话，不需要执行 SQL
            elif action == "chat" or not sql:
                result["success"] = True
                result["result"] = explanation

        except ConnectionError as e:
            result["error"] = str(e)
        except TimeoutError as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = f"处理失败: {e}"

        return result

    def execute_plan(self, plan: dict, confirm_callback=None) -> dict:
        """
        第二阶段：根据思考结果执行操作
        包含用户确认交互，必须在 spinner 外运行

        Args:
            plan: think() 返回的结果字典
            confirm_callback: 确认回调函数，DDL 操作时调用

        Returns:
            执行结果字典
        """
        result = dict(plan)  # 复制 plan 的内容

        # 如果思考阶段已有错误或已完成（纯对话），直接返回
        if result["error"] or result["success"]:
            return result

        action = result["action"]
        sql = result["sql"]
        target_db = result.get("target_db", "")

        try:
            # 1. 如果需要切换数据库
            if target_db and target_db != self.db.current_db:
                # 创建数据库操作不需要切换
                if action != "create_db":
                    try:
                        self.db.connect_to_db(target_db)
                    except Exception as e:
                        result["error"] = f"切换到数据库 '{target_db}' 失败: {e}"
                        return result

            # 2. DDL 操作需要用户确认
            if action in DDL_ACTIONS and confirm_callback:
                is_dangerous = action in DANGEROUS_ACTIONS
                confirmed = confirm_callback(action, sql, result["explanation"], is_dangerous)
                if not confirmed:
                    result["success"] = True
                    result["result"] = "操作已取消"
                    return result

            # 3. 执行 SQL
            exec_result = self._execute_sql(action, sql)
            result["result"] = exec_result
            result["success"] = True

            # 4. 更新 skill.md
            self._update_skill(action, sql, target_db)

        except ConnectionError as e:
            result["error"] = str(e)
        except TimeoutError as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = f"处理失败: {e}"

        return result

    def _execute_sql(self, action: str, sql: str):
        """根据 action 类型执行 SQL"""
        if action in ("query",):
            return self.db.execute_query(sql)
        elif action in ("create_db", "drop_db", "create_table", "drop_table", "alter_table", "other"):
            return self.db.execute_ddl(sql)
        elif action in ("insert", "update", "delete"):
            return self.db.execute_dml(sql)
        else:
            return self.db.execute_query(sql)

    def _update_skill(self, action: str, sql: str, target_db: str):
        """根据操作类型更新 skill.md"""
        try:
            if action == "create_db":
                db_name = self._extract_db_name(sql)
                if db_name:
                    db_info = self.db.get_database_info(db_name)
                    self.skill.add_database(db_name, db_info.get("encoding", "UTF8"))

            elif action == "drop_db":
                db_name = self._extract_db_name(sql)
                if db_name:
                    self.skill.remove_database(db_name)

            elif action == "create_table":
                table_name = self._extract_table_name(sql)
                db_name = target_db or self.db.current_db
                if table_name:
                    columns = self.db.describe_table(table_name, db_name)
                    self.skill.add_table(db_name, table_name, columns)

            elif action == "drop_table":
                table_name = self._extract_table_name(sql)
                db_name = target_db or self.db.current_db
                if table_name:
                    self.skill.remove_table(db_name, table_name)

            elif action == "alter_table":
                table_name = self._extract_table_name(sql)
                db_name = target_db or self.db.current_db
                if table_name:
                    columns = self.db.describe_table(table_name, db_name)
                    self.skill.update_table(db_name, table_name, columns)

        except Exception:
            # skill.md 更新失败不应影响主流程
            pass

    def _extract_db_name(self, sql: str) -> str:
        """从 SQL 中提取数据库名"""
        patterns = [
            r'CREATE\s+DATABASE\s+(?:IF\s+NOT\s+EXISTS\s+)?["\']?(\w+)["\']?',
            r'DROP\s+DATABASE\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)["\']?',
        ]
        for pattern in patterns:
            match = re.search(pattern, sql, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _extract_table_name(self, sql: str) -> str:
        """从 SQL 中提取表名"""
        patterns = [
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?["\']?(\w+)["\']?',
            r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:\w+\.)?["\']?(\w+)["\']?',
            r'ALTER\s+TABLE\s+(?:\w+\.)?["\']?(\w+)["\']?',
        ]
        for pattern in patterns:
            match = re.search(pattern, sql, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def close(self):
        """关闭所有连接"""
        self.db.close()
