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

## {db_type_display} 特定规则：
{db_specific_rules}

## 当前数据库状态：
{skill_context}

## 当前数据库：{current_db}
"""


def build_system_prompt(skill_context: str, current_db: str, db_type: str = "postgresql") -> str:
    """
    构建完整的系统提示词

    Args:
        skill_context: skill.md 的内容摘要
        current_db: 当前连接的数据库名
        db_type: 数据库类型

    Returns:
        完整的系统提示词
    """
    db_type_display = {
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "oracle": "Oracle",
    }.get(db_type, "PostgreSQL")

    db_specific_rules = DB_SPECIFIC_RULES.get(db_type, DB_SPECIFIC_RULES["postgresql"])

    return SYSTEM_PROMPT.format(
        db_type_display=db_type_display,
        db_specific_rules=db_specific_rules,
        skill_context=skill_context,
        current_db=current_db,
    )
