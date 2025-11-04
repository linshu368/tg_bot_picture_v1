import os
import json
from typing import AsyncGenerator, Optional

import aiohttp
from dotenv import load_dotenv
from pathlib import Path


# 加载.env文件 - 从父目录加载（与 gemini_async.py 一致）
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)


class AsyncNovelCaller:
    """
    使用商家原生流式（SSE）协议的异步调用器。
    接口与 AsyncGeminiCaller 对齐：
      - get_stream_response(messages, model_name=None, timeout=60, debug=False)
      - get_response(messages, model_name=None, timeout=60, debug=False)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("NOVEL_API_KEY", os.getenv("GEMINI_API_KEY", ""))
        self.default_model = default_model or os.getenv("NOVEL_MODEL", os.getenv("GEMINI_MODEL", "nalang-xl-0826-10k"))
        # 注意：为商家接口设置默认基础URL
        self.base_url = base_url or os.getenv(
            "NOVEL_BASE_URL",
            "https://www.gpt4novel.com/api/xiaoshuoai/ext/v1/",
        )

        if not self.api_key:
            # 与现有风格一致，抛出可读错误
            raise ValueError("API密钥未设置，请设置NOVEL_API_KEY环境变量或在构造函数中传入api_key")

    async def get_stream_response(
        self,
        messages,
        model_name: Optional[str] = None,
        timeout: int = 60,
        debug: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        原生SSE流式生成：逐行解析 `data: {json}`，从 `choices[0].delta.content` 增量输出。
        """
        model = model_name or self.default_model
        url = self.base_url.rstrip('/') + '/chat/completions'

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            # 与你的 test1.py 参数保持一致
            "temperature": 0.7,
            "max_tokens": 800,
            "top_p": 0.35,
            "repetition_penalty": 1.05,
        }

        if debug:
            print(f"[Novel API] 发起请求到: {url}")
            print(f"[Novel API] 使用模型: {model}")
            print(f"[Novel API] 消息数量: {len(messages)}")

        timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.post(url, headers=headers, json=body) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    if debug:
                        print(f"[Novel API] 非200响应: {resp.status}, 内容: {text[:200]}")
                    raise ValueError(f"Error code: {resp.status} - {text}")

                buffer = ''
                async for chunk in resp.content.iter_chunked(1024):
                    if not chunk:
                        continue
                    decoded = chunk.decode('utf-8', errors='ignore')
                    buffer += decoded

                    # 逐行处理SSE
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        s = line.strip()
                        if not s:
                            continue
                        if not s.startswith('data:'):
                            # 忽略非SSE数据行
                            continue
                        data_str = s[5:].strip()
                        if not data_str:
                            continue
                        if data_str == '[DONE]':
                            return
                        try:
                            payload = json.loads(data_str)
                        except json.JSONDecodeError:
                            if debug:
                                print(f"[Novel API] 无法解析数据: {s}")
                            continue

                        if isinstance(payload, dict):
                            choices = payload.get('choices')
                            if choices and len(choices) > 0:
                                delta = choices[0].get('delta') or {}
                                content = delta.get('content')
                                if content:
                                    yield content

    async def get_response(
        self,
        messages,
        model_name: Optional[str] = None,
        timeout: int = 60,
        debug: bool = False,
    ) -> str:
        """
        非流式：优先尝试 stream=False 的一次性响应；不兼容时回退为聚合流式。
        """
        model = model_name or self.default_model
        url = self.base_url.rstrip('/') + '/chat/completions'

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 800,
            "top_p": 0.35,
            "repetition_penalty": 1.05,
        }

        if debug:
            print(f"[Novel API] 发起非流式请求到: {url}")

        timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                async with session.post(url, headers=headers, json=body) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        if debug:
                            print(f"[Novel API] 非200响应: {resp.status}, 内容: {text[:200]}")
                        raise ValueError(f"Error code: {resp.status} - {text}")

                    # 兼容不同返回结构
                    try:
                        data = json.loads(text)
                        if data.get('choices'):
                            # OpenAI风格
                            first = data['choices'][0]
                            # 兼容 message.content 或 delta.content
                            if 'message' in first and first['message']:
                                return first['message'].get('content', '') or ''
                            delta = first.get('delta') or {}
                            return delta.get('content', '') or ''
                    except json.JSONDecodeError:
                        pass

                    # 无法解析结构，直接返回原文本
                    return text or ''
        except Exception:
            # 回退为聚合流式
            chunks = []
            async for part in self.get_stream_response(messages, model_name=model, timeout=timeout, debug=debug):
                chunks.append(part)
            return ''.join(chunks)


