# main.py
from role import role_data
from api import GPTCaller

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

    while True:
        user_input = input("👤 你: ")
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("👋 对话结束")
            break

        messages = build_messages(user_input)

        # 👇 使用角色指定的模型（若没写，就用默认）
        model_name = role_data.get("model")

        response = gpt.get_response(messages, model_name=model_name)

        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": response})

        print(f"🤖 {role_data['name']}: {response}")
