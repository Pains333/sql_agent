"""
数据导入器 - 将解析后的文件数据导入数据库表
包含列匹配逻辑：
- 自增字段跳过
- NOT NULL 字段必须匹配
- 可空字段缺失时填 NULL
- 多余列不写入
"""

from typing import Optional


# 用于识别自增字段的关键词
AUTO_INCREMENT_KEYWORDS = {
    "serial", "bigserial", "nextval",           # PostgreSQL
    "auto_increment",                            # MySQL
    "identity", "generated always as identity",  # Oracle
}


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
        {
            "success": bool,
            "message": str,
            "inserted": int,          # 成功插入行数
            "skipped_columns": list,  # 跳过的附件列
            "null_columns": list,     # 填充 NULL 的表列
            "auto_columns": list,     # 自增列（跳过）
        }
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

        # 4. 构建并执行 INSERT
        insert_columns = match_result["insert_columns"]  # 要写入的列名列表
        column_mapping = match_result["column_mapping"]   # 表列名 → 文件列索引 (或 None 表示填 NULL)

        if not insert_columns:
            result["message"] = "没有可匹配的列，无法导入数据"
            return result

        # 5. 批量插入
        inserted = _batch_insert(
            db_client=db_client,
            table_name=table_name,
            insert_columns=insert_columns,
            column_mapping=column_mapping,
            file_columns=file_data["columns"],
            rows=file_data["rows"],
        )

        result["success"] = True
        result["inserted"] = inserted

        # 构建详细消息
        msg_parts = [f"成功导入 {inserted} 行数据到表 `{table_name}`"]
        if result["auto_columns"]:
            msg_parts.append(f"自增字段已跳过: {', '.join(result['auto_columns'])}")
        if result["null_columns"]:
            msg_parts.append(f"以下可空字段填充 NULL: {', '.join(result['null_columns'])}")
        if result["skipped_columns"]:
            msg_parts.append(f"以下附件列未匹配表字段，已跳过: {', '.join(result['skipped_columns'])}")
        result["message"] = "。\n".join(msg_parts)

    except Exception as e:
        result["message"] = f"导入失败: {e}"

    return result


def _analyze_table_columns(table_columns: list) -> list:
    """
    分析表结构，标记每个字段的属性

    Args:
        table_columns: describe_table 返回的 [(col_name, full_type, constraints), ...]

    Returns:
        [{
            "name": str,
            "type": str,
            "is_nullable": bool,
            "is_auto_increment": bool,
            "is_primary_key": bool,
        }, ...]
    """
    result = []
    for col_name, col_type, constraints in table_columns:
        constraints_lower = constraints.lower() if constraints else ""
        col_type_lower = col_type.lower() if col_type else ""

        is_auto = False
        # 检查类型名是否包含自增关键词
        for kw in AUTO_INCREMENT_KEYWORDS:
            if kw in col_type_lower or kw in constraints_lower:
                is_auto = True
                break

        is_nullable = "not null" not in constraints_lower and "primary key" not in constraints_lower
        is_pk = "primary key" in constraints_lower

        # 自增主键一定可以跳过
        if is_auto and is_pk:
            is_nullable = True  # 视为可跳过

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
        {
            "error": str or None,
            "insert_columns": [str, ...],       # 要写入的表列名
            "column_mapping": {str: int or None}, # 表列名 → 文件列索引
            "skipped_columns": [str, ...],       # 跳过的附件列
            "null_columns": [str, ...],          # 填充 NULL 的表列
            "auto_columns": [str, ...],          # 自增列
        }
    """
    # 文件列名（小写映射到原始索引）
    file_col_map = {}
    for i, col in enumerate(file_columns):
        file_col_map[col.lower().strip()] = i

    insert_columns = []
    column_mapping = {}
    null_columns = []
    auto_columns = []
    missing_required = []

    for col_info in table_info:
        col_name = col_info["name"]
        col_name_lower = col_name.lower().strip()

        # 自增字段 → 跳过
        if col_info["is_auto_increment"]:
            auto_columns.append(col_name)
            continue

        if col_name_lower in file_col_map:
            # 匹配成功
            insert_columns.append(col_name)
            column_mapping[col_name] = file_col_map[col_name_lower]
        elif col_info["is_nullable"]:
            # 可空字段缺失 → 填 NULL
            insert_columns.append(col_name)
            column_mapping[col_name] = None
            null_columns.append(col_name)
        else:
            # NOT NULL 字段缺失 → 报错
            missing_required.append(col_name)

    if missing_required:
        return {
            "error": f"以下 NOT NULL 字段在附件中未找到匹配列: {', '.join(missing_required)}。请检查附件列名或修改表结构。",
            "insert_columns": [],
            "column_mapping": {},
            "skipped_columns": [],
            "null_columns": [],
            "auto_columns": auto_columns,
        }

    # 找出附件中多余的列（不在表结构中的）
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
    }


def _batch_insert(
    db_client,
    table_name: str,
    insert_columns: list,
    column_mapping: dict,
    file_columns: list,
    rows: list,
    batch_size: int = 100,
) -> int:
    """
    批量插入数据

    Returns:
        成功插入的行数
    """
    db_type = db_client.db_type
    total_inserted = 0

    # 构建列名部分
    if db_type == "mysql":
        col_str = ", ".join(f"`{c}`" for c in insert_columns)
    elif db_type == "oracle":
        col_str = ", ".join(f'"{c}"' for c in insert_columns)
    else:
        col_str = ", ".join(f'"{c}"' for c in insert_columns)

    # 分批插入
    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start:batch_start + batch_size]

        for row in batch:
            values = []
            for col_name in insert_columns:
                file_idx = column_mapping.get(col_name)
                if file_idx is None:
                    values.append(None)
                else:
                    values.append(row[file_idx])

            # 构建参数化 SQL
            _execute_single_insert(db_client, table_name, col_str, insert_columns, values)
            total_inserted += 1

    return total_inserted


def _execute_single_insert(db_client, table_name: str, col_str: str, columns: list, values: list):
    """执行单行插入（使用参数化查询防止 SQL 注入）"""
    db_type = db_client.db_type
    cursor = db_client.conn.cursor()

    try:
        if db_type == "postgresql":
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f'INSERT INTO "{table_name}" ({col_str}) VALUES ({placeholders})'
            cursor.execute(sql, values)
        elif db_type == "mysql":
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO `{table_name}` ({col_str}) VALUES ({placeholders})"
            cursor.execute(sql, values)
        elif db_type == "oracle":
            placeholders = ", ".join([f":{i+1}" for i in range(len(columns))])
            sql = f'INSERT INTO "{table_name}" ({col_str}) VALUES ({placeholders})'
            cursor.execute(sql, values)
    except Exception as e:
        raise RuntimeError(f"插入数据失败: {e}")
    finally:
        cursor.close()
