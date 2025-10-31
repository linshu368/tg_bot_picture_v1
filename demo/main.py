# main.py - 流式回复测试版本
from role import role_data
from api import GPTCaller
import sys

conversation_history = []

def build_messages(user_input):
    messages = []
    if "system_prompt" in role_data:
        messages.append({"role": "system", "content": role_data["system_prompt"]})
    if "history" in role_data:
        messages.extend(role_data["history"])
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_input})
    return messages


if __name__ == "__main__":
    gpt = GPTCaller()
    
    print(f"🎭 当前角色: {role_data['name']}")
    print(f"📝 角色介绍: {role_data['summary']}")
    print(f"🤖 使用模型: {role_data.get('model')}")
    print("="*50)

    while True:
        user_input = input("\n👤 你: ")
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("👋 对话结束")
            break

        messages = build_messages(user_input)

        # 👇 使用角色指定的模型（若没写，就用默认）
        model_name = role_data.get("model")

        # ✅ 流式输出 - 逐字显示回复
        print(f"🤖 {role_data['name']}: ", end='', flush=True)
        
        full_response = ""
        try:
            for chunk in gpt.get_stream_response(messages, model_name=model_name):
                print(chunk, end='', flush=True)  # 逐字打印
                full_response += chunk
            print()  # 换行
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            continue

        # 保存到对话历史
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": full_response})
