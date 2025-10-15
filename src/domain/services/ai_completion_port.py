#AI纯生成器，不涉及任何业务逻辑，应放入GPT/
import time
import random

class AICompletionPort:
    def __init__(self, gpt_caller):
        self.gpt = gpt_caller

    async def generate_reply(self, role_data, history, user_input, timeout=30):
        # 打印输入的历史记录
        print(f"🧠 AI生成回复 | 输入历史记录数量: {len(history)}")
        if history:
            print("📜 输入历史记录:")
            for i, msg in enumerate(history):
                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                print(f"  [{i+1}] {role_emoji} {msg['role']}")
                # 限制内容长度
                content_preview = msg['content'][:80] + "..." if len(msg['content']) > 80 else msg['content']
                print(f"      📝 {content_preview}")
        else:
            print("📜 输入历史记录为空")

        # 构建 prompt
        messages = []
        if "system_prompt" in role_data:
            messages.append({"role": "system", "content": role_data["system_prompt"]})
        if "history" in role_data:
            messages.extend(role_data["history"])
        messages.extend(history)
        # 注意：不再额外添加 user_input，因为它已经在 history 中了

        # 打印构建的完整消息列表
        print(f"🔧 构建完整消息列表 | 总消息数: {len(messages)}")
        print("📋 完整消息列表:")
        for i, msg in enumerate(messages):
            role_emoji = {"system": "⚙️", "user": "👤", "assistant": "🤖"}.get(msg["role"], "❓")
            print(f"  [{i+1}] {role_emoji} {msg['role']}")
            content_preview = msg['content'][:80] + "..." if len(msg['content']) > 80 else msg['content']
            print(f"      📝 {content_preview}")
        
        print(f"👤 当前用户输入: {user_input}")
        print("🧠" + "="*48)

        # 模拟超时
        # （这里应该在 GPTCaller 层做真正的 async 超时控制，这里先简化）
        if random.random() < 0.01:
            raise TimeoutError("4004: 生成超时")

        # 开始计时：从调用GPT API开始
        start = time.time()
        
        # 调用 GPT（注意：GPTCaller 也要改成 async）
        response = await self.gpt.get_response(messages, model_name=role_data.get("model"))
        
        # 打印生成的回复
        print(f"🤖 AI生成回复完成 | 耗时: {time.time() - start:.2f}秒")
        response_preview = response[:100] + "..." if len(response) > 100 else response
        print(f"💬 生成的回复: {response_preview}")
        print("🤖" + "="*48)
        
        return response
