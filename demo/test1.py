import requests
import json

def chat_with_ai(messages):
    url = "https://www.gpt4novel.com/api/xiaoshuoai/ext/v1/chat/completions"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer a80bb032-61d7-4a6a-8271-11f5aadc47f8',  # 使用你的API token
    }
    
    # 构建请求体
    request_body = {
        'model': 'nalang-xl-0826-10k',  # 10K context
        'messages': messages,
        'stream': True,
        'temperature': 0.7,
        'max_tokens': 800,
        'top_p': 0.35,
        'repetition_penalty': 1.05,
    }
    
    # 发送POST请求
    try:
        response = requests.post(url, headers=headers, json=request_body, stream=True)
        
        # 检查响应状态
        if response.status_code != 200:
            print(f"HTTP error! status: {response.status_code}")
            return
        
        print("请求成功，开始读取流...")
        
        # 处理流响应
        buffer = ''
        full_content = ''  # 用于保存完整的内容
        for chunk in response.iter_lines():
            if chunk:
                decoded_chunk = chunk.decode('utf-8')
                # print(f"接收到原始数据：{decoded_chunk}")  # 调试输出
                buffer += decoded_chunk
                
                # 如果流数据是完整的段落（结束符为“\n”），就解析并输出
                if buffer.endswith('\n'):
                    try:
                        # 解析每一行数据
                        json_data = json.loads(buffer.strip())
                        if 'choices' in json_data:
                            content = json_data['choices'][0].get('delta', {}).get('content', '')
                            if content:
                                full_content += content  # 拼接内容
                        buffer = ''  # 清空缓冲区
                    except json.JSONDecodeError:
                        print(f"无法解析数据：{buffer.strip()}")
                        buffer = ''  # 清空缓冲区

        # 输出拼接后的完整内容
        print(f"\n完整的对话内容：\n{full_content}")

    except Exception as e:
        print(f"Error: {e}")

# 使用示例
messages = [
    {"role": "system", "content": "你是一个有帮助的AI助手。"},
    {"role": "user", "content": "你好,请介绍一下自己。"}
]

chat_with_ai(messages)
