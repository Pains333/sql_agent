"""
LLM 客户端 - 支持 Ollama 本地模型和 OpenAI 兼容 API
"""

import json
import re
import requests
import config


class LLMClient:
    """LLM 客户端，支持 local (Ollama) 和 api (OpenAI 兼容) 两种模式"""

    def __init__(
        self,
        mode: str = "local",
        base_url: str = "",
        model: str = "",
        api_key: str = "",
    ):
        """
        初始化 LLM 客户端

        Args:
            mode: "local" (Ollama) 或 "api" (OpenAI 兼容)
            base_url: API 地址
            model: 模型名称
            api_key: API Key (仅 api 模式)
        """
        self.mode = mode
        self.timeout = config.LLM_REQUEST_TIMEOUT
        self.temperature = config.LLM_TEMPERATURE
        self.conversation_history = []

        if mode == "local":
            self.base_url = base_url or config.OLLAMA_BASE_URL
            self.model = model or config.OLLAMA_MODEL
            self.api_key = ""
        else:
            self.base_url = base_url.rstrip("/")
            self.model = model
            self.api_key = api_key

    def reset_history(self):
        """重置对话历史"""
        self.conversation_history = []

    def chat(self, user_message: str, system_prompt: str) -> str:
        """
        发送消息并获取回复

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词

        Returns:
            模型回复的文本
        """
        if self.mode == "local":
            return self._chat_ollama(user_message, system_prompt)
        else:
            return self._chat_openai(user_message, system_prompt)

    def _chat_ollama(self, user_message: str, system_prompt: str) -> str:
        """Ollama 本地模型调用"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            assistant_message = result.get("message", {}).get("content", "")
            self._save_history(user_message, assistant_message)
            return assistant_message

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                "无法连接到 Ollama 服务。请确保 Ollama 正在运行 (ollama serve)"
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Ollama 请求超时 ({self.timeout}s)。模型可能正在加载，请稍后重试。"
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama API 错误: {e}")

    def _chat_openai(self, user_message: str, system_prompt: str) -> str:
        """OpenAI 兼容 API 调用"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            assistant_message = result["choices"][0]["message"]["content"]
            self._save_history(user_message, assistant_message)
            return assistant_message

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"无法连接到 API 服务: {self.base_url}"
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"API 请求超时 ({self.timeout}s)"
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"API 错误: {e}")
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"API 响应格式异常: {e}")

    def _save_history(self, user_message: str, assistant_message: str):
        """保存对话历史"""
        self.conversation_history.append(
            {"role": "user", "content": user_message}
        )
        self.conversation_history.append(
            {"role": "assistant", "content": assistant_message}
        )
        # 限制历史长度
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-16:]

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
        return {
            "action": "chat",
            "sql": "",
            "explanation": response_text,
            "database": "",
        }
