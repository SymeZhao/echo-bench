"""统一 API 客户端：OpenAI 兼容格式，覆盖官方直连与 OpenRouter。"""
import os
import time
from openai import OpenAI


class ChatClient:
    def __init__(self, base_url: str, env_key: str, timeout: int = 60,
                 max_retries: int = 3, retry_delay: int = 5):
        api_key = os.environ.get(env_key)
        if not api_key:
            raise RuntimeError(
                f"环境变量 {env_key} 未设置。请在系统环境变量中配置后重开终端。")
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def chat(self, model: str, messages: list, temperature: float = 0.7,
             extra_body: dict | None = None) -> dict:
        """发送完整消息列表，返回 {content, model, usage}。失败重试后仍失败则抛异常。"""
        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature,
                    extra_body=extra_body or {})
                choice = resp.choices[0].message
                return {
                    "content": choice.content or "",
                    "model": resp.model,
                    "usage": resp.usage.model_dump() if resp.usage else None,
                    # 新增（向后兼容）：供调用方判断是否撞上输出上限被截断
                    "finish_reason": resp.choices[0].finish_reason,
                }
            except Exception as e:  # 网络/限流/5xx 统一重试
                last_err = e
                time.sleep(self.retry_delay * (attempt + 1))
        raise RuntimeError(f"请求失败（重试 {self.max_retries} 次）: {last_err}")
