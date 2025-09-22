# api.py
import requests
import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class GPTCaller:
    def __init__(self, api_key=None, default_model=None, api_url=None):
        self.api_key = api_key or os.getenv("TEXT_OPENAI_API_KEY")
        self.default_model = default_model or os.getenv("TEXT_OPENAI_MODEL", "gpt-4o-mini")
        self.url = api_url or os.getenv("TEXT_OPENAI_API_URL", "https://aifuturekey.xyz/v1/chat/completions")

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_response(self, messages, model_name=None, timeout=60):
        # 检查必要的配置
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置TEXT_OPENAI_API_KEY环境变量")
        
        data = {
            'model': model_name or self.default_model,
            'messages': messages
        }

        response = requests.post(self.url, headers=self.headers, json=data, timeout=timeout)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
