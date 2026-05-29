"""
数据导入器 - 将解析后的文件数据导入数据库表
包含列匹配逻辑：
- 自增字段跳过
- NOT NULL 字段必须匹配
- 可空字段缺失时填 NULL
- 多余列不写入
"""

from datetime import datetime
from typing import Optional

from backend.core.exceptions import DataImportError
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

# 用于识别自增字段的关键词
AUTO_INCREMENT_KEYWORDS = {
    "serial", "bigserial", "nextval",           # PostgreSQL
    "auto_increment",                            # MySQL
    "identity", "generated always as identity",  # Oracle
}

# 批量插入的每批行数
BATCH_SIZE = 500

# 用于识别日期/时间字段的类型关键词
TIMESTAMP_TYPE_KEYWORDS = {
    "timestamp", "timestamptz", "datetime", "date", "time",
    "timestamp with time zone", "timestamp without time zone",
}

# 特殊标记：表示该列应自动填充当前时间
_SENTINEL_NOW = "_CURRENT_TIMESTAMP_"


def import_data_to_table(
    db_client,
    table_name: str,
    file_data: dict,
    database: Optional[str] = None,
) -> dict:
    """
    将文件数据导入到指定数据库表

    Args:
        db_client: DBClient 实例
        table_name: 目标表名
        file_data: file_parser 解析结果 {columns, rows, row_count}
        database: 目标数据库名（可选，默认当前数据库）

    Returns:
        {success, message, inserted, skipped_columns, null_columns, auto_columns}
    """
    result = {
        "success": False,
        "message": "",
        "inserted": 0,
        "skipped_columns": [],
        "null_columns": [],
        "auto_columns": [],
    }

    try:
        # 1. 获取表结构
        table_columns = db_client.describe_table(table_name, database)
        if not table_columns:
            result["message"] = f"表 '{table_name}' 不存在或没有字段"
            return result

        # 2. 分析表字段
        table_info = _analyze_table_columns(table_columns)

        # 3. 执行列匹配
        match_result = _match_columns(
            file_columns=file_data["columns"],
            table_info=table_info,
        )

        if match_result["error"]:
            result["message"] = match_result["error"]
            return result

        result["skipped_columns"] = match_result["skipped_columns"]
        result["null_columns"] = match_result["null_columns"]
        result["auto_columns"] = match_result["auto_columns"]

        insert_columns = match_result["insert_columns"]
        column_mapping = match_result["column_mapping"]

        if not insert_columns:
            result["message"] = "没有可匹配的列，无法导入数据"
            return result

        # 4. 批量插入
        inserted = _batch_insert(
            db_client=db_client,
            table_name=table_name,
            insert_columns=insert_columns,
            column_mapping=column_mapping,
            rows=file_data["rows"],
        )

        result["success"] = True
        result["inserted"] = inserted

        # 构建详细消息
        msg_parts = [f"成功导入 {inserted} 行数据到表 `{table_name}`"]
        if result["auto_columns"]:
            msg_parts.append(f"自增字段已跳过: {', '.join(result['auto_columns'])}")
        if match_result.get("timestamp_columns"):
            msg_parts.append(f"以下时间字段自动填充当前时间: {', '.join(match_result['timestamp_columns'])}")
        if result["null_columns"]:
            msg_parts.append(f"以下可空字段填充 NULL: {', '.join(result['null_columns'])}")
        if result["skipped_columns"]:
            msg_parts.append(f"以下附件列未匹配表字段，已跳过: {', '.join(result['skipped_columns'])}")
        result["message"] = "。\n".join(msg_parts)

        logger.info("数据导入完成: %s 行 → %s", inserted, table_name)

    except Exception as e:
        logger.error("数据导入失败: %s", e, exc_info=True)
        result["message"] = f"导入失败: {e}"

    return result


def _analyze_table_columns(table_columns: list) -> list:
    """
    分析表结构，标记每个字段的属性

    Returns:
        [{name, type, is_nullable, is_auto_increment, is_primary_key}, ...]
    """
    result = []
    for col_name, col_type, constraints in table_columns:
        constraints_lower = constraints.lower() if constraints else ""
        col_type_lower = col_type.lower() if col_type else ""

        is_auto = any(
            kw in col_type_lower or kw in constraints_lower
            for kw in AUTO_INCREMENT_KEYWORDS
        )

        is_nullable = "not null" not in constraints_lower and "primary key" not in constraints_lower
        is_pk = "primary key" in constraints_lower

        # 自增主键一定可以跳过
        if is_auto and is_pk:
            is_nullable = True

        result.append({
            "name": col_name,
            "type": col_type,
            "is_nullable": is_nullable,
            "is_auto_increment": is_auto,
            "is_primary_key": is_pk,
        })

    return result


def _match_columns(file_columns: list, table_info: list) -> dict:
    """
    执行列匹配逻辑

    Returns:
        {error, insert_columns, column_mapping, skipped_columns, null_columns, auto_columns, timestamp_columns}
    """
    # 文件列名（小写映射到原始索引）
    file_col_map = {
        col.lower().strip(): i
        for i, col in enumerate(file_columns)
    }

    insert_columns = []
    column_mapping = {}
    null_columns = []
    auto_columns = []
    timestamp_columns = []
    missing_required = []

    for col_info in table_info:
        col_name = col_info["name"]
        col_name_lower = col_name.lower().strip()

        # 自增字段 → 跳过
        if col_info["is_auto_increment"]:
            auto_columns.append(col_name)
            continue

        if col_name_lower in file_col_map:
            insert_columns.append(col_name)
            column_mapping[col_name] = file_col_map[col_name_lower]
        elif col_info["is_nullable"]:
            # 判断是否是日期/时间类型 → 自动填充当前时间
            col_type_lower = col_info["type"].lower() if col_info["type"] else ""
            is_time_col = any(kw in col_type_lower for kw in TIMESTAMP_TYPE_KEYWORDS)
            if is_time_col:
                insert_columns.append(col_name)
                column_mapping[col_name] = _SENTINEL_NOW
                timestamp_columns.append(col_name)
            else:
                insert_columns.append(col_name)
                column_mapping[col_name] = None
                null_columns.append(col_name)
        else:
            missing_required.append(col_name)

    if missing_required:
        return {
            "error": f"以下 NOT NULL 字段在附件中未找到匹配列: {', '.join(missing_required)}。请检查附件列名或修改表结构。",
            "insert_columns": [],
            "column_mapping": {},
            "skipped_columns": [],
            "null_columns": [],
            "auto_columns": auto_columns,
            "timestamp_columns": [],
        }

    table_col_names = {info["name"].lower().strip() for info in table_info}
    skipped_columns = [
        col for col in file_columns
        if col.lower().strip() not in table_col_names
    ]

    return {
        "error": None,
        "insert_columns": insert_columns,
        "column_mapping": column_mapping,
        "skipped_columns": skipped_columns,
        "null_columns": null_columns,
        "auto_columns": auto_columns,
        "timestamp_columns": timestamp_columns,
    }


def _build_row_values(row: list, insert_columns: list, column_mapping: dict) -> list:
    """为单行数据构建 VALUES 参数列表"""
    values = []
    now = datetime.now()
    for col in insert_columns:
        mapping = column_mapping.get(col)
        if mapping == _SENTINEL_NOW:
            values.append(now)
        elif mapping is not None:
            values.append(row[mapping])
        else:
            values.append(None)
    return values


def _batch_insert(
    db_client,
    table_name: str,
    insert_columns: list,
    column_mapping: dict,
    rows: list,
) -> int:
    """
    批量插入数据（使用 executemany，每批 BATCH_SIZE 行）
    自动处理唯一约束冲突（跳过重复行）

    Returns:
        成功插入的行数
    """
    # 构建列名部分
    quote = "`" if db_client.db_type == "mysql" else '"'
    col_str = ", ".join(f"{quote}{c}{quote}" for c in insert_columns)

    # 构建占位符
    if db_client.db_type == "oracle":
        placeholders = ", ".join(f":{i+1}" for i in range(len(insert_columns)))
    else:
        placeholders = ", ".join(["%s"] * len(insert_columns))

    # 构建冲突处理的 SQL
    if db_client.db_type == "postgresql":
        sql = f'INSERT INTO {quote}{table_name}{quote} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
    elif db_client.db_type == "mysql":
        sql = f'INSERT IGNORE INTO {quote}{table_name}{quote} ({col_str}) VALUES ({placeholders})'
    else:
        # Oracle: 普通 INSERT（逐行处理冲突）
        sql = f'INSERT INTO {quote}{table_name}{quote} ({col_str}) VALUES ({placeholders})'

    total_inserted = 0

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        values_list = [
            _build_row_values(row, insert_columns, column_mapping)
            for row in batch
        ]

        try:
            if db_client.db_type == "oracle":
                # Oracle 没有 ON CONFLICT，逐行插入跳过冲突
                inserted_count = 0
                for values in values_list:
                    try:
                        db_client.execute_many(sql, [values])
                        inserted_count += 1
                    except Exception:
                        # 跳过冲突行
                        continue
                total_inserted += inserted_count
            else:
                db_client.execute_many(sql, values_list)
                total_inserted += len(batch)
        except Exception as e:
            raise DataImportError(
                f"批量插入失败 (行 {batch_start+1}-{batch_start+len(batch)}): {e}"
            ) from e

        if batch_start > 0 and batch_start % (BATCH_SIZE * 10) == 0:
            logger.info("已插入 %d / %d 行", total_inserted, len(rows))

    return total_inserted

