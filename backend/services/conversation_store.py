"""
对话存储管理器 - 使用 JSON 文件持久化对话历史
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional


# 对话存储目录
from backend.core.config import PROJECT_ROOT

CONVERSATIONS_DIR = os.path.join(PROJECT_ROOT, "conversations")


class ConversationStore:
    """管理对话的创建、读取、更新和删除"""

    def __init__(self):
        os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    def _get_path(self, conv_id: str) -> str:
        """获取对话文件路径"""
        return os.path.join(CONVERSATIONS_DIR, f"{conv_id}.json")

    def cleanup_expired(self, max_days: int = 1):
        """清理超过 max_days 天没有更新的对话数据"""
        now = datetime.now()
        for filename in os.listdir(CONVERSATIONS_DIR):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(CONVERSATIONS_DIR, filename)
            try:
                # 获取文件最后修改时间
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if (now - mtime).days >= max_days:
                    os.remove(filepath)
            except Exception:
                pass

    def create_conversation(self, title: str = "新对话") -> dict:
        """
        创建新对话

        Args:
            title: 对话标题

        Returns:
            新创建的对话对象
        """
        # 每次创建新对话时，顺便清理一下过期的对话文件（大于1天）
        self.cleanup_expired(max_days=1)
        
        conv_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        conversation = {
            "id": conv_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        path = self._get_path(conv_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
        os.chmod(path, 0o600)
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

    def _update_conversation(self, conv_id: str, updater) -> Optional[dict]:
        """读取对话、应用更新函数、写回文件"""
        conversation = self.get_conversation(conv_id)
        if conversation is None:
            return None
        result = updater(conversation)
        conversation["updated_at"] = datetime.now().isoformat()
        path = self._get_path(conv_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
        os.chmod(path, 0o600)
        return result

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        sql: str = "",
        action: str = "",
        result: str = "",
        error: str = "",
        status: str = "",
        plan: Optional[dict] = None,
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
            status: 消息状态 (pending/executed/cancelled)
            plan: 执行计划字典 (用于两阶段执行)

        Returns:
            添加的消息对象
        """
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
        if status:
            message["status"] = status
        if plan:
            message["plan"] = plan

        def updater(conversation):
            conversation["messages"].append(message)
            # 如果是第一条用户消息，用它作为标题
            if role == "user" and len(conversation["messages"]) == 1:
                title = content[:30]
                if len(content) > 30:
                    title += "..."
                conversation["title"] = title
            return message

        return self._update_conversation(conv_id, updater)

    def get_message(self, conv_id: str, message_id: str) -> Optional[dict]:
        """
        获取单条消息

        Args:
            conv_id: 对话 ID
            message_id: 消息 ID

        Returns:
            消息对象，不存在则返回 None
        """
        conversation = self.get_conversation(conv_id)
        if conversation is None:
            return None
        for msg in conversation.get("messages", []):
            if msg["id"] == message_id:
                return msg
        return None

    def update_message_status(
        self,
        conv_id: str,
        message_id: str,
        status: str,
        **updates,
    ) -> Optional[dict]:
        """
        更新消息状态（用于两阶段执行的确认/取消）

        Args:
            conv_id: 对话 ID
            message_id: 消息 ID
            status: 新状态 (executed/cancelled)
            **updates: 其他要更新的字段 (result, error 等)

        Returns:
            更新后的消息对象
        """
        def updater(conversation):
            for msg in conversation.get("messages", []):
                if msg["id"] == message_id:
                    msg["status"] = status
                    for key, value in updates.items():
                        msg[key] = value
                    return msg
            return None

        return self._update_conversation(conv_id, updater)

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
        def updater(conversation):
            conversation["title"] = title
            return True

        result = self._update_conversation(conv_id, updater)
        return result is not None
