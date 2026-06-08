"""
SQL Agent 配置文件
提供默认值和常量，运行时配置通过 API 动态注入
"""

import os


PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "gemma4:31b"


PG_HOST: str = "localhost"


SKILL_FILE_PATH: str = os.path.join(PROJECT_ROOT, "skill.md")


LLM_TEMPERATURE: float = 0.1
LLM_REQUEST_TIMEOUT: int = 300  # 秒


DB_DEFAULT_PORTS: dict[str, int] = {
    "postgresql": 5432,
    "mysql": 3306,
    "oracle": 1521,
    "sqlite": 0,
    "duckdb": 0,
}


DB_DEFAULT_NAMES: dict[str, str] = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "oracle": "ORCL",
    "sqlite": "main",
    "duckdb": "main",
}
