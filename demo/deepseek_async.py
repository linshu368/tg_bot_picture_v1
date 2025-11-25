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

class AsyncDeepseekCaller:
    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.url = api_url or os.getenv("DEEPSEEK_API_URL")
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    async def get_stream_response(self, messages, model=None, timeout=60, debug=False):
        """
        调用 DeepSeek API 流式生成响应 (异步版本)
        """
        import time
        
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置DEEPSEEK_API_KEY环境变量")
        
        # 如果没有传入model，尝试从环境变量获取默认值
        use_model = model or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"

        data = {
            'messages': messages,
            'stream': True,  # 启用流式返回
            'model': use_model,
            'temperature': 1.3  # DeepSeek 建议 temperature (deepseek-chat 通用建议 1.3 左右，或根据具体需求调整)
        }

        # 创建超时配置
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
                    raise ValueError(f"API请求失败 (状态码: {response.status}): {error_text[:200]}")
                
                response.raise_for_status()
                
                first_byte_received = False
                chunk_count = 0
                
                # 逐块读取流式数据 (OpenAI/DeepSeek 流式响应格式)
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
                    
                    # 格式: "data: {...}"
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # 去掉 "data: " 前缀
                        
                        # 结束标志
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            chunk_json = json.loads(data_str)
                            choices = chunk_json.get('choices', [])
                            
                            if not choices:
                                continue
                                
                            delta = choices[0].get('delta', {})
                            content = delta.get('content')
                            
                            # DeepSeek 有时会返回 reasoning_content (思维链)，如果需要可以处理，这里暂时只返回 content
                            # reasoning = delta.get('reasoning_content')
                            
                            if content:
                                chunk_count += 1
                                if debug and chunk_count == 1:
                                    first_content_time = time.time() - request_start
                                    print(f"[API] 首个内容chunk到达耗时: {first_content_time:.3f}秒")
                                yield content
                        except (json.JSONDecodeError, IndexError, KeyError) as e:
                            continue
                
                if debug:
                    total_time = time.time() - request_start
                    print(f"[API] 总耗时: {total_time:.3f}秒, 共{chunk_count}个chunk")

    async def get_response(self, messages, model=None, timeout=60):
        """
        非流式版本 - 获取完整响应
        """
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置DEEPSEEK_API_KEY环境变量")
        
        use_model = model or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
        
        data = {
            'messages': messages,
            'stream': False,
            'model': use_model,
            'temperature': 0.3
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

