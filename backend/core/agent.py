"""
SQL Agent 核心逻辑
协调 LLM、数据库客户端和 Skill 管理器
"""

import re
from typing import Optional, Callable

from backend.llm.llm_client import LLMClient
from backend.db.db_client import DBClient
from backend.services.skill_manager import SkillManager, DEFAULT_SKILL_CONTENT
from backend.llm.prompts import build_system_prompt
from backend.core.exceptions import SQLAgentError
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

# 需要用户确认的危险操作
DDL_ACTIONS = {"create_db", "drop_db", "create_table", "drop_table", "alter_table"}
# DDL 中特别危险的操作
DANGEROUS_ACTIONS = {"drop_db", "drop_table"}

# PostgreSQL / MySQL 系统数据库（扫描时排除）
SYSTEM_DATABASES = {
    "template0", "template1",                              # PostgreSQL
    "information_schema", "performance_schema", "sys",     # MySQL
}


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
            logger.warning("切换数据库失败: %s", e)
            return f"切换数据库失败: {e}"

    def scan_all_databases(self) -> str:
        """
        扫描数据库所有结构，写入 skill.md

        Returns:
            扫描结果摘要
        """
        try:
            # 重置 skill.md
            self.skill.reset()

            current_db = self.db.current_db
            scanned_tables = 0
            db_count = 0

            if self.db_type == "oracle":
                # Oracle: 扫描当前用户下的所有表
                db_count = 1
                self.skill.add_database(current_db, "AL32UTF8")
                tables = self.db.list_tables()
                for table in tables:
                    try:
                        columns = self.db.describe_table(table)
                        self.skill.add_table(current_db, table, columns)
                        scanned_tables += 1
                    except Exception as e:
                        logger.warning("扫描 Oracle 表 %s 失败: %s", table, e)
            else:
                # PostgreSQL / MySQL: 扫描所有数据库及其表
                databases = self.db.list_databases()
                databases = [db for db in databases if db not in SYSTEM_DATABASES]
                db_count = len(databases)

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
                            except Exception as e:
                                logger.warning("扫描表 %s.%s 失败: %s", db_name, table, e)
                    except Exception as e:
                        logger.warning("扫描数据库 %s 失败: %s", db_name, e)

                # 切换回原始数据库
                try:
                    self.db.connect_to_db(current_db)
                except Exception as e:
                    logger.error("无法切回原始数据库 %s: %s", current_db, e)

            result_msg = f"扫描完成：发现 {db_count} 个数据库，{scanned_tables} 张表"
            logger.info(result_msg)
            return result_msg

        except Exception as e:
            logger.error("数据库扫描失败: %s", e)
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

            # import_file / 纯对话：标记成功，不需要执行 SQL
            if action in ("import_file", "chat") or not sql:
                result["success"] = True
                result["result"] = explanation

        except SQLAgentError as e:
            result["error"] = str(e)
        except Exception as e:
            logger.error("think() 处理失败: %s", e, exc_info=True)
            result["error"] = f"处理失败: {e}"

        return result

    def execute_plan(self, plan: dict, confirm_callback: Optional[Callable] = None) -> dict:
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

        except SQLAgentError as e:
            result["error"] = str(e)
        except Exception as e:
            logger.error("execute_plan() 处理失败: %s", e, exc_info=True)
            result["error"] = f"处理失败: {e}"

        return result

    # action → 执行方法的映射
    _ACTION_DISPATCH = {
        "query": "execute_query",
        "create_db": "execute_ddl", "drop_db": "execute_ddl",
        "create_table": "execute_ddl", "drop_table": "execute_ddl",
        "alter_table": "execute_ddl", "other": "execute_ddl",
        "insert": "execute_dml", "update": "execute_dml", "delete": "execute_dml",
    }

    def _execute_sql(self, action: str, sql: str):
        """根据 action 类型执行 SQL"""
        method_name = self._ACTION_DISPATCH.get(action, "execute_query")
        return getattr(self.db, method_name)(sql)

    def _update_skill(self, action: str, sql: str, target_db: str) -> None:
        """根据操作类型更新 skill.md"""
        try:
            if action in ("create_db", "drop_db"):
                db_name = self._extract_db_name(sql)
                if not db_name:
                    return
                if action == "create_db":
                    db_info = self.db.get_database_info(db_name)
                    self.skill.add_database(db_name, db_info.get("encoding", "UTF8"))
                else:
                    self.skill.remove_database(db_name)

            elif action in ("create_table", "drop_table", "alter_table"):
                table_name = self._extract_table_name(sql)
                db_name = target_db or self.db.current_db
                if not table_name:
                    return
                if action == "drop_table":
                    self.skill.remove_table(db_name, table_name)
                else:
                    columns = self.db.describe_table(table_name, db_name)
                    if action == "create_table":
                        self.skill.add_table(db_name, table_name, columns)
                    else:
                        self.skill.update_table(db_name, table_name, columns)

        except Exception as e:
            # skill.md 更新失败不应影响主流程，但记录日志
            logger.warning("更新 skill.md 失败 (action=%s): %s", action, e)

    @staticmethod
    def _extract_db_name(sql: str) -> str:
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

    @staticmethod
    def _extract_table_name(sql: str) -> str:
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

    def close(self) -> None:
        """关闭所有连接"""
        self.db.close()
