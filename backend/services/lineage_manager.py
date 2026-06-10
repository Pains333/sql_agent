import json
import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

class LineageManager:
    def __init__(self, storage_path="lineage.json"):
        self.storage_path = storage_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)

    def _load(self) -> List[Dict[str, Any]]:
        self._ensure_file()
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def _save(self, data: List[Dict[str, Any]]):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_lineage(self, db_name: str = None) -> List[Dict[str, Any]]:
        data = self._load()
        if not db_name:
            return data
        return [e for e in data if e.get("db_name") in (None, "", db_name)]

    def add_lineage(self, source_table: str, source_column: str, target_table: str, target_column: str, transform_logic: str, db_name: str = "") -> Dict[str, Any]:
        data = self._load()
        entry = {
            "id": str(uuid.uuid4()),
            "db_name": db_name,
            "source_table": source_table.strip(),
            "source_column": source_column.strip(),
            "target_table": target_table.strip(),
            "target_column": target_column.strip(),
            "transform_logic": transform_logic.strip(),
            "created_at": datetime.now().isoformat()
        }
        data.append(entry)
        self._save(data)
        return entry

    def update_lineage(self, entry_id: str, source_table: str, source_column: str, target_table: str, target_column: str, transform_logic: str) -> Optional[Dict[str, Any]]:
        data = self._load()
        for entry in data:
            if entry["id"] == entry_id:
                entry["source_table"] = source_table.strip()
                entry["source_column"] = source_column.strip()
                entry["target_table"] = target_table.strip()
                entry["target_column"] = target_column.strip()
                entry["transform_logic"] = transform_logic.strip()
                entry["updated_at"] = datetime.now().isoformat()
                self._save(data)
                return entry
        return None

    def delete_lineage(self, entry_id: str) -> bool:
        data = self._load()
        new_data = [e for e in data if e["id"] != entry_id]
        if len(data) != len(new_data):
            self._save(new_data)
            return True
        return False

    def get_context_for_prompt(self, db_name: str = None) -> str:
        lineage_data = self.list_lineage(db_name)
        if not lineage_data:
            return ""

        lines = ["=== Business Data Lineage (数据血缘关系) ==="]
        lines.append("The following data lineage rules show how data flows between tables and how specific metrics are calculated:")
        for e in lineage_data:
            src = f"{e['source_table']}.{e['source_column']}"
            dst = f"{e['target_table']}.{e['target_column']}"
            logic = e.get("transform_logic", "")
            if logic:
                lines.append(f"- {dst} is derived from {src} using logic: {logic}")
            else:
                lines.append(f"- {dst} is mapped directly from {src}")
        return "\n".join(lines) + "\n"

    def parse_sql_lineage(self, sql: str, llm_client) -> List[Dict[str, str]]:
        """
        Use the LLM to parse a complex SQL statement and extract lineage.
        """
        system_prompt = """You are a data lineage extraction tool.
Given a SQL statement (e.g. CREATE TABLE AS SELECT, or INSERT INTO SELECT, or a View definition),
extract the data lineage mappings from source tables/columns to target tables/columns.
If the SQL creates a table or view, the target_table is that new table/view.
If it's an INSERT, the target is the table being inserted into.
Identify the source_table, source_column, target_table, target_column, and transform_logic for each mapping.
If multiple sources feed into one target column, try to capture the main ones or summarize.
Return a JSON array of objects. NO Markdown formatting, just the raw JSON array.
Format:
[
  {
    "source_table": "str",
    "source_column": "str",
    "target_table": "str",
    "target_column": "str",
    "transform_logic": "str (e.g. SUM(), LEFT JOIN condition, direct copy, etc.)"
  }
]
"""
        user_prompt = f"Extract lineage from this SQL:\n\n{sql}"
        
        try:
            response = llm_client.chat(user_prompt, system_prompt=system_prompt)
            from backend.core.logging_config import get_logger
            logger = get_logger(__name__)
            logger.info("Raw LLM response for lineage parse:\n%s", response)
            
            try:
                parsed = json.loads(response)
                if isinstance(parsed, list):
                    logger.info("parse_sql_lineage returning direct json list of size %d", len(parsed))
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning("Direct json.loads failed: %s", e)
                pass

            import re
            json_patterns = [
                r'```json\s*\n(.*?)\n\s*```',
                r'```\s*\n(.*?)\n\s*```',
                r'\[\s*\{.*\}\s*\]'
            ]
            for pattern in json_patterns:
                matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    # Clean up trailing commas
                    cleaned_match = re.sub(r',\s*\}', '}', match)
                    cleaned_match = re.sub(r',\s*\]', ']', cleaned_match)
                    try:
                        parsed = json.loads(cleaned_match)
                        if isinstance(parsed, list):
                            logger.info("parse_sql_lineage returning regex json list of size %d", len(parsed))
                            return parsed
                        elif isinstance(parsed, dict):
                            if "lineage" in parsed and isinstance(parsed["lineage"], list):
                                logger.info("parse_sql_lineage returning regex dict lineage of size %d", len(parsed["lineage"]))
                                return parsed["lineage"]
                            else:
                                logger.info("parse_sql_lineage returning wrapped dict")
                                return [parsed]
                    except json.JSONDecodeError:
                        try:
                            import ast
                            parsed = ast.literal_eval(cleaned_match)
                            if isinstance(parsed, list):
                                return parsed
                        except Exception:
                            pass
            
            # Aggressive fallback: find first [ and last ]
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                array_str = response[start_idx:end_idx+1]
                # clean trailing commas in the array string
                array_str = re.sub(r',\s*\}', '}', array_str)
                array_str = re.sub(r',\s*\]', ']', array_str)
                try:
                    parsed = json.loads(array_str)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    try:
                        import ast
                        parsed = ast.literal_eval(array_str)
                        if isinstance(parsed, list):
                            logger.info("parse_sql_lineage returning aggressive ast list of size %d", len(parsed))
                            return parsed
                    except Exception as e:
                        logger.warning("Aggressive ast failed: %s", e)
                        pass

        except Exception as e:
            from backend.core.logging_config import get_logger
            logger = get_logger(__name__)
            logger.error("Failed to parse SQL lineage: %s", e)
        
        logger.error("parse_sql_lineage exhausted all parsing methods and is returning []")
        return []
