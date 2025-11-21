import aiohttp
import asyncio
import os
import json
from typing import AsyncGenerator
from dotenv import load_dotenv
from pathlib import Path

# 加载 .env 文件
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

class AsyncGeminiCaller:
    def __init__(self, api_key=None, base_url=None):
        """
        初始化 Gemini API 调用器

        Args:
            api_key: Gemini API 密钥，默认从环境变量 GEMINI_API_KEY 获取
            base_url: API 基础 URL，默认从环境变量 GEMINI_BASE_URL 获取
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.base_url = base_url or os.getenv("GEMINI_BASE_URL", "")
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    async def get_stream_response(self, messages, model_name=None, timeout=60, debug=False) -> AsyncGenerator[str, None]:
        """
        调用 Gemini API 流式生成响应 (异步版本)

        Args:
            messages: 消息列表，格式与 OpenAI 兼容
            model_name: 模型名称，如果不指定则使用默认模型
            timeout: 超时时间（秒）
            debug: 是否启用调试输出
            
        Yields:
            str: 流式响应的文本片段
        """
        import time
        
        if not self.api_key:
            raise ValueError("API 密钥未设置，请设置 GEMINI_API_KEY 环境变量")
        
        model = model_name or os.getenv("GEMINI_MODEL", "")
        if not model:
            raise ValueError("模型未设置，请设置 GEMINI_MODEL 环境变量或在调用时传入 model_name 参数")
        
        # ⏱️ 时间监控
        request_start = time.time()
        if debug:
            print(f"[Gemini API] 发起请求到: {self.base_url}")
            print(f"[Gemini API] 使用模型: {model}")
            print(f"[Gemini API] 消息数量: {len(messages)}")
        
        data = {
            'messages': messages,
            'model': model,
            'temperature': 0.3,  # 可根据需要调整
            'stream': True
        }

        # 创建超时配置
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        
        try:
            # 使用 aiohttp 发起 POST 请求
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.post(self.base_url, headers=self.headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"API 请求失败 (状态码: {response.status}): {error_text[:200]}")
                    response.raise_for_status()
                    
                    first_chunk_received = False
                    chunk_count = 0

                    # 逐块读取流式数据
                    async for line in response.content:
                        if not line:
                            continue
                        
                        if not first_chunk_received:
                            first_chunk_time = time.time() - request_start
                            if debug:
                                print(f"[Gemini API] 首个 chunk 到达耗时: {first_chunk_time:.3f}秒")
                            first_chunk_received = True
                        
                        # 解码
                        line_str = line.decode('utf-8').strip()
                        
                        # 检查数据格式
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # 去掉 "data: " 前缀
                            
                            # 结束标志
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                chunk_json = json.loads(data_str)
                                choices = chunk_json.get('choices', [])
                                
                                # 检查 choices 是否为空
                                if not choices:
                                    continue
                                
                                delta = choices[0].get('delta', {})
                                content = delta.get('content')
                                
                                if content:
                                    chunk_count += 1
                                    if debug and chunk_count == 1:
                                        first_content_time = time.time() - request_start
                                        print(f"[Gemini API] 首个内容到达耗时: {first_content_time:.3f}秒")
                                    yield content
                            except (json.JSONDecodeError, IndexError, KeyError) as e:
                                continue

                    if debug:
                        total_time = time.time() - request_start
                        print(f"[Gemini API] 总耗时: {total_time:.3f}秒, 共{chunk_count}个 chunk")
        except Exception as e:
            if debug:
                print(f"[Gemini API] 请求失败: {str(e)}")
            raise ValueError(f"Gemini API 请求失败: {str(e)}")

    async def get_response(self, messages, model_name=None, timeout=60, debug=False) -> str:
        """
        非流式版本 - 获取完整响应

        Args:
            messages: 消息列表，格式与 OpenAI 兼容
            model_name: 模型名称，如果不指定则使用默认模型
            timeout: 超时时间（秒）
            debug: 是否启用调试输出
            
        Returns:
            str: 完整的响应文本
        """
        import time
        
        if not self.api_key:
            raise ValueError("API 密钥未设置，请设置 GEMINI_API_KEY 环境变量")
        
        model = model_name or os.getenv("GEMINI_MODEL", "")
        if not model:
            raise ValueError("模型未设置，请设置 GEMINI_MODEL 环境变量或在调用时传入 model_name 参数")
        
        # ⏱️ 时间监控
        request_start = time.time()
        if debug:
            print(f"[Gemini API] 发起非流式请求到: {self.base_url}")
            print(f"[Gemini API] 使用模型: {model}")
        
        data = {
            'messages': messages,
            'model': model,
            'temperature': 0.3,  # 可根据需要调整
            'stream': False
        }
        
        # 创建超时配置
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        
        try:
            # 使用 aiohttp 发起 POST 请求
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.post(self.base_url, headers=self.headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"API 请求失败 (状态码: {response.status}): {error_text[:200]}")
                    response.raise_for_status()
                    
                    result = await response.json()
                    choices = result.get('choices', [])
                    if not choices:
                        raise ValueError("API 响应中没有有效的 choices")
                    
                    return choices[0].get('message', {}).get('content', "")
        except Exception as e:
            if debug:
                print(f"[Gemini API] 非流式请求失败: {str(e)}")
            raise ValueError(f"Gemini API 请求失败: {str(e)}")

    async def test_connection(self, debug=True) -> bool:
        """
        测试 API 连接是否正常

        Args:
            debug: 是否启用调试输出

        Returns:
            bool: 连接是否成功
        """
        try:
            test_messages = [
                {"role": "user", "content": "Hello, please respond with 'OK' to test the connection."}
            ]
            
            response = await self.get_response(test_messages, debug=debug)
            
            if debug:
                print(f"[Gemini API] 连接测试成功，响应: {response[:50]}...")
            
            return True
            
        except Exception as e:
            if debug:
                print(f"[Gemini API] 连接测试失败: {str(e)}")
            return False


# 测试函数
async def test_gemini_caller():
    """测试 AsyncGeminiCaller 的基本功能"""
    print("🧪 开始测试 AsyncGeminiCaller...")
    
    caller = AsyncGeminiCaller()
    
    # 测试连接
    print("\n1. 测试连接...")
    connection_ok = await caller.test_connection(debug=True)
    if not connection_ok:
        print("❌ 连接测试失败")
        return
    
    # 测试非流式响应
    print("\n2. 测试非流式响应...")
    messages = [
        {"role": "user", "content": "1+1 等于几？请简短回答。"}
    ]
    
    try:
        response = await caller.get_response(messages, debug=True)
        print(f"✅ 非流式响应: {response}")
    except Exception as e:
        print(f"❌ 非流式响应失败: {e}")
    
    # 测试流式响应
    print("\n3. 测试流式响应...")
    try:
        print("🔄 流式响应内容: ", end="", flush=True)
        async for chunk in caller.get_stream_response(messages, debug=True):
            print(chunk, end="", flush=True)
        print("\n✅ 流式响应完成")
    except Exception as e:
        print(f"\n❌ 流式响应失败: {e}")
    
    print("\n🎉 测试完成!")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_gemini_caller())
