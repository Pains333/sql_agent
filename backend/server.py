import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from backend.core.agent import SQLAgent, DDL_ACTIONS
from backend.services.conversation_store import ConversationStore
from backend.services.file_parser import parse_file, SUPPORTED_EXTENSIONS
from backend.db.data_importer import import_data_to_table
from backend.services.skill_manager import DEFAULT_SKILL_CONTENT
from backend.llm.prompts import build_system_prompt
from backend.core.logging_config import get_logger, setup_logging
from backend.core import config

logger = get_logger(__name__)

# 配置持久化文件路径
SETUP_CONFIG_PATH = os.path.join(config.PROJECT_ROOT, "setup_config.json")

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


class SwitchDatabaseRequest(BaseModel):
    database: str


class ExecuteRequest(BaseModel):
    sql: str
    action: str
    message_id: str
    target_db: Optional[str] = None
    upload_id: Optional[str] = None
    target_table: Optional[str] = None


class PaginateRequest(BaseModel):
    sql: str
    page: int = 1
    page_size: int = 50


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

        # 如果是 import_file action，返回 pending 状态等待用户确认
        if plan.get("action") == "import_file" and file_data:
            target_table = plan.get("target_table", "").strip()
            import_sql = plan.get("sql", "").strip() or _build_import_preview_sql(
                target_table, file_data
            )
            return store.add_message(
                conv_id,
                role="assistant",
                content=plan.get("explanation", f"将附件 {file_data['filename']} 的数据导入到表 {target_table}"),
                sql=import_sql,
                action="import_file",
                status="pending",
                plan={**plan, "upload_id": req.upload_id, "filename": file_data['filename']},
            )

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


def _build_import_preview_sql(target_table: str, file_data: dict) -> str:
    """为文件导入生成预览 SQL，让用户确认"""
    columns = file_data.get("columns", [])
    row_count = file_data.get("row_count", 0)
    filename = file_data.get("filename", "")

    col_str = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["?" for _ in columns])

    lines = [
        f"-- 导入附件: {filename}",
        f"-- 目标表: {target_table}",
        f"-- 数据列: {', '.join(columns)}",
        f"-- 共 {row_count} 行数据",
        f"-- 自增字段(如ID)会自动跳过，缺少的时间字段会自动填充当前时间",
        f"-- 重复数据会自动跳过(ON CONFLICT DO NOTHING)",
        f"",
        f'INSERT INTO "{target_table}" ({col_str})',
        f'VALUES ({placeholders})',
        f'-- × {row_count} 行',
    ]
    return "\n".join(lines)



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


@app.post("/api/databases/switch")
def switch_database(req: SwitchDatabaseRequest):
    """切换当前数据库"""
    ag = _require_agent()
    try:
        ag.db.connect_to_db(req.database)
        # 重新扫描数据库结构
        ag.scan_all_databases()
        return {
            "success": True,
            "message": f"已切换到 {req.database}",
            "current": ag.db.current_db,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/databases/{db}/tables")
def get_tables(db: str):
    """获取指定数据库的表列表"""
    ag = _require_agent()
    try:
        tables = ag.db.list_tables(db)
        return {"database": db, "tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/databases/{db}/tables/{table}")
def describe_table_endpoint(db: str, table: str):
    """获取表结构详情"""
    ag = _require_agent()
    try:
        columns = ag.db.describe_table(table, db)
        return {
            "database": db,
            "table": table,
            "columns": [
                {"name": c[0], "type": c[1], "constraints": c[2]}
                for c in columns
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
def health_check():
    """健康检查：返回数据库和 LLM 连接状态"""
    ag_instance = agent
    if ag_instance is None:
        return {"db_connected": False, "llm_connected": False, "current_db": ""}

    # 检查数据库连接
    db_ok = False
    try:
        db_ok = not ag_instance.db._is_closed()
    except Exception:
        pass

    # 检查 LLM 连接
    llm_ok = False
    try:
        if ag_instance.llm.mode == "local":
            r = requests.get(f"{ag_instance.llm.base_url}/api/tags", timeout=3)
            llm_ok = r.status_code == 200
        else:
            headers = {}
            if ag_instance.llm.api_key:
                headers["Authorization"] = f"Bearer {ag_instance.llm.api_key}"
            r = requests.get(
                f"{ag_instance.llm.base_url}/v1/models",
                headers=headers,
                timeout=3,
            )
            llm_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "db_connected": db_ok,
        "llm_connected": llm_ok,
        "current_db": ag_instance.db.current_db,
    }


@app.post("/api/query/paginate")
def paginate_query(req: PaginateRequest):
    """分页查询：对已有 SQL 进行分页"""
    ag = _require_agent()
    try:
        # 获取总数
        base_sql = req.sql.rstrip(";")
        count_sql = f"SELECT COUNT(*) FROM ({base_sql}) AS _count_subquery"
        _, count_rows = ag.db.execute_query(count_sql)
        total = count_rows[0][0] if count_rows else 0

        # 分页查询
        offset = (req.page - 1) * req.page_size
        page_sql = f"{base_sql} LIMIT {req.page_size} OFFSET {offset}"
        columns, rows = ag.db.execute_query(page_sql)

        # 将行数据转为可序列化格式
        serializable_rows = [
            [str(v) if v is not None else None for v in row]
            for row in rows
        ]

        return {
            "columns": columns,
            "rows": serializable_rows,
            "total": total,
            "page": req.page,
            "page_size": req.page_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations/{conv_id}/execute")
def execute_sql_endpoint(conv_id: str, req: ExecuteRequest):
    """两阶段执行：用户确认后执行 SQL（支持 DDL 和文件导入）"""
    ag = _require_agent()

    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    try:
        # 文件导入操作
        if req.action == "import_file" and req.upload_id:
            file_data = upload_storage.get(req.upload_id)
            if not file_data:
                raise HTTPException(status_code=400, detail="上传文件已过期，请重新上传")

            plan = {
                "action": "import_file",
                "sql": req.sql,
                "explanation": "",
                "target_db": req.target_db or "",
                "target_table": req.target_table or "",
            }

            # 更新原消息状态为已执行
            store.update_message_status(conv_id, req.message_id, "executed")

            return _handle_import_file(ag, conv_id, plan, file_data, req.upload_id)

        # 普通 DDL/DML 操作
        plan = {
            "action": req.action,
            "sql": req.sql,
            "explanation": "",
            "target_db": req.target_db or "",
            "target_table": req.target_table or "",
            "success": False,
            "result": None,
            "error": "",
        }

        # 执行 SQL（跳过确认回调，因为用户已在前端确认）
        result = ag.execute_plan(plan, confirm_callback=None)

        # 更新原消息状态为已执行
        store.update_message_status(conv_id, req.message_id, "executed")

        # 构建 AI 回复消息
        return _build_ai_response(conv_id, result)

    except Exception as e:
        return store.add_message(
            conv_id,
            role="assistant",
            content="执行失败",
            error=str(e),
        )


@app.post("/api/conversations/{conv_id}/cancel/{message_id}")
def cancel_execution(conv_id: str, message_id: str):
    """取消待执行的 SQL 操作"""
    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 更新原消息状态为已取消
    store.update_message_status(conv_id, message_id, "cancelled")

    # 添加取消提示消息
    msg = store.add_message(
        conv_id,
        role="assistant",
        content="操作已取消",
        action="chat",
    )
    return msg or {"success": True}


@app.post("/api/conversations/{conv_id}/messages/stream")
def send_message_stream(conv_id: str, req: MessageRequest):
    """流式发送消息 (SSE)：实时返回 AI 思考过程"""
    ag = _require_agent()

    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    user_input = req.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # 保存用户消息
    store.add_message(conv_id, role="user", content=user_input)

    # 检查附件
    file_info_text = ""
    file_data = None
    if req.upload_id and req.upload_id in upload_storage:
        file_data = upload_storage[req.upload_id]
        file_info_text = (
            f"\n[附件信息] 文件名: {file_data['filename']}, "
            f"列名: {', '.join(file_data['columns'])}, "
            f"行数: {file_data['row_count']}"
        )

    def event_generator():
        try:
            # 流式思考阶段
            skill_context = ag.skill.get_summary()
            system_prompt = build_system_prompt(
                skill_context, ag.db.current_db, ag.db_type
            )

            full_response = ""
            for token in ag.llm.chat_stream(
                user_input + file_info_text, system_prompt
            ):
                full_response += token
                yield f"event: thinking\ndata: {json.dumps({'token': token})}\n\n"

            # 解析 LLM 响应
            parsed = ag.llm.parse_json_response(full_response)
            action = parsed.get("action", "chat")
            sql = parsed.get("sql", "").strip()
            explanation = parsed.get("explanation", "")
            target_db = parsed.get("database", "").strip()

            # 如果是文件导入：返回 pending 状态等待用户确认
            if action == "import_file" and file_data:
                target_table = parsed.get("target_table", "").strip()
                import_sql = sql or _build_import_preview_sql(target_table, file_data)
                plan_data = {
                    "action": action, "sql": import_sql,
                    "explanation": explanation,
                    "target_db": target_db,
                    "target_table": target_table,
                    "upload_id": req.upload_id,
                    "filename": file_data['filename'],
                }
                pending_msg = store.add_message(
                    conv_id,
                    role="assistant",
                    content=explanation or f"将附件 {file_data['filename']} 的数据导入到表 {target_table}",
                    sql=import_sql,
                    action=action,
                    status="pending",
                    plan=plan_data,
                )
                yield f"event: result\ndata: {json.dumps(pending_msg)}\n\n"
                yield f"event: done\ndata: {json.dumps({})}\n\n"
                return

            # DDL 操作：返回 pending 状态，让用户在前端确认
            if action in DDL_ACTIONS and sql:
                plan_data = {
                    "action": action,
                    "sql": sql,
                    "explanation": explanation,
                    "target_db": target_db,
                }
                msg = store.add_message(
                    conv_id,
                    role="assistant",
                    content=explanation,
                    sql=sql,
                    action=action,
                    status="pending",
                    plan=plan_data,
                )
                yield f"event: plan\ndata: {json.dumps(msg)}\n\n"
                yield f"event: done\ndata: {json.dumps({})}\n\n"
                return

            # 非 DDL：构建完整计划并直接执行
            plan = {
                "action": action,
                "sql": sql,
                "explanation": explanation,
                "target_db": target_db,
                "target_table": parsed.get("target_table", "").strip(),
                "success": action in ("chat",) or not sql,
                "result": explanation if (action == "chat" or not sql) else None,
                "error": "",
            }

            result = ag.execute_plan(plan, confirm_callback=None)
            result_msg = _build_ai_response(conv_id, result)
            yield f"event: result\ndata: {json.dumps(result_msg)}\n\n"
            yield f"event: done\ndata: {json.dumps({})}\n\n"

        except Exception as e:
            logger.error("SSE stream error: %s", e, exc_info=True)
            error_msg = store.add_message(
                conv_id,
                role="assistant",
                content="处理请求时发生错误",
                error=str(e),
            )
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            yield f"event: done\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
        tmp_dir = os.path.join(config.PROJECT_ROOT, ".uploads")
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
