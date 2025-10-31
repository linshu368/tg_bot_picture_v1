# api.py
import requests
import os
import json
from dotenv import load_dotenv
from pathlib import Path

# 加载.env文件 - 从父目录加载
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

class GPTCaller:
    def __init__(self, api_key=None, default_model=None, api_url=None):
        self.api_key = api_key or os.getenv("TEXT_OPENAI_API_KEY")
        self.default_model = default_model or os.getenv("TEXT_OPENAI_MODEL")
        self.url = api_url or os.getenv("TEXT_OPENAI_API_URL")
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_stream_response(self, messages, model_name=None, timeout=60):
        """
        调用 OpenAI API 流式生成响应 (同步版本，用于测试)
        """
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置TEXT_OPENAI_API_KEY环境变量")
        
        data = {
            'model': model_name or self.default_model,
            'messages': messages,
            'stream': True  # 启用流式返回
        }

        # 发送请求并开启流式返回
        with requests.post(self.url, headers=self.headers, json=data, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            
            # 逐块读取流式数据 (OpenAI SSE 格式)
            for line in response.iter_lines():
                if not line:
                    continue
                    
                # 解码
                line_str = line.decode('utf-8')
                
                # OpenAI 流式响应格式: "data: {...}"
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
                            yield content
                    except (json.JSONDecodeError, IndexError, KeyError) as e:
                        # 忽略解析错误，继续处理下一行
                        continue
