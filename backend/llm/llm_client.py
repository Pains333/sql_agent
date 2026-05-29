"""
LLM 客户端 - 支持 Ollama 本地模型和 OpenAI 兼容 API
"""

import json
import re
import requests

from backend.core import config
from backend.core.exceptions import LLMConnectionError, LLMTimeoutError, LLMResponseError
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

# 对话历史最大条数（超出后保留最近的部分）
MAX_HISTORY_MESSAGES = 20
HISTORY_TRIM_TO = 16


class LLMClient:
    """LLM 客户端，支持 local (Ollama) 和 api (OpenAI 兼容) 两种模式"""

    def __init__(
        self,
        mode: str = "local",
        base_url: str = "",
        model: str = "",
        api_key: str = "",
    ):
        self.mode = mode
        self.timeout = config.LLM_REQUEST_TIMEOUT
        self.temperature = config.LLM_TEMPERATURE
        self.conversation_history: list[dict] = []

        if mode == "local":
            self.base_url = base_url or config.OLLAMA_BASE_URL
            self.model = model or config.OLLAMA_MODEL
            self.api_key = ""
        else:
            self.base_url = base_url.rstrip("/")
            self.model = model
            self.api_key = api_key

    def reset_history(self) -> None:
        """重置对话历史"""
        self.conversation_history = []

    def _build_messages(self, user_message: str, system_prompt: str) -> list[dict]:
        """构建包含系统提示、历史记录和用户消息的消息列表"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def chat(self, user_message: str, system_prompt: str) -> str:
        """
        发送消息并获取回复

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词

        Returns:
            模型回复的文本

        Raises:
            LLMConnectionError: 无法连接到 LLM 服务
            LLMTimeoutError: 请求超时
            LLMResponseError: 响应格式异常
        """
        messages = self._build_messages(user_message, system_prompt)

        if self.mode == "local":
            url = f"{self.base_url}/api/chat"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.temperature},
            }
            extract = lambda r: r.get("message", {}).get("content", "")
            service_name = f"Ollama ({self.base_url})"
        else:
            url = f"{self.base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
            }
            extract = lambda r: r["choices"][0]["message"]["content"]
            service_name = self.base_url

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            assistant_message = extract(result)
            self._save_history(user_message, assistant_message)
            return assistant_message

        except requests.exceptions.ConnectionError:
            raise LLMConnectionError(f"无法连接到服务: {service_name}")
        except requests.exceptions.Timeout:
            raise LLMTimeoutError(f"请求超时 ({self.timeout}s)")
        except requests.exceptions.HTTPError as e:
            raise LLMResponseError(f"API 错误: {e}") from e
        except (KeyError, IndexError) as e:
            raise LLMResponseError(f"响应格式异常: {e}") from e

    def chat_stream(self, user_message: str, system_prompt: str):
        """
        流式发送消息并逐 token 返回回复

        Yields:
            str: 每个 token 片段

        最终通过 _save_history 保存完整对话。
        """
        messages = self._build_messages(user_message, system_prompt)
        full_response = ""

        try:
            if self.mode == "local":
                url = f"{self.base_url}/api/chat"
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": self.temperature},
                }
                response = requests.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout, stream=True,
                )
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full_response += token
                            yield token
                        if data.get("done"):
                            break
            else:
                url = f"{self.base_url}/v1/chat/completions"
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "stream": True,
                }
                response = requests.post(
                    url, json=payload, headers=headers,
                    timeout=self.timeout, stream=True,
                )
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8")
                        if line_str.startswith("data: ") and line_str.strip() != "data: [DONE]":
                            try:
                                data = json.loads(line_str[6:])
                                token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if token:
                                    full_response += token
                                    yield token
                            except json.JSONDecodeError:
                                continue

            self._save_history(user_message, full_response)

        except requests.exceptions.ConnectionError:
            raise LLMConnectionError(f"无法连接到服务")
        except requests.exceptions.Timeout:
            raise LLMTimeoutError(f"请求超时 ({self.timeout}s)")
        except requests.exceptions.HTTPError as e:
            raise LLMResponseError(f"API 错误: {e}") from e

    def _save_history(self, user_message: str, assistant_message: str) -> None:
        """保存对话历史"""
        self.conversation_history.append(
            {"role": "user", "content": user_message}
        )
        self.conversation_history.append(
            {"role": "assistant", "content": assistant_message}
        )
        if len(self.conversation_history) > MAX_HISTORY_MESSAGES:
            self.conversation_history = self.conversation_history[-HISTORY_TRIM_TO:]

    def parse_json_response(self, response_text: str) -> dict:
        """
        从 LLM 回复中提取 JSON 对象

        Args:
            response_text: LLM 回复文本

        Returns:
            解析后的 JSON 字典
        """
        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        json_patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, response_text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        # 如果都无法解析，返回一个默认结构
        logger.warning("无法从 LLM 回复中解析 JSON，使用 chat 回退: %s", response_text[:200])
        return {
            "action": "chat",
            "sql": "",
            "explanation": response_text,
            "database": "",
        }
