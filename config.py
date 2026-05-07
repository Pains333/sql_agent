"""
SQL Agent 配置文件
提供默认值和常量，运行时配置通过 API 动态注入
"""

import os

# === 默认值（用于 CLI 模式向后兼容） ===

# Ollama 默认配置
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma4:31b"

# PostgreSQL 默认配置
PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = ""
PG_PASSWORD = ""
PG_DEFAULT_DB = "postgres"

# skill.md 文件路径
SKILL_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill.md")

# LLM 请求配置
LLM_TEMPERATURE = 0.1
LLM_REQUEST_TIMEOUT = 300  # 秒

# === 常量 ===

# 数据库默认端口
DB_DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
    "oracle": 1521,
}

# 数据库默认数据库名
DB_DEFAULT_NAMES = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "oracle": "ORCL",
}
