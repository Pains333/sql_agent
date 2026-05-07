"""
Skill 管理器 - 管理 skill.md 文件的读写
记录数据库和表的元信息
"""

import os
import re
from datetime import datetime
import config


class SkillManager:
    """管理 skill.md 文件"""

    def __init__(self):
        self.file_path = config.SKILL_FILE_PATH
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """确保 skill.md 文件存在"""
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("# 数据库元信息\n\n> 此文件由 SQL Agent 自动维护，记录所有数据库和表的结构信息。\n")

    def read(self) -> str:
        """读取 skill.md 内容"""
        self._ensure_file_exists()
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, content: str):
        """写入 skill.md 内容"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def add_database(self, db_name: str, encoding: str = "UTF8"):
        """
        添加数据库记录

        Args:
            db_name: 数据库名
            encoding: 字符集编码
        """
        content = self.read()

        # 检查是否已存在
        if f"## 数据库: {db_name}" in content:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        db_section = f"\n---\n\n## 数据库: {db_name}\n\n"
        db_section += f"- **字符集**: {encoding}\n"
        db_section += f"- **创建时间**: {today}\n"

        content += db_section
        self.write(content)

    def remove_database(self, db_name: str):
        """
        删除数据库记录（包括其下所有表）

        Args:
            db_name: 数据库名
        """
        content = self.read()

        # 匹配从 "---\n\n## 数据库: xxx" 到下一个 "---" 或文件末尾的所有内容
        # 先尝试匹配带分隔线的
        pattern = r'\n---\n\n## 数据库: ' + re.escape(db_name) + r'\n.*?(?=\n---\n|$)'
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)

        # 如果没有变化，尝试不带前导分隔线的模式
        if new_content == content:
            pattern = r'## 数据库: ' + re.escape(db_name) + r'\n.*?(?=\n---\n|$)'
            new_content = re.sub(pattern, '', content, flags=re.DOTALL)

        # 清理多余空行
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)
        self.write(new_content)

    def add_table(self, db_name: str, table_name: str, columns: list):
        """
        添加表记录

        Args:
            db_name: 数据库名
            table_name: 表名
            columns: 字段列表 [(name, type, constraints), ...]
        """
        content = self.read()

        # 确保数据库部分存在
        if f"## 数据库: {db_name}" not in content:
            self.add_database(db_name)
            content = self.read()

        # 检查表是否已存在，如果存在先删除旧记录
        if f"### 表: {table_name}" in content:
            self._remove_table_from_content(db_name, table_name)
            content = self.read()

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

        # 找到这个数据库部分之后的下一个 "---" 分隔线
        next_separator = content.find("\n---\n", db_pos + len(db_header))

        if next_separator != -1:
            # 在下一个分隔线之前插入
            content = content[:next_separator] + table_section + content[next_separator:]
        else:
            # 追加到文件末尾
            content += table_section

        self.write(content)

    def remove_table(self, db_name: str, table_name: str):
        """
        删除表记录

        Args:
            db_name: 数据库名
            table_name: 表名
        """
        self._remove_table_from_content(db_name, table_name)

    def _remove_table_from_content(self, db_name: str, table_name: str):
        """从 skill.md 中移除指定表"""
        content = self.read()

        # 匹配表部分：从 "### 表: xxx" 到下一个 "###" 或 "---" 或文件末尾
        pattern = r'\n### 表: ' + re.escape(table_name) + r'\n.*?(?=\n### |\n---|$)'
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)

        # 清理多余空行
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)
        self.write(new_content)

    def update_table(self, db_name: str, table_name: str, columns: list):
        """
        更新表记录（删除旧记录后重新添加）

        Args:
            db_name: 数据库名
            table_name: 表名
            columns: 新的字段列表
        """
        self.add_table(db_name, table_name, columns)

    def get_summary(self) -> str:
        """
        获取 skill.md 的简短摘要（用于 LLM 上下文）

        Returns:
            摘要文本
        """
        content = self.read()
        if content.strip() == "# 数据库元信息\n\n> 此文件由 SQL Agent 自动维护，记录所有数据库和表的结构信息。".strip():
            return "当前没有已记录的数据库和表信息。"
        return content
