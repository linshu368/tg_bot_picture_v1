# api.py
import requests
import os
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

    async def get_response(self, messages, model_name=None, timeout=60):
        # 检查必要的配置
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置TEXT_OPENAI_API_KEY环境变量")
        
        data = {
            'model': model_name or self.default_model,
            'messages': messages
        }

        # print(f"🔍 调试信息:")
        # print(f"   API URL: {self.url}")
        # print(f"   API Key: {self.api_key[:20]}...")
        # print(f"   Model: {model_name or self.default_model}")
        # print(f"   Messages: {messages}")

        response = requests.post(self.url, headers=self.headers, json=data, timeout=timeout)
        
        # print(f"🔍 响应状态码: {response.status_code}")
        # print(f"🔍 响应内容: {response.text}")
        
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
