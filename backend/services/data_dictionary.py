import os
import json
import uuid
from datetime import datetime
from backend.core import config
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

class DataDictionary:
    """业务字典管理器：管理业务规则，供 LLM 参考"""
    
    def __init__(self):
        self.file_path = os.path.join(config.PROJECT_ROOT, "data_dictionary.json")
        self.entries: list[dict] = []
        self._load()
    
    def _load(self):
        """从 JSON 文件加载字典"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception as e:
                logger.error("加载业务字典失败: %s", e)
                self.entries = []
        else:
            self.entries = []
            
    def _save(self):
        """保存字典到 JSON 文件"""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存业务字典失败: %s", e)
            raise

    def list_entries(self, db_name: str = None) -> list[dict]:
        if not db_name:
            return self.entries
        return [e for e in self.entries if e.get("db_name") in (None, "", db_name)]
        
    def add_entry(self, term: str, definition: str, sql_hint: str = "", field_mappings: dict = None, db_name: str = "") -> dict:
        entry = {
            "id": str(uuid.uuid4()),
            "db_name": db_name,
            "term": term,
            "definition": definition,
            "sql_hint": sql_hint or "",
            "field_mappings": field_mappings or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.entries.append(entry)
        self._save()
        return entry
        
    def update_entry(self, entry_id: str, **kwargs) -> dict:
        for entry in self.entries:
            if entry["id"] == entry_id:
                if "term" in kwargs:
                    entry["term"] = kwargs["term"]
                if "definition" in kwargs:
                    entry["definition"] = kwargs["definition"]
                if "sql_hint" in kwargs:
                    entry["sql_hint"] = kwargs["sql_hint"]
                if "field_mappings" in kwargs:
                    entry["field_mappings"] = kwargs["field_mappings"]
                entry["updated_at"] = datetime.now().isoformat()
                self._save()
                return entry
        raise ValueError("未找到指定字典条目")
        
    def delete_entry(self, entry_id: str) -> bool:
        initial_len = len(self.entries)
        self.entries = [e for e in self.entries if e["id"] != entry_id]
        if len(self.entries) < initial_len:
            self._save()
            return True
        return False
        
    def get_context_for_prompt(self, db_name: str = None) -> str:
        """生成供注入系统提示词的上下文"""
        entries = self.list_entries(db_name)
        if not entries:
            return ""
            
        lines = ["## 业务规则与数据字典 (Business Rules & Data Dictionary)"]
        for e in entries:
            lines.append(f"\n### {e['term']}")
            lines.append(f"- **定义**: {e['definition']}")
            if e.get('sql_hint'):
                lines.append(f"- **SQL 示例/提示**: {e['sql_hint']}")
            if e.get('field_mappings'):
                mapping_str = ", ".join([f"{k} -> {v}" for k, v in e['field_mappings'].items()])
                lines.append(f"- **字段映射**: {mapping_str}")
                
        return "\n".join(lines)
