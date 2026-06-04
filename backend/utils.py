def format_query_result(columns: list, rows: list) -> str:
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
