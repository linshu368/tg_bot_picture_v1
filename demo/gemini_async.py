# gemini_async.py - 使用OpenAI SDK调用Gemini API的异步版本
import asyncio
import os
from typing import AsyncGenerator
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pathlib import Path

# 加载.env文件 - 从父目录加载
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

class AsyncGeminiCaller:
    def __init__(self, api_key=None, base_url=None):
        """
        初始化Gemini API调用器
        
        Args:
            api_key: Gemini API密钥，默认从环境变量GEMINI_API_KEY获取
            base_url: API基础URL，默认从环境变量GEMINI_BASE_URL获取
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.base_url = base_url or os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
        
        # 初始化异步OpenAI客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    async def get_stream_response(self, messages, model_name=None, timeout=60, debug=False) -> AsyncGenerator[str, None]:
        """
        调用 Gemini API 流式生成响应 (异步版本)
        
        Args:
            messages: 消息列表，格式与OpenAI兼容
            model_name: 模型名称，如果不指定则使用默认模型
            timeout: 超时时间（秒）
            debug: 是否启用调试输出
            
        Yields:
            str: 流式响应的文本片段
        """
        import time
        
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置GEMINI_API_KEY环境变量")
        
        model = model_name or os.getenv("GEMINI_MODEL", "")
        if not model:
            raise ValueError("模型未设置，请设置GEMINI_MODEL环境变量或在调用时传入model_name参数")
        
        # ⏱️ 时间监控
        request_start = time.time()
        if debug:
            print(f"[Gemini API] 发起请求到: {self.base_url}")
            print(f"[Gemini API] 使用模型: {model}")
            print(f"[Gemini API] 消息数量: {len(messages)}")
        
        try:
            # 使用OpenAI SDK调用Gemini API
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                timeout=timeout
            )
            
            first_chunk_received = False
            chunk_count = 0
            
            # 处理流式响应
            async for chunk in stream:
                if not first_chunk_received:
                    first_chunk_time = time.time() - request_start
                    if debug:
                        print(f"[Gemini API] 首个chunk到达耗时: {first_chunk_time:.3f}秒")
                    first_chunk_received = True
                
                # 提取内容
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        chunk_count += 1
                        if debug and chunk_count == 1:
                            first_content_time = time.time() - request_start
                            print(f"[Gemini API] 首个内容到达耗时: {first_content_time:.3f}秒")
                        yield delta.content
            
            if debug:
                total_time = time.time() - request_start
                print(f"[Gemini API] 总耗时: {total_time:.3f}秒, 共{chunk_count}个chunk")
                
        except Exception as e:
            if debug:
                print(f"[Gemini API] 请求失败: {str(e)}")
            raise ValueError(f"Gemini API请求失败: {str(e)}")

    async def get_response(self, messages, model_name=None, timeout=60, debug=False) -> str:
        """
        非流式版本 - 获取完整响应
        
        Args:
            messages: 消息列表，格式与OpenAI兼容
            model_name: 模型名称，如果不指定则使用默认模型
            timeout: 超时时间（秒）
            debug: 是否启用调试输出
            
        Returns:
            str: 完整的响应文本
        """
        import time
        
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置GEMINI_API_KEY环境变量")
        
        model = model_name or os.getenv("GEMINI_MODEL", "")
        if not model:
            raise ValueError("模型未设置，请设置GEMINI_MODEL环境变量或在调用时传入model_name参数")
        
        # ⏱️ 时间监控
        request_start = time.time()
        if debug:
            print(f"[Gemini API] 发起非流式请求到: {self.base_url}")
            print(f"[Gemini API] 使用模型: {model}")
        
        try:
            # 使用OpenAI SDK调用Gemini API
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
                timeout=timeout
            )
            
            if debug:
                total_time = time.time() - request_start
                print(f"[Gemini API] 非流式请求耗时: {total_time:.3f}秒")
            
            # 提取响应内容
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            else:
                raise ValueError("API响应中没有有效的choices")
                
        except Exception as e:
            if debug:
                print(f"[Gemini API] 非流式请求失败: {str(e)}")
            raise ValueError(f"Gemini API请求失败: {str(e)}")

    async def test_connection(self, debug=True) -> bool:
        """
        测试API连接是否正常
        
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
    """测试GeminiCaller的基本功能"""
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
        {"role": "user", "content": "1+1等于几？请简短回答。"}
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
