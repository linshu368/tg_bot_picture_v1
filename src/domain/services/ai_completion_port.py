#AI纯生成器，不涉及任何业务逻辑，应放入GPT/
import time
import random

class AICompletionPort:
    def __init__(self, gpt_caller):
        self.gpt = gpt_caller

    async def generate_reply(self, role_data, history, user_input, timeout=30):
        start = time.time()

        # 构建 prompt
        messages = []
        if "system_prompt" in role_data:
            messages.append({"role": "system", "content": role_data["system_prompt"]})
        if "history" in role_data:
            messages.extend(role_data["history"])
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        # 模拟超时
        # （这里应该在 GPTCaller 层做真正的 async 超时控制，这里先简化）
        if random.random() < 0.01:
            raise TimeoutError("4004: 生成超时")

        # 调用 GPT（注意：GPTCaller 也要改成 async）
        return await self.gpt.get_response(messages, model_name=role_data.get("model"))
