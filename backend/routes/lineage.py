from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import uuid

from backend.state import require_agent

router = APIRouter()

class LineageEntryCreate(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    transform_logic: str = ""

class LineageEntryUpdate(LineageEntryCreate):
    pass

class ParseSqlRequest(BaseModel):
    sql: str

@router.get("/api/lineage")
def get_lineage():
    ag = require_agent()
    return ag.lineage.list_lineage()

@router.post("/api/lineage")
def create_lineage(req: LineageEntryCreate):
    ag = require_agent()
    entry = ag.lineage.add_lineage(
        req.source_table,
        req.source_column,
        req.target_table,
        req.target_column,
        req.transform_logic,
    )
    return {"success": True, "data": entry}

@router.put("/api/lineage/{entry_id}")
def update_lineage(entry_id: str, req: LineageEntryUpdate):
    ag = require_agent()
    entry = ag.lineage.update_lineage(
        entry_id,
        req.source_table,
        req.source_column,
        req.target_table,
        req.target_column,
        req.transform_logic,
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Lineage entry not found")
    return {"success": True, "data": entry}

@router.delete("/api/lineage/{entry_id}")
def delete_lineage(entry_id: str):
    ag = require_agent()
    success = ag.lineage.delete_lineage(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lineage entry not found")
    return {"success": True}

# 在内存中保存任务状态。如果在生产环境建议使用 Redis 或数据库。
parse_tasks = {}

def process_lineage_task(task_id: str, sql: str, ag):
    from backend.core.logging_config import get_logger
    logger = get_logger(__name__)
    
    try:
        parsed = ag.lineage.parse_sql_lineage(sql, ag.llm)
        logger.info("Task %s: parse_sql_lineage returned %d items", task_id, len(parsed))
        
        if not parsed:
            parse_tasks[task_id]["status"] = "error"
            parse_tasks[task_id]["error"] = "未能从 SQL 中提取到血缘关系，或 SQL 语法不受支持。"
            return

        saved_entries = []
        for item in parsed:
            entry = ag.lineage.add_lineage(
                item.get("source_table", ""),
                item.get("source_column", ""),
                item.get("target_table", ""),
                item.get("target_column", ""),
                item.get("transform_logic", "")
            )
            saved_entries.append(entry)

        logger.info("Task %s: Successfully saved %d entries", task_id, len(saved_entries))
        parse_tasks[task_id]["status"] = "success"
        parse_tasks[task_id]["data"] = saved_entries

    except Exception as e:
        logger.exception("Exception in background task %s: %s", task_id, e)
        parse_tasks[task_id]["status"] = "error"
        parse_tasks[task_id]["error"] = f"解析过程发生异常: {str(e)}"

@router.post("/api/lineage/parse")
def parse_sql_lineage(req: ParseSqlRequest, background_tasks: BackgroundTasks):
    ag = require_agent()
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="SQL cannot be empty")
    
    task_id = str(uuid.uuid4())
    parse_tasks[task_id] = {"status": "processing", "data": None, "error": None}
    
    background_tasks.add_task(process_lineage_task, task_id, req.sql, ag)
    
    return {"success": True, "task_id": task_id}

@router.get("/api/lineage/task/{task_id}")
def get_parse_task_status(task_id: str):
    task = parse_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": task}
