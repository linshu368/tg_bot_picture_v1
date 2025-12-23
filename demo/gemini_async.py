import aiohttp
import asyncio
import os
import json
from dotenv import load_dotenv
from pathlib import Path

# 加载.env文件 - 从父目录加载
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)


class AsyncGeminiCaller:
    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.url = api_url or os.getenv("GEMINI_API_URL")
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    async def get_stream_response(self, messages, model=None, timeout=60, debug=False):
        """
        调用 Gemini API 流式生成响应 (异步版本)
        """
        import time

        if not self.api_key:
            raise ValueError("API密钥未设置，请设置 GEMINI_API_KEY 环境变量")

        # 如果没有传入 model，尝试从环境变量获取
        use_model = model or os.getenv("GEMINI_MODEL")

        data = {
            'messages': messages,
            'stream': True,
            'model': use_model,
            # 'temperature': 1.3
        }

        timeout_config = aiohttp.ClientTimeout(total=timeout)

        # ⏱️ 时间监控
        request_start = time.time()
        if debug:
            print(f"[API] 发起请求到: {self.url}")
            print(f"[API] 使用模型: {use_model}")

        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            connection_start = time.time()
            async with session.post(self.url, headers=self.headers, json=data) as response:
                connection_time = time.time() - connection_start
                if debug:
                    print(f"[API] 建立连接耗时: {connection_time:.3f}秒")
                    print(f"[API] 响应状态码: {response.status}")

                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(
                        f"API请求失败 (状态码: {response.status}): {error_text[:200]}"
                    )

                response.raise_for_status()

                first_byte_received = False
                chunk_count = 0

                # 按 OpenAI / DeepSeek 风格解析 SSE 流
                async for line in response.content:
                    if not line:
                        continue

                    if not first_byte_received:
                        first_byte_time = time.time() - request_start
                        if debug:
                            print(f"[API] 首字节到达耗时: {first_byte_time:.3f}秒")
                        first_byte_received = True

                    line_str = line.decode('utf-8').strip()

                    if line_str.startswith('data: '):
                        data_str = line_str[6:]

                        if data_str == '[DONE]':
                            break

                        try:
                            chunk_json = json.loads(data_str)
                            choices = chunk_json.get('choices', [])

                            if not choices:
                                continue

                            delta = choices[0].get('delta', {})
                            content = delta.get('content')

                            if content:
                                chunk_count += 1
                                if debug and chunk_count == 1:
                                    first_content_time = time.time() - request_start
                                    print(
                                        f"[API] 首个内容chunk到达耗时: {first_content_time:.3f}秒"
                                    )
                                yield content
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue

                if debug:
                    total_time = time.time() - request_start
                    print(f"[API] 总耗时: {total_time:.3f}秒, 共 {chunk_count} 个 chunk")


if __name__ == "__main__":
    async def test_main():
        import time

        print("=" * 50)
        print("Gemini Async Stream Test")
        print("=" * 50)

        caller = AsyncGeminiCaller()

        test_model = os.getenv("GEMINI_MODEL")
        messages = [
            {"role": "user", "content": "你是小说创作家，写一个400字的都市题材故事"}
        ]

        try:
            print(f"Prompt: {messages[0]['content']}")
            print(f"Testing Model: {test_model}")

            start_time = time.time()
            last_time = start_time

            async for chunk in caller.get_stream_response(
                messages, model=test_model, debug=True
            ):
                now = time.time()
                total_elapsed = now - start_time
                chunk_elapsed = now - last_time

                clean_chunk = chunk.replace('\n', '\\n')
                print(
                    f"[Chunk +{chunk_elapsed:.3f}s | Total {total_elapsed:.3f}s]: {clean_chunk}"
                )
                last_time = now

        except Exception as e:
            print(f"\n[ERROR] 发生异常: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(test_main())
