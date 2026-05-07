"""
对话存储管理器 - 使用 JSON 文件持久化对话历史
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional


# 对话存储目录
CONVERSATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversations")


class ConversationStore:
    """管理对话的创建、读取、更新和删除"""

    def __init__(self):
        os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    def _get_path(self, conv_id: str) -> str:
        """获取对话文件路径"""
        return os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")

    def create_conversation(self, title: str = "新对话") -> dict:
        """
        创建新对话

        Args:
            title: 对话标题

        Returns:
            新创建的对话对象
        """
        conv_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        conversation = {
            "id": conv_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        with open(self._get_path(conv_id), "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
        return conversation

    def list_conversations(self) -> list:
        """
        获取所有对话列表（不含消息内容，按更新时间倒序）

        Returns:
            对话摘要列表
        """
        conversations = []
        for filename in os.listdir(CONVERSATIONS_DIR):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(CONVERSATIONS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                conversations.append({
                    "id": data["id"],
                    "title": data["title"],
                    "created_at": data["created_at"],
                    "updated_at": data["updated_at"],
                    "message_count": len(data.get("messages", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        # 按更新时间倒序排列
        conversations.sort(key=lambda x: x["updated_at"], reverse=True)
        return conversations

    def get_conversation(self, conv_id: str) -> Optional[dict]:
        """
        获取单个对话（含完整消息）

        Args:
            conv_id: 对话 ID

        Returns:
            对话对象，不存在则返回 None
        """
        path = self._get_path(conv_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        sql: str = "",
        action: str = "",
        result: str = "",
        error: str = "",
    ) -> Optional[dict]:
        """
        向对话添加消息

        Args:
            conv_id: 对话 ID
            role: "user" 或 "assistant"
            content: 消息内容
            sql: SQL 语句（仅 assistant）
            action: 操作类型（仅 assistant）
            result: 执行结果（仅 assistant）
            error: 错误信息

        Returns:
            添加的消息对象
        """
        conversation = self.get_conversation(conv_id)
        if conversation is None:
            return None

        message = {
            "id": str(uuid.uuid4())[:8],
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if sql:
            message["sql"] = sql
        if action:
            message["action"] = action
        if result:
            message["result"] = result
        if error:
            message["error"] = error

        conversation["messages"].append(message)
        conversation["updated_at"] = datetime.now().isoformat()

        # 如果是第一条用户消息，用它作为标题
        if role == "user" and len(conversation["messages"]) == 1:
            title = content[:30]
            if len(content) > 30:
                title += "..."
            conversation["title"] = title

        with open(self._get_path(conv_id), "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)

        return message

    def delete_conversation(self, conv_id: str) -> bool:
        """
        删除对话

        Args:
            conv_id: 对话 ID

        Returns:
            是否成功删除
        """
        path = self._get_path(conv_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def update_title(self, conv_id: str, title: str) -> bool:
        """
        更新对话标题

        Args:
            conv_id: 对话 ID
            title: 新标题

        Returns:
            是否成功更新
        """
        conversation = self.get_conversation(conv_id)
        if conversation is None:
            return False

        conversation["title"] = title
        conversation["updated_at"] = datetime.now().isoformat()

        with open(self._get_path(conv_id), "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
        return True
