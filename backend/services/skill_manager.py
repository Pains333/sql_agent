"""
Skill 管理器 - 管理 skill.md 文件的读写
记录数据库和表的元信息
"""

import os
import re
from datetime import datetime

from backend.core import config
from backend.core.logging_config import get_logger
from backend.services.table_retriever import TableRetriever

logger = get_logger(__name__)

# skill.md 默认内容（全局唯一，供 server.py / agent.py 引用）
DEFAULT_SKILL_CONTENT = (
    "# 数据库元信息\n\n"
    "> 此文件由 SQL Agent 自动维护，记录所有数据库和表的结构信息。\n"
)


class SkillManager:
    """管理 skill.md 文件"""

    def __init__(self):
        self.file_path = config.SKILL_FILE_PATH
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """确保 skill.md 文件存在"""
        if not os.path.exists(self.file_path):
            self._write(DEFAULT_SKILL_CONTENT)

    def read(self) -> str:
        """读取 skill.md 内容"""
        self._ensure_file_exists()
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _write(self, content: str) -> None:
        """写入 skill.md 内容"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(content)

    # 保留 public write 作为兼容接口
    write = _write

    def reset(self) -> None:
        """重置 skill.md 为默认内容"""
        self._write(DEFAULT_SKILL_CONTENT)

    def add_database(self, db_name: str, encoding: str = "UTF8") -> None:
        """添加数据库记录"""
        content = self.read()

        if f"## 数据库: {db_name}" in content:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        db_section = (
            f"\n---\n\n## 数据库: {db_name}\n\n"
            f"- **字符集**: {encoding}\n"
            f"- **创建时间**: {today}\n"
        )

        self._write(content + db_section)

    def remove_database(self, db_name: str) -> None:
        """删除数据库记录（包括其下所有表）"""
        content = self.read()

        # 匹配从 "---\n\n## 数据库: xxx" 到下一个 "---" 或文件末尾
        pattern = r'\n---\n\n## 数据库: ' + re.escape(db_name) + r'\n.*?(?=\n---\n|$)'
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)

        # 如果没有变化，尝试不带前导分隔线的模式
        if new_content == content:
            pattern = r'## 数据库: ' + re.escape(db_name) + r'\n.*?(?=\n---\n|$)'
            new_content = re.sub(pattern, '', content, flags=re.DOTALL)

        new_content = re.sub(r'\n{3,}', '\n\n', new_content)
        self._write(new_content)

    def add_table(self, db_name: str, table_name: str, columns: list) -> None:
        """添加表记录（如已存在则先删除旧记录）"""
        content = self.read()

        # 确保数据库部分存在
        if f"## 数据库: {db_name}" not in content:
            self.add_database(db_name)
            content = self.read()

        # 如果表已存在，在内存中删除旧记录（避免额外文件 I/O）
        if f"### 表: {table_name}" in content:
            content = self._remove_table_from_text(content, table_name)

        # 构建表信息
        table_section = f"\n### 表: {table_name}\n\n"
        table_section += "| 字段名 | 类型 | 约束 |\n"
        table_section += "|--------|------|------|\n"
        for col_name, col_type, col_constraints in columns:
            table_section += f"| {col_name} | {col_type} | {col_constraints} |\n"

        # 找到数据库部分的末尾，在下一个 "---" 之前或文件末尾插入
        db_header = f"## 数据库: {db_name}"
        db_pos = content.find(db_header)

        if db_pos == -1:
            return

        next_separator = content.find("\n---\n", db_pos + len(db_header))

        if next_separator != -1:
            content = content[:next_separator] + table_section + content[next_separator:]
        else:
            content += table_section

        self._write(content)

    def remove_table(self, db_name: str, table_name: str) -> None:
        """删除表记录"""
        content = self.read()
        new_content = self._remove_table_from_text(content, table_name)
        if new_content != content:
            self._write(new_content)

    @staticmethod
    def _remove_table_from_text(content: str, table_name: str) -> str:
        """从内容文本中移除指定表（纯字符串操作，不涉及文件 I/O）"""
        pattern = r'\n### 表: ' + re.escape(table_name) + r'\n.*?(?=\n### |\n---|$)'
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)
        return re.sub(r'\n{3,}', '\n\n', new_content)

    def update_table(self, db_name: str, table_name: str, columns: list) -> None:
        """更新表记录（删除旧记录后重新添加）"""
        self.add_table(db_name, table_name, columns)

    def get_summary(self) -> str:
        """获取 skill.md 的完整内容（旧方法，为向后兼容保留）"""
        content = self.read()
        if content.strip() == DEFAULT_SKILL_CONTENT.strip():
            return "当前没有已记录的数据库和表信息。"
        return content

    def get_relevant_summary(self, query: str, max_tables: int = 15) -> str:
        """获取检索后相关的 skill.md 内容（用于 LLM 上下文）"""
        content = self.read()
        if content.strip() == DEFAULT_SKILL_CONTENT.strip():
            return "当前没有已记录的数据库和表信息。"

        if not query:
            return content

        # 解析 Markdown 结构
        tables_info = []
        current_db = ""
        current_table = ""
        current_schema = []

        lines = content.split('\n')
        for line in lines:
            if line.startswith('## 数据库:'):
                current_db = line.replace('## 数据库:', '').strip()
            elif line.startswith('### 表:'):
                if current_table and current_db:
                    tables_info.append({
                        "db": current_db,
                        "table": current_table,
                        "schema": "\n".join(current_schema),
                    })
                current_table = line.replace('### 表:', '').strip()
                current_schema = []
            elif current_table:
                current_schema.append(line)
        
        # 最后一个表
        if current_table and current_db:
            tables_info.append({
                "db": current_db,
                "table": current_table,
                "schema": "\n".join(current_schema),
            })

        # 如果表数量较少，直接返回完整内容
        if len(tables_info) <= max_tables:
            return content

        # 否则使用检索器
        retriever = TableRetriever(top_k=max_tables)
        retriever.build_index(tables_info)
        relevant_tables = retriever.retrieve(query)

        # 重建摘要内容
        summary_lines = ["# 数据库元信息 (检索结果)\n"]
        summary_lines.append(f"> 找到了 {len(relevant_tables)} 个与 '{query}' 相关的表。\n")
        
        # 按数据库对表进行分组
        db_tables = {}
        for info in relevant_tables:
            db_name = info["db"]
            if db_name not in db_tables:
                db_tables[db_name] = []
            db_tables[db_name].append(info)
            
        for db_name, tables in db_tables.items():
            summary_lines.append(f"\n## 数据库: {db_name}\n")
            for table in tables:
                summary_lines.append(f"\n### 表: {table['table']}\n")
                summary_lines.append(table['schema'])
                
        return "\n".join(summary_lines)
