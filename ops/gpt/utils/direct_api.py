# from openai import OpenAI
import requests
import os
# from dotenv import load_dotenv
from pathlib import Path

# 获取项目根目录路径并加载 .env 文件
project_root = Path(__file__).resolve().parents[2]  # 从 gpt/utils/direct_api.py 向上两级到项目根目录
env_path = project_root / '.env'
# load_dotenv(env_path)

class gptCaller:
    def __init__(self):
        """
        初始化 OpenAI 聊天类
        """
        # 从环境变量读取 API Key 和模型 
        self.api_key = os.getenv("OPENAI_API_KEY","sk-1iJIb2VngP3CTyIzLG4pch0ySXbTovW4ucpJoU4s3Zhyxtp5")
        
        # 检查 API Key 是否正确加载
        if not self.api_key:
            raise ValueError(f"OPENAI_API_KEY 未找到！请检查 .env 文件是否存在于: {env_path}")
        # self.model =  "gpt-5-2025-08-07"
        self.model = "gpt-4.1"
        # self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 默认用 gpt-4o-mini
        self.url = os.getenv("OPENAI_API_URL", "https://aifuturekey.xyz/v1/chat/completions")

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_response(self, prompt, timeout=60):
        """
        发送用户输入并获取 OpenAI 的回复
        :param prompt: 用户输入的内容
        :param timeout: 请求超时时间（秒）
        :return: OpenAI 的回复内容
        """
        # 构造 messages 列表
        messages = [
            {'role': 'user', 'content': prompt}
        ]

        # 构造请求数据
        data = {
            'model': self.model,
            'messages': messages
        }

        try:
            # 发送 POST 请求，添加超时设置
            response = requests.post(self.url, headers=self.headers, json=data, timeout=timeout)

            # 检查请求是否成功
            if response.status_code == 200:
                return response.json().get('choices')[0].get('message').get('content')
            else:
                raise Exception(f"请求失败，状态码: {response.status_code}, 错误信息: {response.json()}")
        except requests.exceptions.Timeout:
            raise Exception(f"请求超时，超过 {timeout} 秒")
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求异常: {str(e)}")
        except Exception as e:
            raise Exception(f"未知错误: {str(e)}")


#示例用法
gpt_caller = gptCaller()

# 使用示例
if __name__ == "__main__":
    # 初始化调用器
    gpt_caller = gptCaller()
    

    # 查看可用模型
    print("可用模型:", gpt_caller.get_available_models())
    
    #测试
    prompt = """
   你好

    """
    response = gpt_caller.get_response(prompt,model_name='gpt-4.1')
    print(response)
