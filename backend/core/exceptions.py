"""
SQL Agent 统一异常体系
提供分层的异常类型，替代散布在各模块中的裸 Exception
"""


class SQLAgentError(Exception):
    """SQL Agent 基础异常，所有自定义异常的父类"""


class DatabaseConnectionError(SQLAgentError):
    """数据库连接失败"""


class DatabaseExecutionError(SQLAgentError):
    """SQL 执行失败（查询 / DDL / DML）"""


class LLMConnectionError(SQLAgentError):
    """LLM 服务连接失败（Ollama 或 API）"""


class LLMTimeoutError(SQLAgentError):
    """LLM 请求超时"""


class LLMResponseError(SQLAgentError):
    """LLM 响应格式异常"""


class FileParseError(SQLAgentError):
    """文件解析失败"""


class DataImportError(SQLAgentError):
    """数据导入失败"""


class SetupRequiredError(SQLAgentError):
    """Agent 未初始化，需要先完成配置"""
