"""
SQL Agent 配置文件
提供默认值和常量，运行时配置通过 API 动态注入
"""

import os

# === 项目根目录 (backend/ 的父目录) ===
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# === Ollama 默认配置 ===
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "gemma4:31b"

# === 默认主机（用于 CLI 模式向后兼容） ===
PG_HOST: str = "localhost"

# === skill.md 文件路径 ===
SKILL_FILE_PATH: str = os.path.join(PROJECT_ROOT, "skill.md")

# === LLM 请求配置 ===
LLM_TEMPERATURE: float = 0.1
LLM_REQUEST_TIMEOUT: int = 300  # 秒

# === 数据库默认端口 ===
DB_DEFAULT_PORTS: dict[str, int] = {
    "postgresql": 5432,
    "mysql": 3306,
    "oracle": 1521,
}

# === 数据库默认数据库名 ===
DB_DEFAULT_NAMES: dict[str, str] = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "oracle": "ORCL",
}
