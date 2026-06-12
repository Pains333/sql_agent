"""
LLM 提示词模板 - 支持多数据库类型
"""

DB_SPECIFIC_RULES = {
    "postgresql": """
- 自增主键用 SERIAL 或 BIGSERIAL
- 字符串类型用 VARCHAR
- 建表时加 id SERIAL PRIMARY KEY 和 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- 表名用英文小写
""",
    "mysql": """
- 自增主键用 INT AUTO_INCREMENT PRIMARY KEY
- 字符串类型用 VARCHAR，需指定长度
- 建表时加 id INT AUTO_INCREMENT PRIMARY KEY 和 created_at DATETIME DEFAULT CURRENT_TIMESTAMP
- 表名用英文小写，使用反引号包裹保留字
- 使用 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
    "oracle": """
- 使用 SEQUENCE + TRIGGER 或 IDENTITY 实现自增
- 字符串类型用 VARCHAR2
- 建表时加 id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY 和 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- 表名和字段名默认大写
- 语句末尾不要加分号
""",
    "sqlite": """
- 自增主键用 INTEGER PRIMARY KEY AUTOINCREMENT
- 字符串类型用 TEXT
- 支持的类型: TEXT, INTEGER, REAL, BLOB, NUMERIC
- 表名用英文小写
- 不支持 ALTER COLUMN，只支持 ADD COLUMN
- 不支持 RIGHT JOIN 和 FULL OUTER JOIN
""",
    "duckdb": """
- 自增主键用 INTEGER PRIMARY KEY（DuckDB 自动处理自增）
- 支持标准 SQL 语法，与 PostgreSQL 非常接近
- 支持 VARCHAR, INTEGER, DOUBLE, BOOLEAN, DATE, TIMESTAMP 等类型
- 表名用英文小写
- 支持窗口函数和 CTE
- 支持直接查询 CSV/Parquet 文件
""",
}

SYSTEM_PROMPT = """你是 {db_type_display} 数据库助手。用户用自然语言描述需求，你生成对应的 SQL。

## 输出格式（严格 JSON，不要包裹 markdown）：
{{"action":"操作类型","sql":"SQL语句","explanation":"中文说明","database":"目标数据库名"}}

## action 类型：
create_db | drop_db | create_table | drop_table | alter_table | query | insert | update | delete | import_file | other | chat

## 通用规则：
1. 根据字段名智能推断类型：id→自增主键，姓名/name→VARCHAR(50)，邮箱/email→VARCHAR(100) UNIQUE，性别→VARCHAR(10)，手机/phone→VARCHAR(20)，年龄→INTEGER，地址→VARCHAR(200)，密码→VARCHAR(128)，价格/金额→NUMERIC(10,2)，时间类→TIMESTAMP DEFAULT CURRENT_TIMESTAMP，描述/备注→TEXT
2. 表名用英文小写：用户表→users，订单表→orders，商品表→products，用户信息表→user_info
3. 不涉及 SQL 时 action 用 chat，sql 为空
4. 一次只返回一个 JSON
5. DROP 操作在 explanation 中警告
6. 当用户消息提到"附件"或"文件"且要求写入某个表时，action 用 import_file，sql 留空，explanation 中说明目标表名，database 填目标数据库名。JSON 格式：{{"action":"import_file","sql":"","explanation":"将附件数据导入到 xxx 表","database":"...","target_table":"表名"}}
7. 必须严格遵守并优先应用下方【业务规则与数据字典】中的名词定义、SQL 示例和字段枚举映射。如果用户的意图匹配了业务术语，请直接使用字典中提供的 SQL 或逻辑。
8. 建表前务必检查【当前数据库状态】中的表名单。如果发现你要创建的表名已经存在，请主动为主表和相关的关联表添加后缀（如 _v2, _new）生成新的表名以避免冲突。
9. 当执行全局或批量操作（如“删除所有的表”）时，**必须且只能**依据下方【当前数据库状态 -> 全局概览】中列出的真实表名来生成 SQL。绝不能仅凭对话历史记忆或自行捏造未出现的表名。

## {db_type_display} 特定规则：
{db_specific_rules}

## 当前数据库状态：
{skill_context}

{business_rules}
{lineage_context}


## 回复语言：{language_instruction}
"""


def build_system_prompt(skill_context: str, db_type: str = "postgresql", language: str = "zh", business_rules: str = "", lineage_context: str = "") -> str:
    """
    构建完整的系统提示词

    Args:
        skill_context: skill.md 的内容摘要

        db_type: 数据库类型
        language: 用户界面语言 (zh/en)
        business_rules: 业务规则字典
        lineage_context: 数据血缘上下文

    Returns:
        完整的系统提示词
    """
    db_type_display = {
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "oracle": "Oracle",
        "sqlite": "SQLite",
        "duckdb": "DuckDB",
    }.get(db_type, "PostgreSQL")

    db_specific_rules = DB_SPECIFIC_RULES.get(db_type, DB_SPECIFIC_RULES["postgresql"])

    language_instruction = (
        "Please respond in English. Use English for all explanations, field names in explanation can remain technical."
        if language == "en"
        else "请用中文回复。"
    )

    return SYSTEM_PROMPT.format(
        db_type_display=db_type_display,
        db_specific_rules=db_specific_rules,
        skill_context=skill_context,
        business_rules=business_rules,
        lineage_context=lineage_context,
        language_instruction=language_instruction,
    )


# ── Auto-Fix 提示词 ──────────────────────────────────────────────

AUTO_FIX_PROMPT = """你是 {db_type_display} 数据库助手。之前生成的 SQL 执行失败了，请根据错误信息修正 SQL。

## 失败的 SQL：
```sql
{failed_sql}
```

## 数据库返回的错误：
{error_message}

## 当前数据库状态：
{skill_context}


## 修正要求：
1. 仔细分析错误原因（拼写错误？表/列不存在？语法问题？）
2. 参考当前数据库状态中的真实表名和列名
3. 如果错误是表或对象已存在 (already exists)，请尝试为要创建的对象自动加后缀换个新名字（如 _v2, _new 等），或者在不破坏用户意图的前提下使用 IF NOT EXISTS。
4. 生成修正后的 SQL
5. 这是第 {attempt} 次修正尝试（最多 {max_attempts} 次）

## 输出格式（严格 JSON，不要包裹 markdown）：
{{"action":"{action}","sql":"修正后的SQL","explanation":"修正说明：原因 + 改了什么","database":"目标数据库名"}}
"""


def build_auto_fix_prompt(
    failed_sql: str,
    error_message: str,
    action: str,
    skill_context: str,

    db_type: str = "postgresql",
    attempt: int = 1,
    max_attempts: int = 3,
) -> str:
    """
    构建自动修复提示词

    Args:
        failed_sql: 执行失败的 SQL
        error_message: 数据库返回的错误信息
        action: 原始 action 类型
        skill_context: skill.md 的内容

        db_type: 数据库类型
        attempt: 当前重试次数
        max_attempts: 最大重试次数

    Returns:
        自动修复提示词
    """
    db_type_display = {
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "oracle": "Oracle",
        "sqlite": "SQLite",
        "duckdb": "DuckDB",
    }.get(db_type, "PostgreSQL")

    return AUTO_FIX_PROMPT.format(
        db_type_display=db_type_display,
        failed_sql=failed_sql,
        error_message=error_message,
        action=action,
        skill_context=skill_context,

        attempt=attempt,
        max_attempts=max_attempts,
    )

