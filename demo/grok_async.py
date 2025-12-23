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

class AsyncGrokCaller:
    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or os.getenv("GROK_API_KEY")
        self.url = api_url or os.getenv("GROK_API_URL")
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    async def get_stream_response(self, messages, model=None, timeout=60, debug=False):
        """
        调用 GROK API 流式生成响应 (异步版本)
        """
        import time
        
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置GROK_API_KEY环境变量")
        
        data = {
            'messages': messages,
            'stream': True,  # 启用流式返回
            'model': model,   # 模型参数从外部传入
            # 'temperature': 0.3  # 设置创造性参数
        }

        # 创建超时配置
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        
        # ⏱️ 时间监控
        request_start = time.time()
        if debug:
            print(f"[API] 发起请求到: {self.url}")
            print(f"[API] 使用模型: {model}")
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            connection_start = time.time()
            async with session.post(self.url, headers=self.headers, json=data) as response:
                connection_time = time.time() - connection_start
                if debug:
                    print(f"[API] 建立连接耗时: {connection_time:.3f}秒")
                    print(f"[API] 响应状态码: {response.status}")
                
                # 改进错误处理，提供更详细的错误信息
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"API请求失败 (状态码: {response.status}): {error_text[:200]}")
                
                response.raise_for_status()
                
                first_byte_received = False
                chunk_count = 0
                
                # 逐块读取流式数据 (GROK 流式响应格式)
                async for line in response.content:
                    if not line:
                        continue
                    
                    if not first_byte_received:
                        first_byte_time = time.time() - request_start
                        if debug:
                            print(f"[API] 首字节到达耗时: {first_byte_time:.3f}秒")
                        first_byte_received = True
                        
                    # 解码
                    line_str = line.decode('utf-8').strip()
                    
                    # GROK 流式响应格式: "data: {...}"
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
                            
                            # 只返回有内容的部分
                            if content:
                                chunk_count += 1
                                if debug and chunk_count == 1:
                                    first_content_time = time.time() - request_start
                                    print(f"[API] 首个内容chunk到达耗时: {first_content_time:.3f}秒")
                                yield content
                        except (json.JSONDecodeError, IndexError, KeyError) as e:
                            # 忽略解析错误，继续处理下一行
                            continue
                
                if debug:
                    total_time = time.time() - request_start
                    print(f"[API] 总耗时: {total_time:.3f}秒, 共{chunk_count}个chunk")

    async def get_response(self, messages, model=None, timeout=60):
        """
        非流式版本 - 获取完整响应
        """
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置GROK_API_KEY环境变量")
        
        data = {
            'messages': messages,
            'stream': False,
            'model': model,  # 模型参数从外部传入
            # 'temperature': 0.3  # 设置创造性参数
        }

        timeout_config = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.post(self.url, headers=self.headers, json=data) as response:
                response.raise_for_status()
                result = await response.json()
                
                choices = result.get('choices', [])
                if not choices:
                    raise ValueError("API响应中没有choices")
                
                return choices[0].get('message', {}).get('content', '')


# 为了方便使用，提供一个简单的异步生成器函数
async def chat_with_grok_async(messages, api_key=None, model_name=None, debug=False):
    """
    简化的异步生成器函数，用于流式对话
    """
    caller = AsyncGrokCaller(api_key=api_key)
    async for content in caller.get_stream_response(messages, model=model_name, debug=debug):
        yield content