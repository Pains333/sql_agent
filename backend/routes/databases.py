import re
import requests
from fastapi import APIRouter, HTTPException

from backend.models import PaginateRequest, ExplainRequest
from backend.state import require_agent, agent as _agent_ref, store
from backend.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _validate_identifier(name: str) -> str:
    """校验数据库/表标识符，防止 SQL 注入"""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,63}$', name):
        raise HTTPException(status_code=400, detail="无效的标识符名称")
    return name


def _safe_error(e: Exception, context: str = "操作") -> HTTPException:
    """返回脱敏的错误信息，详细错误仅记录日志"""
    logger.error("%s失败: %s", context, e, exc_info=True)
    return HTTPException(status_code=500, detail=f"{context}失败，请检查日志")


@router.get("/api/databases")
def list_databases():
    """获取数据库列表"""
    ag = require_agent()
    try:
        databases = ag.db.list_databases()
        current = ag.db.current_db
        return {"databases": databases, "current": current}
    except Exception as e:
        raise _safe_error(e, "获取数据库列表")




@router.get("/api/databases/{db}/tables")
def get_tables(db: str):
    """获取指定数据库的表列表"""
    ag = require_agent()
    _validate_identifier(db)
    try:
        tables = ag.db.list_tables(db)
        return {"database": db, "tables": tables}
    except Exception as e:
        raise _safe_error(e, "获取表列表")


@router.get("/api/databases/{db}/tables/{table}")
def describe_table_endpoint(db: str, table: str):
    """获取表结构详情"""
    ag = require_agent()
    _validate_identifier(db)
    _validate_identifier(table)
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
        raise _safe_error(e, "获取表结构")


@router.get("/api/databases/{db}/er-diagram")
def get_er_diagram(db: str):
    """获取整个数据库的 ER 图结构（表、字段、关系）"""
    ag = require_agent()
    _validate_identifier(db)
    try:
        ag.db._ensure_database(db)
        tables_names = ag.db.list_tables(db)
        
        tables = []
        for table in tables_names:
            cols = ag.db.describe_table(table, db)
            tables.append({
                "name": table,
                "columns": [
                    {"name": c[0], "type": c[1], "constraints": c[2]}
                    for c in cols
                ]
            })
            
        relationships = ag.db.get_foreign_keys(db)
        
        return {
            "database": db,
            "tables": tables,
            "relationships": relationships
        }
    except Exception as e:
        raise _safe_error(e, "获取ER图")


@router.get("/api/databases/{db}/tables/{table}/preview")
def preview_table_endpoint(db: str, table: str):
    """预览表数据 (前 50 行)"""
    ag = require_agent()
    _validate_identifier(db)
    _validate_identifier(table)
    try:
        # 白名单校验：确认表确实存在
        valid_tables = ag.db.list_tables(db)
        if table not in valid_tables:
            raise HTTPException(status_code=404, detail="表不存在")

        ag.db._ensure_database(db)
        if ag.db.db_type == "oracle":
            sql = f"SELECT * FROM {table} WHERE ROWNUM <= 50"
        else:
            sql = f"SELECT * FROM {table} LIMIT 50"
            
        columns, rows = ag.db.execute_query(sql)
        
        serializable_rows = [
            [str(v) if v is not None else None for v in row]
            for row in rows
        ]
        
        return {
            "database": db,
            "table": table,
            "columns": columns,
            "rows": serializable_rows,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(e, "预览表数据")


@router.get("/api/health")
def health_check():
    """健康检查：返回数据库和 LLM 连接状态"""
    import backend.state as st
    ag_instance = st.agent
    if ag_instance is None:
        return {"db_connected": False, "llm_connected": False, "current_db": ""}

    db_ok = False
    try:
        db_ok = not ag_instance.db._is_closed()
    except Exception:
        pass

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


@router.post("/api/query/paginate")
def paginate_query(req: PaginateRequest):
    """分页查询：对已有 SQL 进行分页"""
    ag = require_agent()
    try:
        base_sql = req.sql.rstrip(";")
        count_sql = f"SELECT COUNT(*) FROM ({base_sql}) AS _count_subquery"
        _, count_rows = ag.db.execute_query(count_sql)
        total = count_rows[0][0] if count_rows else 0

        offset = (req.page - 1) * req.page_size
        page_sql = f"{base_sql} LIMIT {req.page_size} OFFSET {offset}"
        columns, rows = ag.db.execute_query(page_sql)

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
        raise _safe_error(e, "分页查询")


@router.get("/api/skill")
def get_skill():
    """获取 skill.md 内容"""
    ag = require_agent()
    return {"content": ag.skill.read()}


@router.post("/api/query/explain")
def explain_sql(req: ExplainRequest):
    """分析 SQL 执行计划"""
    ag = require_agent()
    sql = req.sql.strip()
    
    if not sql.lower().startswith("select") and not sql.lower().startswith("with"):
        return {"columns": ["Message"], "rows": [["EXPLAIN is usually only valid for SELECT/WITH queries."]]}
        
    try:
        if req.database:
            ag.db._ensure_database(req.database)
        
        explain_sql = f"EXPLAIN {sql}"
        columns, rows = ag.db.execute_query(explain_sql)
        
        return {
            "columns": columns,
            "rows": [list(r) for r in rows]
        }
    except Exception as e:
        return {"error": str(e)}
