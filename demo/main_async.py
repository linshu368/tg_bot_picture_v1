# main_async.py - 异步流式回复测试版本
import asyncio
import time
import os
from role import role_data
from grok_async import chat_with_grok_async

conversation_history = []


async def chat_with_ai_async(messages, api_key, model_name, debug=False):
    """使用grok_async.py中的函数调用API"""
    if debug:
        print(f"[API] 使用Grok API")
        print(f"[API] 使用模型: {model_name}")
        print(f"[API] 消息数量: {len(messages)}")
    
    try:
        # 直接调用grok_async.py中的函数，传入模型名称
        async for content in chat_with_grok_async(messages, api_key, model_name, debug=debug):
            yield content
                    
    except Exception as e:
        if debug:
            print(f"[API] 请求失败: {str(e)}")
        raise ValueError(f"API请求失败: {str(e)}")


def build_messages(user_input):
    """构建消息列表"""
    messages = []
    
    # 添加系统提示
    if "system_prompt" in role_data:
        messages.append({"role": "system", "content": role_data["system_prompt"]})
    
    # 添加历史记录
    if "history" in role_data:
        messages.extend(role_data["history"])
    
    # 添加对话历史
    messages.extend(conversation_history)
    
    # 添加用户输入
    messages.append({"role": "user", "content": user_input})
    
    return messages


async def granular_stream_display(api_key, messages, model_name, debug=False):
    """
    精细化流式显示：
    1. 前5个字符立即显示
    2. 之后每2秒更新一次
    3. 生成完成立即显示
    """
    accumulated_text = ""
    char_count = 0
    first_chars_threshold = 5  # 前5个字符立即显示
    regular_update_interval = 2.0  # 2秒间隔
    last_update_time = 0
    last_displayed_length = 0  # 记录上次显示的长度
    
    # 阶段标记
    phase = "collecting_first_chars"  # collecting_first_chars -> regular_updates -> completed
    
    # ⏱️ 时间日志
    start_time = time.time()
    first_chunk_time = None
    first_5chars_time = None
    update_times = []  # 记录每次更新的时间
    
    print("✍️输入中...", end='', flush=True)
    print(f"\n[⏱️ 请求开始时间: {time.strftime('%H:%M:%S')}]")
    
    try:
        async for chunk in chat_with_ai_async(messages, api_key, model_name, debug=debug):
            # 记录第一个chunk到达时间
            if first_chunk_time is None:
                first_chunk_time = time.time()
                elapsed = first_chunk_time - start_time
                print(f"[⏱️ 首个chunk到达: +{elapsed:.3f}秒]")
            
            # 逐字符处理，实现精确控制
            for char in chunk:
                accumulated_text += char
                char_count = len(accumulated_text)
                current_time = time.time()
                
                if phase == "collecting_first_chars":
                    # 阶段1：收集前5个字符后立即更新
                    if char_count >= first_chars_threshold:
                        first_5chars_time = current_time
                        elapsed_from_start = first_5chars_time - start_time
                        elapsed_from_first_chunk = first_5chars_time - first_chunk_time
                        
                        # 清除"输入中..."并显示前5个字符
                        print("\r" + " " * 10 + "\r", end='', flush=True)  # 清除之前的文本
                        print(accumulated_text, end='', flush=True)
                        last_displayed_length = len(accumulated_text)
                        phase = "regular_updates"
                        last_update_time = current_time
                        
                        print(f"\n[⏱️ 前5字符显示: 总耗时{elapsed_from_start:.3f}秒, 从首chunk{elapsed_from_first_chunk:.3f}秒]", end='', flush=True)
                        update_times.append(("首段显示", elapsed_from_start))
                        
                elif phase == "regular_updates":
                    # 阶段2：每2秒更新一次
                    if current_time - last_update_time >= regular_update_interval:
                        elapsed = current_time - start_time
                        interval = current_time - last_update_time
                        
                        # 清除之前显示的内容并显示新内容
                        clear_length = last_displayed_length + 20  # 额外清除标记文本
                        print("\r" + " " * clear_length + "\r", end='', flush=True)
                        print(accumulated_text, end='', flush=True)
                        last_displayed_length = len(accumulated_text)
                        last_update_time = current_time
                        
                        print(f"\n[⏱️ 定时更新: 总耗时{elapsed:.3f}秒, 间隔{interval:.3f}秒, {char_count}字符]", end='', flush=True)
                        update_times.append(("定时更新", elapsed))
        
        # 阶段3：立即最终更新
        if accumulated_text:
            end_time = time.time()
            total_elapsed = end_time - start_time
            
            # 清除之前显示的内容并显示最终内容
            clear_length = last_displayed_length + 30
            print("\r" + " " * clear_length + "\r", end='', flush=True)
            print(accumulated_text, end='', flush=True)
            
            print(f"\n[✅ 完成: 总耗时{total_elapsed:.3f}秒, 共{len(accumulated_text)}字符]")
            print(f"[⏱️ 平均速度: {len(accumulated_text)/total_elapsed:.1f}字符/秒]")
            
            # 打印详细时间线
            print("\n📊 时间线详情:")
            print(f"  请求发起 -> 首个chunk: {(first_chunk_time - start_time) if first_chunk_time else 0:.3f}秒")
            if first_5chars_time:
                print(f"  请求发起 -> 前5字符: {(first_5chars_time - start_time):.3f}秒")
            print(f"  请求发起 -> 全部完成: {total_elapsed:.3f}秒")
        
    except Exception as e:
        print(f"\n❌ 流式显示错误: {e}")
        raise


async def collect_full_response(api_key, messages, model_name, debug=False):
    """收集完整响应用于保存到历史记录"""
    full_response = ""
    try:
        async for chunk in chat_with_ai_async(messages, api_key, model_name, debug=False):
            full_response += chunk
        return full_response
    except Exception as e:
        print(f"❌ 收集响应错误: {e}")
        return ""


async def main():
    # 🔧 API配置 - 从环境变量读取
    API_KEY = os.getenv("GROK_API_KEY")
    MODEL_NAME = os.getenv("GROK_MODEL_NAME", "grok-4-fast-non-reasoning")  # 默认模型
    
    # 检查API密钥是否设置
    if not API_KEY:
        print("❌ 错误: 请设置 GROK_API_KEY 环境变量")
        print("💡 提示: 在 .env 文件中添加: GROK_API_KEY=你的API密钥")
        return
    
    # 🔍 设置调试模式
    DEBUG_MODE = True  # 改为False可关闭API详细日志
    
    print(f"🎭 当前角色: {role_data['name']}")
    print(f"📝 角色介绍: {role_data['summary']}")
    print(f"🤖 使用模型: {role_data.get('model', MODEL_NAME)}")
    print(f"🔑 API密钥: {API_KEY[:10]}...{API_KEY[-10:] if API_KEY else '未设置'}")
    print(f"🔍 调试模式: {'开启' if DEBUG_MODE else '关闭'}")
    print("=" * 50)

    while True:
        user_input = input("\n👤 你: ")
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("👋 对话结束")
            break

        messages = build_messages(user_input)

        # 👇 使用角色指定的模型（若没写，就用环境变量或默认模型）
        model_name = role_data.get("model", MODEL_NAME)

        # ✅ 精细化流式输出 - 5字符立即显示，然后每2秒更新
        print(f"🤖 {role_data['name']}: ", end='', flush=True)
        
        full_response = ""
        try:
            await granular_stream_display(API_KEY, messages, model_name, debug=DEBUG_MODE)
            full_response = await collect_full_response(API_KEY, messages, model_name, debug=DEBUG_MODE)
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            continue

        # 保存到对话历史
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    asyncio.run(main())