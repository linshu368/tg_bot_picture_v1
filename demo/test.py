import time
import requests
import json

# API相关配置
api_url = "https://www.gpt4novel.com/api/xiaoshuoai/ext/v1/chat/completions"
api_key = "a80bb032-61d7-4a6a-8271-11f5aadc47f8"
# 请求头
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 测试的prompt
test_prompt = "输出100个字"

def get_response(prompt, debug=False):
    """发送流式请求到GPT模型并获取完整响应"""
    data = {
        "model": "nalang-xl-0826-10k",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,  # 启用流式响应
        "temperature": 0.7,
        "max_tokens": 800,
        "top_p": 0.35,
        "repetition_penalty": 1.05,
    }
    
    # 发送POST请求，启用流式响应
    response = requests.post(api_url, headers=headers, json=data, stream=True)
    
    if debug:
        print(f"响应状态码: {response.status_code}")
    
    # 如果请求成功，处理流式响应
    if response.status_code == 200:
        full_content = ""
        first_chunk_time = None
        start_time = time.time()
        
        try:
            buffer = ''
            for chunk in response.iter_lines():
                if chunk:
                    # 记录首个chunk时间
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                    
                    decoded_chunk = chunk.decode('utf-8')
                    buffer += decoded_chunk + '\n'
                    
                    # 按行处理数据 - 处理SSE格式
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.strip():
                            try:
                                # 处理SSE格式：去掉 "data: " 前缀
                                if line.strip().startswith('data: '):
                                    json_str = line.strip()[6:]  # 去掉 "data: " 前缀
                                    if json_str.strip():  # 确保不是空字符串
                                        json_data = json.loads(json_str)
                                        if 'choices' in json_data:
                                            content = json_data['choices'][0].get('delta', {}).get('content', '')
                                            if content:
                                                full_content += content
                            except json.JSONDecodeError:
                                if debug:
                                    print(f"无法解析数据：{line.strip()}")
                                continue
            
            total_time = time.time() - start_time
            first_chunk_delay = (first_chunk_time - start_time) if first_chunk_time else 0
            
            return {
                "content": full_content,
                "total_time": total_time,
                "first_chunk_time": first_chunk_delay,
                "total_chars": len(full_content)
            }
            
        except Exception as e:
            raise Exception(f"处理流式响应时出错: {str(e)}")
    else:
        raise Exception(f"请求失败，状态码：{response.status_code}, 错误信息：{response.text}")


def test_response_time():
    """测试模型的响应时间"""
    print("\n=== 流式API性能测试 ===")
    print(f"API地址: {api_url}")
    print(f"模型: nalang-xl-0826-10k")
    print(f"测试提示: '{test_prompt}'")
    print(f"测试次数: 10次\n")

    total_times = []
    first_chunk_times = []
    char_counts = []
    successful_tests = 0

    # 测试10次
    for i in range(10):
        print(f"第{i+1}次测试:", end=" ")
        try:
            # 获取响应
            result = get_response(test_prompt, debug=False)
            
            total_times.append(result["total_time"])
            first_chunk_times.append(result["first_chunk_time"])
            char_counts.append(result["total_chars"])
            successful_tests += 1
            
            print(f"✅ 总耗时: {result['total_time']:.3f}秒, 首chunk: {result['first_chunk_time']:.3f}秒, 字符数: {result['total_chars']}")
            print(f"    响应内容: {result['content'][:50]}{'...' if len(result['content']) > 50 else ''}")
            
        except Exception as e:
            print(f"❌ 失败 - {e}")

        # 避免请求过快
        if i < 9:
            time.sleep(1)  # 增加间隔时间
        print()

    # 统计结果
    if total_times:
        print("="*60)
        print("📊 性能统计结果:")
        print(f"  ✅ 成功次数: {successful_tests}/10")
        print(f"  📈 总响应时间:")
        print(f"    - 平均: {sum(total_times)/len(total_times):.3f}秒")
        print(f"    - 最快: {min(total_times):.3f}秒")
        print(f"    - 最慢: {max(total_times):.3f}秒")
        print(f"  ⚡ 首个chunk时间:")
        print(f"    - 平均: {sum(first_chunk_times)/len(first_chunk_times):.3f}秒")
        print(f"    - 最快: {min(first_chunk_times):.3f}秒")
        print(f"    - 最慢: {max(first_chunk_times):.3f}秒")
        print(f"  📝 响应内容:")
        print(f"    - 平均字符数: {sum(char_counts)/len(char_counts):.1f}")
        print(f"    - 最少字符数: {min(char_counts)}")
        print(f"    - 最多字符数: {max(char_counts)}")
        
        # 计算吞吐量
        avg_total_time = sum(total_times) / len(total_times)
        avg_chars = sum(char_counts) / len(char_counts)
        throughput = avg_chars / avg_total_time if avg_total_time > 0 else 0
        print(f"  🚀 平均吞吐量: {throughput:.1f} 字符/秒")
    else:
        print("❌ 所有测试都失败了！")

# 执行响应时间测试
if __name__ == "__main__":
    test_response_time()
