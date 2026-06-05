import base64
import json
import os
import time
from typing import Optional

from backend.core.agent import SQLAgent
from backend.services.conversation_store import ConversationStore
from backend.core.logging_config import get_logger
from backend.core import config
from fastapi import HTTPException

logger = get_logger(__name__)

SETUP_CONFIG_PATH = os.path.join(config.PROJECT_ROOT, "setup_config.json")

# 敏感字段列表
_SENSITIVE_KEYS = {"db_password", "api_key"}


def _encode_value(val: str) -> str:
    """对敏感字段进行 Base64 编码存储（防止明文直接可见）"""
    return base64.b64encode(val.encode("utf-8")).decode("ascii")


def _decode_value(val: str) -> str:
    """解码 Base64 编码的敏感字段"""
    try:
        return base64.b64decode(val.encode("ascii")).decode("utf-8")
    except Exception:
        return val  # 兼容旧的明文配置

# 上传文件过期时间（30 分钟）
UPLOAD_TTL_SECONDS = 30 * 60

# 全局实例（延迟初始化，setup 后才可用）
agent: Optional[SQLAgent] = None
store = ConversationStore()
setup_done = False

# 上传文件的临时存储 {upload_id: {filename, columns, rows, row_count, preview, created_at}}
upload_storage: dict = {}


def save_setup_config(cfg: dict):
    """将配置持久化到文件，敏感字段加密"""
    safe_cfg = dict(cfg)
    for key in _SENSITIVE_KEYS:
        if key in safe_cfg and safe_cfg[key]:
            safe_cfg[key] = _encode_value(safe_cfg[key])
    safe_cfg["_encoded"] = True  # 标记已编码
    with open(SETUP_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(safe_cfg, f, ensure_ascii=False, indent=2)
    # 设置文件权限为仅所有者可读写
    os.chmod(SETUP_CONFIG_PATH, 0o600)


def load_setup_config() -> Optional[dict]:
    """从文件加载已保存的配置，自动解密敏感字段"""
    if os.path.exists(SETUP_CONFIG_PATH):
        with open(SETUP_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("_encoded"):
            for key in _SENSITIVE_KEYS:
                if key in cfg and cfg[key]:
                    cfg[key] = _decode_value(cfg[key])
            del cfg["_encoded"]
        return cfg
    return None

def init_agent_from_config(cfg: dict) -> bool:
    """根据配置初始化 Agent"""
    global agent, setup_done
    try:
        if agent:
            agent.close()
        agent = SQLAgent(
            model_type=cfg.get("model_type", "local"),
            model_name=cfg.get("model_name", ""),
            api_base_url=cfg.get("api_base_url", ""),
            api_key=cfg.get("api_key", ""),
            api_model=cfg.get("api_model", ""),
            db_type=cfg.get("db_type", "postgresql"),
            db_host=cfg.get("db_host", "localhost"),
            db_port=cfg.get("db_port", 5432),
            db_user=cfg.get("db_user", ""),
            db_password=cfg.get("db_password", ""),
        )
        _ = agent.db.conn
        setup_done = True
        return True
    except Exception as e:
        logger.warning("自动加载配置失败: %s", e)
        if agent:
            try:
                agent.close()
            except Exception:
                pass
            agent = None
        setup_done = False
        return False


def cleanup_expired_uploads():
    """清理过期的上传文件数据"""
    now = time.time()
    expired = [
        uid for uid, data in upload_storage.items()
        if now - data.get("created_at", 0) > UPLOAD_TTL_SECONDS
    ]
    for uid in expired:
        del upload_storage[uid]
    if expired:
        logger.info("清理了 %d 个过期上传", len(expired))


def require_agent():
    """确保 agent 已初始化，如果未初始化则尝试从保存的配置延迟初始化"""
    global agent
    if agent is None:
        saved = load_setup_config()
        if saved:
            logger.info("Agent 未初始化，尝试从保存的配置恢复...")
            if init_agent_from_config(saved):
                logger.info("Agent 延迟初始化成功")
                return agent
            else:
                logger.warning("Agent 延迟初始化失败")
        raise HTTPException(status_code=503, detail="Agent 未初始化，请先完成配置")
    return agent
