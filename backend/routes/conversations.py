import json
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models import MessageRequest, ConversationCreate, TitleUpdate, ExecuteRequest
from backend.state import require_agent, cleanup_expired_uploads, upload_storage, store
from backend.core.agent import DDL_ACTIONS
from backend.db.data_importer import import_data_to_table
from backend.llm.prompts import build_system_prompt
from backend.utils import format_query_result
from backend.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

# SQL 关键字到 action 的映射（后端重新判断，不信任前端）
_SQL_ACTION_MAP = [
    (r'^\s*(CREATE\s+TABLE)', 'create_table'),
    (r'^\s*(DROP\s+TABLE)', 'drop_table'),
    (r'^\s*(ALTER\s+TABLE)', 'alter_table'),
    (r'^\s*(CREATE\s+DATABASE)', 'create_db'),
    (r'^\s*(DROP\s+DATABASE)', 'drop_db'),
    (r'^\s*(INSERT)', 'insert'),
    (r'^\s*(UPDATE)', 'update'),
    (r'^\s*(DELETE)', 'delete'),
    (r'^\s*(SELECT|WITH)', 'query'),
]


def _detect_action(sql: str) -> str:
    """根据 SQL 内容重新判断 action 类型，防止前端篡改"""
    sql_upper = sql.strip()
    for pattern, action in _SQL_ACTION_MAP:
        if re.match(pattern, sql_upper, re.IGNORECASE):
            return action
    return 'other'


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
            result_text = format_query_result(columns, rows)
    elif isinstance(res, str):
        result_text = res

    # 构建自动修正元数据
    plan = None
    if result.get("auto_fixed"):
        plan = {
            "auto_fixed": True,
            "fix_attempts": result.get("fix_attempts", 0),
            "original_sql": result.get("original_sql", ""),
            "fix_explanation": result.get("fix_explanation", ""),
        }

    explanation = result.get("explanation", "")
    if result.get("auto_fixed"):
        fix_note = f"\n\n🔧 **SQL 已自动修正**（第 {result.get('fix_attempts')} 次尝试成功）\n{result.get('fix_explanation', '')}"
        explanation = (explanation or "") + fix_note

    return store.add_message(
        conv_id,
        role="assistant",
        content=explanation,
        sql=result.get("sql", ""),
        action=result.get("action", ""),
        result=result_text,
        plan=plan,
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

    upload_storage.pop(upload_id, None)

    if import_result["success"]:
        # 导入成功后，表可能被新建，需要更新 skill.md
        try:
            db_name = target_db or ag.db.current_db
            columns = ag.db.describe_table(target_table, db_name)
            ag.skill.add_table(db_name, target_table, columns)
        except Exception as e:
            from backend.core.logging_config import get_logger
            get_logger(__name__).warning("更新 skill.md 失败 (import_file): %s", e)

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


@router.get("/api/conversations")
def list_conversations(db_name: Optional[str] = None):
    """获取所有对话列表"""
    return store.list_conversations(db_name=db_name)


@router.post("/api/conversations")
def create_conversation(req: ConversationCreate):
    """创建新对话"""
    ag = require_agent()
    # 如果请求中未指定数据库，则默认使用当前 agent 所在的数据库
    db_name = req.database or ag.db.current_db
    return store.create_conversation(title=req.title, db_name=db_name)


@router.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    """获取对话详情（含所有消息）"""
    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """删除对话"""
    if not store.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"success": True}


@router.patch("/api/conversations/{conv_id}/title")
def update_conversation_title(conv_id: str, req: TitleUpdate):
    """更新对话标题"""
    if not store.update_title(conv_id, req.title):
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"success": True}


@router.post("/api/conversations/{conv_id}/messages")
def send_message(conv_id: str, req: MessageRequest):
    """发送用户消息，获取 AI 回复"""
    ag = require_agent()

    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    user_input = req.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    store.add_message(conv_id, role="user", content=user_input)

    cleanup_expired_uploads()

    try:
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
        plan = ag.think(user_input + file_info_text, language=req.language)

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

        return _build_ai_response(conv_id, result)

    except Exception as e:
        return store.add_message(
            conv_id,
            role="assistant",
            content="处理请求时发生错误",
            error=str(e),
        )


@router.post("/api/conversations/{conv_id}/execute")
def execute_sql_endpoint(conv_id: str, req: ExecuteRequest):
    """两阶段执行：用户确认后执行 SQL（支持 DDL 和文件导入）"""
    ag = require_agent()

    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    try:
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

            store.update_message_status(conv_id, req.message_id, "executed")

            return _handle_import_file(ag, conv_id, plan, file_data, req.upload_id)

        # 后端重新检测 action，不信任前端传入的 action
        detected_action = _detect_action(req.sql)

        plan = {
            "action": detected_action,
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

        store.update_message_status(conv_id, req.message_id, "executed")

        return _build_ai_response(conv_id, result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("执行 SQL 失败: %s", e, exc_info=True)
        return store.add_message(
            conv_id,
            role="assistant",
            content="执行失败",
            error="执行失败，请检查 SQL 语法或数据库连接",
        )


@router.post("/api/conversations/{conv_id}/cancel/{message_id}")
def cancel_execution(conv_id: str, message_id: str):
    """取消待执行的 SQL 操作"""
    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    store.update_message_status(conv_id, message_id, "cancelled")

    msg = store.add_message(
        conv_id,
        role="assistant",
        content="操作已取消",
        action="chat",
    )
    return msg or {"success": True}


@router.post("/api/conversations/{conv_id}/messages/stream")
def send_message_stream(conv_id: str, req: MessageRequest):
    """流式发送消息 (SSE)：实时返回 AI 思考过程"""
    ag = require_agent()

    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    user_input = req.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    store.add_message(conv_id, role="user", content=user_input)

    file_info_text = ""
    file_data = None
    if req.upload_id and req.upload_id in upload_storage:
        file_data = upload_storage[req.upload_id]
        file_info_text = (
            f"\n[附件信息] 文件名: {file_data['filename']}, "
            f"列名: {', '.join(file_data['columns'])}, "
            f"行数: {file_data['row_count']}"
        )

    # 提取最近对话历史，供大模型使用（排除掉系统消息和本次的用户输入）
    history = []
    if conv and "messages" in conv:
        for msg in conv["messages"][-16:]:
            if msg["role"] in ("user", "assistant"):
                history.append({"role": msg["role"], "content": msg["content"]})

    def event_generator():
        try:
            # 流式思考阶段
            skill_context = ag.skill.get_relevant_summary(user_input, max_tables=15)
            business_rules = ag.dictionary.get_context_for_prompt(ag.db.current_db)
            lineage_context = ag.lineage.get_context_for_prompt(ag.db.current_db)
            system_prompt = build_system_prompt(
                skill_context, ag.db.current_db, ag.db_type, language=req.language, business_rules=business_rules, lineage_context=lineage_context
            )

            full_response = ""
            for token in ag.llm.chat_stream(
                user_input + file_info_text, system_prompt, history=history
            ):
                full_response += token
                yield f"event: thinking\ndata: {json.dumps({'token': token})}\n\n"

            parsed = ag.llm.parse_json_response(full_response)
            action = parsed.get("action", "chat")
            sql = parsed.get("sql", "").strip()
            explanation = parsed.get("explanation", "")
            target_db = parsed.get("database", "").strip()

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

            # 所有 SQL 操作：返回 pending 状态，让用户在前端确认
            if action != "chat" and sql:
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
