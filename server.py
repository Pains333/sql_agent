import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from agent import SQLAgent
from conversation_store import ConversationStore
from file_parser import parse_file, SUPPORTED_EXTENSIONS
from data_importer import import_data_to_table
from skill_manager import DEFAULT_SKILL_CONTENT
from logging_config import get_logger, setup_logging
import config

logger = get_logger(__name__)

# 配置持久化文件路径
SETUP_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_config.json")

# 上传文件过期时间（30 分钟）
UPLOAD_TTL_SECONDS = 30 * 60

# 全局实例（延迟初始化，setup 后才可用）
agent: Optional[SQLAgent] = None
store = ConversationStore()
setup_done = False

# 上传文件的临时存储 {upload_id: {filename, columns, rows, row_count, preview, created_at}}
upload_storage: dict = {}


def _save_setup_config(cfg: dict):
    """将配置持久化到文件"""
    with open(SETUP_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _load_setup_config() -> Optional[dict]:
    """从文件加载已保存的配置"""
    if os.path.exists(SETUP_CONFIG_PATH):
        with open(SETUP_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _init_agent_from_config(cfg: dict) -> bool:
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
        _ = agent.db.conn  # 测试连接
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


def _cleanup_expired_uploads():
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()

    saved = _load_setup_config()
    if saved:
        logger.info("发现已保存的配置，正在自动初始化...")
        if _init_agent_from_config(saved):
            logger.info("Agent 初始化成功，跳过配置向导")
        else:
            global setup_done
            setup_done = True
            logger.info("Agent 初始化失败，但配置已保存，将在访问时延迟重试")
    yield
    # 关闭时清理
    if agent:
        agent.close()


app = FastAPI(title="SQL Agent API", version="2.0.0", lifespan=lifespan)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 请求/响应模型 ===

class SetupRequest(BaseModel):
    language: str = "zh"
    model_type: str = "local"         # local / api
    model_name: str = ""              # Ollama 模型名
    api_base_url: str = ""            # API 地址
    api_key: str = ""                 # API Key
    api_model: str = ""               # API 模型名
    db_type: str = "postgresql"       # postgresql / mysql / oracle
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = ""
    db_password: str = ""


class MessageRequest(BaseModel):
    content: str
    upload_id: Optional[str] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"


class TitleUpdate(BaseModel):
    title: str


# === Setup API ===

@app.get("/api/setup/status")
def get_setup_status():
    """检查是否已完成配置"""
    global setup_done
    if not setup_done:
        saved = _load_setup_config()
        if saved:
            setup_done = True
            _init_agent_from_config(saved)
    return {"setup_done": setup_done}


@app.post("/api/setup/reset")
def reset_setup():
    """重置配置，关闭 Agent，删除配置文件，清除 skill.md"""
    global agent, setup_done
    if agent:
        try:
            agent.close()
        except Exception:
            pass
        agent = None
    setup_done = False
    if os.path.exists(SETUP_CONFIG_PATH):
        os.remove(SETUP_CONFIG_PATH)
    with open(config.SKILL_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(DEFAULT_SKILL_CONTENT)
    return {"success": True}


@app.get("/api/ollama/models")
def get_ollama_models():
    """查询 Ollama 本地模型列表"""
    try:
        resp = requests.get(
            f"{config.OLLAMA_BASE_URL}/api/tags",
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        models = [
            {
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
            }
            for m in data.get("models", [])
        ]
        return {"models": models}
    except requests.exceptions.ConnectionError:
        return {"models": [], "error": "Ollama 未运行"}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.post("/api/setup")
def submit_setup(req: SetupRequest):
    """
    提交配置，初始化 Agent，扫描数据库结构

    流程：
    1. 根据配置创建 SQLAgent
    2. 测试数据库连接
    3. 扫描数据库结构写入 skill.md
    4. 保存配置到文件（下次启动自动加载）
    5. 标记 setup 完成
    """
    global agent, setup_done

    # 校验必填字段
    if not req.db_user.strip():
        raise HTTPException(status_code=400, detail="数据库用户名不能为空")
    if not req.db_password.strip():
        raise HTTPException(status_code=400, detail="数据库密码不能为空")
    if req.model_type == "api":
        if not req.api_base_url.strip():
            raise HTTPException(status_code=400, detail="API 地址不能为空")
        if not req.api_key.strip():
            raise HTTPException(status_code=400, detail="API Key 不能为空")
        if not req.api_model.strip():
            raise HTTPException(status_code=400, detail="API 模型名称不能为空")

    cfg = req.model_dump()

    try:
        if not _init_agent_from_config(cfg):
            raise RuntimeError("数据库连接失败")

        scan_result = agent.scan_all_databases()
        _save_setup_config(cfg)

        return {
            "success": True,
            "message": scan_result,
            "current_db": agent.get_current_db(),
            "skill_summary": agent.skill.get_summary(),
        }

    except Exception as e:
        if agent:
            try:
                agent.close()
            except Exception:
                pass
            agent = None
        setup_done = False
        raise HTTPException(status_code=400, detail=str(e))


def _require_agent():
    """确保 agent 已初始化，如果未初始化则尝试从保存的配置延迟初始化"""
    global agent
    if agent is None:
        saved = _load_setup_config()
        if saved:
            logger.info("Agent 未初始化，尝试从保存的配置恢复...")
            if _init_agent_from_config(saved):
                logger.info("Agent 延迟初始化成功")
                return agent
            else:
                logger.warning("Agent 延迟初始化失败")
        raise HTTPException(status_code=503, detail="Agent 未初始化，请先完成配置")
    return agent


# === 对话 API ===

@app.get("/api/conversations")
def list_conversations():
    """获取所有对话列表"""
    return store.list_conversations()


@app.post("/api/conversations")
def create_conversation(req: ConversationCreate):
    """创建新对话"""
    return store.create_conversation(title=req.title)


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    """获取对话详情（含所有消息）"""
    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """删除对话"""
    if not store.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"success": True}


@app.patch("/api/conversations/{conv_id}/title")
def update_conversation_title(conv_id: str, req: TitleUpdate):
    """更新对话标题"""
    if not store.update_title(conv_id, req.title):
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"success": True}


@app.post("/api/conversations/{conv_id}/messages")
def send_message(conv_id: str, req: MessageRequest):
    """发送用户消息，获取 AI 回复"""
    ag = _require_agent()

    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    user_input = req.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # 保存用户消息
    store.add_message(conv_id, role="user", content=user_input)

    # 定期清理过期上传
    _cleanup_expired_uploads()

    try:
        # 检查是否有附件
        file_data = None
        file_info_text = ""
        if req.upload_id and req.upload_id in upload_storage:
            file_data = upload_storage[req.upload_id]
            file_info_text = (
                f"\n[附件信息] 文件名: {file_data['filename']}, "
                f"列名: {', '.join(file_data['columns'])}, "
                f"行数: {file_data['row_count']}"
            )

        # 第一阶段：LLM 思考（将附件信息注入用户消息）
        plan = ag.think(user_input + file_info_text)

        # 如果是 import_file action，直接执行数据导入
        if plan.get("action") == "import_file" and file_data:
            return _handle_import_file(ag, conv_id, plan, file_data, req.upload_id)

        # 第二阶段：执行
        result = ag.execute_plan(plan, confirm_callback=None)

        # 构建 AI 回复
        return _build_ai_response(conv_id, result)

    except Exception as e:
        return store.add_message(
            conv_id,
            role="assistant",
            content="处理请求时发生错误",
            error=str(e),
        )


def _build_ai_response(conv_id: str, result: dict):
    """根据执行结果构建 AI 回复消息"""
    if result["error"]:
        return store.add_message(
            conv_id,
            role="assistant",
            content=result.get("explanation", "") or result["error"],
            sql=result.get("sql", ""),
            action=result.get("action", ""),
            error=result["error"],
        )

    result_text = ""
    res = result.get("result")
    if isinstance(res, tuple) and len(res) == 2:
        columns, rows = res
        if columns:
            result_text = _format_query_result(columns, rows)
    elif isinstance(res, str):
        result_text = res

    return store.add_message(
        conv_id,
        role="assistant",
        content=result.get("explanation", ""),
        sql=result.get("sql", ""),
        action=result.get("action", ""),
        result=result_text,
    )


def _handle_import_file(ag, conv_id: str, plan: dict, file_data: dict, upload_id: str):
    """处理文件导入操作"""
    target_table = plan.get("target_table", "").strip()
    target_db = plan.get("target_db", "").strip() or None

    if not target_table:
        match = re.search(
            r'[\u5bfc\u5165|\u5199\u5165|\u589e\u52a0].*?[\u5230|\u8868]\s*[`\'"]?(\w+)[`\'"]?',
            plan.get("explanation", ""),
        )
        if match:
            target_table = match.group(1)

    if not target_table:
        return store.add_message(
            conv_id,
            role="assistant",
            content="请指定目标表名，例如: 将附件数据导入到 users 表",
            action="import_file",
            error="未指定目标表名",
        )

    import_result = import_data_to_table(
        db_client=ag.db,
        table_name=target_table,
        file_data=file_data,
        database=target_db,
    )

    # 清理上传的文件数据
    upload_storage.pop(upload_id, None)

    if import_result["success"]:
        return store.add_message(
            conv_id,
            role="assistant",
            content=import_result["message"],
            action="import_file",
            result=f"成功导入 {import_result['inserted']} 行数据",
        )
    else:
        return store.add_message(
            conv_id,
            role="assistant",
            content=import_result["message"],
            action="import_file",
            error=import_result["message"],
        )


# === 工具 API ===

@app.get("/api/databases")
def list_databases():
    """获取数据库列表"""
    ag = _require_agent()
    try:
        databases = ag.db.list_databases()
        current = ag.db.current_db
        return {"databases": databases, "current": current}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skill")
def get_skill():
    """获取 skill.md 内容"""
    ag = _require_agent()
    return {"content": ag.skill.read()}


# === 文件上传 API ===

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件并解析
    支持: xlsx, xls, csv, pkl, parquet, json
    返回: upload_id, 文件信息, 列名, 行数, 预览
    """
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    try:
        tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".uploads")
        os.makedirs(tmp_dir, exist_ok=True)

        tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}{ext}")
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        # 解析文件
        parsed = parse_file(tmp_path, filename)

        # 清理临时文件
        os.remove(tmp_path)

        # 存储解析结果（带创建时间用于过期清理）
        upload_id = uuid.uuid4().hex[:12]
        upload_storage[upload_id] = {
            "filename": filename,
            "columns": parsed["columns"],
            "rows": parsed["rows"],
            "row_count": parsed["row_count"],
            "preview": parsed["preview"],
            "created_at": time.time(),
        }

        return {
            "upload_id": upload_id,
            "filename": filename,
            "columns": parsed["columns"],
            "row_count": parsed["row_count"],
            "preview": parsed["preview"],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")


@app.delete("/api/upload/{upload_id}")
def delete_upload(upload_id: str):
    """删除已上传的文件数据"""
    upload_storage.pop(upload_id, None)
    return {"success": True}


# === 辅助函数 ===

def _format_query_result(columns: list, rows: list) -> str:
    """将查询结果格式化为 Markdown 表格"""
    if not columns:
        return "查询无结果"

    header = "| " + " | ".join(str(c) for c in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"

    data_rows = []
    for row in rows[:100]:
        data_rows.append("| " + " | ".join(
            str(v) if v is not None else "NULL" for v in row
        ) + " |")

    result = "\n".join([header, separator] + data_rows)
    if len(rows) > 100:
        result += f"\n\n_(共 {len(rows)} 条记录，仅显示前 100 条)_"
    else:
        result += f"\n\n_共 {len(rows)} 条记录_"

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
