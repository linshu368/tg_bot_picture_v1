#AI纯生成器，不涉及任何业务逻辑，应放入GPT/
import time
import random
from typing import Optional, Callable, AsyncGenerator

class AICompletionPort:
    def __init__(self, gpt_caller):
        self.gpt = gpt_caller

    async def generate_reply(self, role_data, history, user_input, timeout=30, session_context_source=None, on_partial_reply: Optional[Callable[[str], None]] = None):
        """
        生成AI回复
        
        Args:
            role_data: 角色配置数据
            history: 会话历史消息
            user_input: 当前用户输入
            timeout: 超时时间
            session_context_source: 会话上下文来源标记，"snapshot" 表示来自快照会话
        
        说明：
            - 常规会话: system_prompt + role_data.history + MessageService历史
            - 快照会话: system_prompt + MessageService历史（已含快照完整上下文，跳过role_data.history避免重复）
        """
        # 打印输入的历史记录
        print(f"🧠 AI生成回复 | 输入历史记录数量: {len(history)} | 上下文来源: {session_context_source or '常规'}")
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
        
        # 1. 添加 system_prompt
        if "system_prompt" in role_data:
            messages.append({"role": "system", "content": role_data["system_prompt"]})
        
        # 2. 仅在非快照会话时添加角色预置 history（避免重复）
        if session_context_source != "snapshot" and "history" in role_data:
            messages.extend(role_data["history"])
            print(f"✅ 添加角色预置对话: {len(role_data.get('history', []))} 条")
        elif session_context_source == "snapshot":
            print(f"⏭️ 跳过角色预置对话（快照会话已包含完整上下文）")
        
        # 3. 添加实际会话历史
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
        
        # 收集完整回复
        full_response = ""
        
        # 调用异步流式 GPT API
        async for partial_reply in self.gpt.get_stream_response(messages, model_name=role_data.get("model"), timeout=timeout):
            full_response += partial_reply
            
            # 如果提供了回调函数，逐步调用它来处理部分回复
            if on_partial_reply:
                if callable(on_partial_reply):
                    # 同步回调
                    on_partial_reply(partial_reply)
                else:
                    # 异步回调
                    await on_partial_reply(partial_reply)

        # 结束流式生成
        print(f"🤖 AI生成回复完成 | 耗时: {time.time() - start:.2f}秒 | 总字符数: {len(full_response)}")
        print("🤖" + "="*48)
        
        return full_response

    async def generate_reply_stream(self, role_data, history, user_input, timeout=30, session_context_source=None) -> AsyncGenerator[str, None]:
        """
        流式生成AI回复 - 返回异步生成器，用于Telegram Bot的流式更新
        
        Args:
            role_data: 角色配置数据
            history: 会话历史消息
            user_input: 当前用户输入
            timeout: 超时时间
            session_context_source: 会话上下文来源标记
            
        Yields:
            str: 每个流式回复片段
        """
        # 打印输入的历史记录
        print(f"🧠 AI流式生成回复 | 输入历史记录数量: {len(history)} | 上下文来源: {session_context_source or '常规'}")
        
        # 构建 prompt（复用相同逻辑）
        messages = []
        
        # 1. 添加 system_prompt
        if "system_prompt" in role_data:
            messages.append({"role": "system", "content": role_data["system_prompt"]})
        
        # 2. 仅在非快照会话时添加角色预置 history（避免重复）
        if session_context_source != "snapshot" and "history" in role_data:
            messages.extend(role_data["history"])
            print(f"✅ 添加角色预置对话: {len(role_data.get('history', []))} 条")
        elif session_context_source == "snapshot":
            print(f"⏭️ 跳过角色预置对话（快照会话已包含完整上下文）")
        
        # 3. 添加实际会话历史
        messages.extend(history)
        
        print(f"🔧 构建完整消息列表 | 总消息数: {len(messages)}")
        print("🧠" + "="*48)

        # 模拟超时
        if random.random() < 0.01:
            raise TimeoutError("4004: 生成超时")

        # 开始计时
        start = time.time()
        
        # 流式生成并逐步返回
        async for partial_reply in self.gpt.get_stream_response(messages, model_name=role_data.get("model"), timeout=timeout):
            yield partial_reply

        # 结束流式生成
        print(f"🤖 AI流式生成完成 | 耗时: {time.time() - start:.2f}秒")
        print("🤖" + "="*48)


# ✅ 全局唯一实例 - 与其他服务保持一致的设计模式

from demo.novel_async import AsyncNovelCaller
ai_completion_port = AICompletionPort(AsyncNovelCaller())
