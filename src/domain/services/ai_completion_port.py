#AI纯生成器，不涉及任何业务逻辑，应放入GPT/
import time
import random
import os
from typing import Optional, Callable, AsyncGenerator, Dict, Any
from demo.grok_async import AsyncGrokCaller
from demo.novel_async import AsyncNovelCaller

class AICompletionPort:
    def __init__(self, grok_caller: Optional[AsyncGrokCaller] = None, novel_caller: Optional[AsyncNovelCaller] = None):
        self.grok = grok_caller
        self.novel = novel_caller
        # 前3轮对话的增强指令模板
        self.early_conversation_instruction = (
            "##用户信息:{user_context}\n"
            "##系统指令：以下为最高优先级指令。\n"
            "{system_instructions}"
        )
        # 第4轮及以后对话的持续指令模板
        self.ongoing_conversation_instruction = (
            "##用户信息:{user_context}\n"
            "##持续指令：\n"
            "{ongoing_instructions}"
        )
        # 取消实例级共享状态，改为通过回调向调用方传递本次使用的指令信息
        # self.last_used_instructions 已移除


    def _safe_for_logging(self, text: str, max_len: Optional[int] = None) -> str:
        """Return a logging-safe preview of text, avoiding Unicode surrogate errors.

        - Truncates to max_len if provided
        - Replaces unencodable characters with Python-style backslash escapes
        """
        try:
            if text is None:
                return ""
            if max_len is not None:
                text = text[:max_len]
            # backslashreplace ensures surrogates or other problematic code points won't crash stdout
            return text.encode('utf-8', 'backslashreplace').decode('utf-8', 'strict')
        except Exception:
            return "<unprintable>"


    def _count_real_user_turns(self, history):
        """
        统计会话中真实用户发言轮次
        只统计 role == "user" 的消息数量
        """
        user_turns = sum(1 for msg in history if msg.get("role") == "user")
        print(f"📊 统计用户对话轮次: {user_turns}")
        return user_turns
    
    def _find_last_user_message_index(self, messages):
        """
        找到消息列表中最后一条用户消息的索引
        从后往前查找，返回最后一条 role == "user" 的消息索引
        """
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                print(f"🔍 找到最后一条用户消息位置: index={i}")
                return i
        print("⚠️ 未找到用户消息")
        return None
    
    def _enhance_user_message_with_instruction(self, original_content, user_context="当前对话", instruction_type="system"):
        """
        为用户消息添加增强指令
        
        Args:
            original_content: 原始用户消息内容
            user_context: 用户上下文信息（用于指令中的占位符）
            instruction_type: 指令类型，"system"(前3轮) 或 "ongoing"(第4轮及以后)
        
        Returns:
            tuple: (增强后的消息内容, 使用的指令内容)
        """
        # 代理到公共 util，保持单一实现
        from src.utils.enhance import enhance_user_input
        enhanced_content, instructions = enhance_user_input(original_content, instruction_type, user_context=user_context)
        print(f"✨ 用户消息已增强({instruction_type}) | 原长度: {len(original_content)} | 增强后长度: {len(enhanced_content)}")
        return enhanced_content, instructions if instructions else None

    async def generate_reply_stream(self, role_data, history, user_input, timeout=60, session_context_source=None, caller: Optional[object] = None, model_name: Optional[str] = None, on_used_instructions: Optional[Callable[[Dict[str, Any]], None]] = None, apply_enhancement: bool = False) -> AsyncGenerator[str, None]:
        """
        流式生成AI回复 - 返回异步生成器，用于Telegram Bot的流式更新
        
        Args:
            role_data: 角色配置数据
            history: 会话历史消息
            user_input: 当前用户输入
            timeout: 超时时间
            session_context_source: 会话上下文来源标记
            on_used_instructions: 可选回调，携带本次调用实际使用的指令元数据（仅调用一次）
            apply_enhancement: 是否在本方法中对最后一条用户消息做指令增强（默认 False）
            
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
        
        # 🆕 4. 对话增强指令逻辑（流式版本）
        user_turn_count = self._count_real_user_turns(history)
        used_meta: Dict[str, Any] = {
            "turn_count": user_turn_count,
            "instruction_type": None,
            "system_instructions": None,
            "ongoing_instructions": None,
            "model": model_name
        }
        
        if user_turn_count <= 3 and messages:
            # 前3轮：使用系统指令
            last_user_msg_index = self._find_last_user_message_index(messages)
            if last_user_msg_index is not None:
                original_content = messages[last_user_msg_index]["content"]
                enhanced_content, used_instruction = self._enhance_user_message_with_instruction(
                    original_content, 
                    original_content,
                    instruction_type="system"
                )
                if apply_enhancement:
                    messages[last_user_msg_index]["content"] = enhanced_content
                used_meta["instruction_type"] = "system"
                used_meta["system_instructions"] = used_instruction
                # 🆕 新字段写入逻辑：记录本轮实际使用的指令（供上层存入 messages.instructions）
                used_meta["instructions"] = used_instruction
                if apply_enhancement:
                    print(f"✅ 已为第{user_turn_count}轮对话添加系统增强指令（流式）")
        elif user_turn_count >= 4 and messages:
            # 第4轮及以后：使用持续指令
            last_user_msg_index = self._find_last_user_message_index(messages)
            if last_user_msg_index is not None:
                original_content = messages[last_user_msg_index]["content"]
                enhanced_content, used_instruction = self._enhance_user_message_with_instruction(
                    original_content, 
                    original_content,
                    instruction_type="ongoing"
                )
                if apply_enhancement:
                    messages[last_user_msg_index]["content"] = enhanced_content
                used_meta["instruction_type"] = "ongoing"
                used_meta["ongoing_instructions"] = used_instruction
                # 🆕 新字段写入逻辑：记录本轮实际使用的指令（供上层存入 messages.instructions）
                used_meta["instructions"] = used_instruction
                if apply_enhancement:
                    print(f"✅ 已为第{user_turn_count}轮对话添加持续增强指令（流式）")
        
        print(f"🔧 构建完整消息列表 | 总消息数: {len(messages)}")
        print("🧠" + "="*48)

        # 模拟超时
        if random.random() < 0.01:
            raise TimeoutError("4004: 生成超时")

        # 开始计时
        start = time.time()
        
        # 流式生成并逐步返回
        chunk_count = 0
        total_chars = 0
        # 选择调用器与模型
        use_caller = caller or self._select_default_caller()
        use_model = model_name
        if use_caller is None:
            raise RuntimeError("未配置任何可用的AI调用器（Grok/Novel）")

        # 🆕 新字段写入逻辑：补充回调元数据（模型名与本次调用的上下文载荷）
        try:
            used_meta["model_name"] = model_name
            # 100% 复现：记录本次实际投喂的完整 messages
            used_meta["final_messages"] = list(messages)
            used_meta["prompt_payload"] = {
                "system_prompt": role_data.get("system_prompt") if isinstance(role_data, dict) else None,
                "history": history,
                "user_input": user_input,
                "instructions": used_meta.get("instructions"),
                "instruction_type": used_meta.get("instruction_type"),
                # 兼容旧字段的同时，加入最终 messages
                "final_messages": list(messages)
            }
        except Exception:
            pass

        # 在开始流式之前，回调一次提供指令使用的元数据
        if on_used_instructions and used_meta.get("instruction_type") is not None:
            try:
                on_used_instructions(dict(used_meta))
            except Exception as _e:
                print(f"⚠️ on_used_instructions 回调执行失败: {_e}")

        async for partial_reply in use_caller.get_stream_response(messages, use_model, timeout=timeout):
            chunk_count += 1
            total_chars += len(partial_reply)
            safe_chunk_preview = self._safe_for_logging(partial_reply, 50)
            # print(f"🔄 收到chunk #{chunk_count}: {len(partial_reply)} 字符 | 内容预览: {safe_chunk_preview}...")
            yield partial_reply

        # 结束流式生成
        print(f"🤖 AI流式生成完成 | 耗时: {time.time() - start:.2f}秒 | 总chunk数: {chunk_count} | 总字符数: {total_chars}")
        print("🤖" + "="*48)

    async def generate_reply_stream_with_retry(self, role_data, history, user_input, 
                                             max_retries=3, timeout=60, session_context_source=None,
                                             on_used_instructions: Optional[Callable[[Dict[str, Any]], None]] = None,
                                             apply_enhancement: bool = False) -> AsyncGenerator[str, None]:
        """
        带重试机制的流式生成AI回复
        
        Args:
            role_data: 角色配置数据
            history: 会话历史消息
            user_input: 当前用户输入
            max_retries: 最大重试次数，默认3次
            timeout: 超时时间
            session_context_source: 会话上下文来源标记
            on_used_instructions: 可选回调，携带本次调用实际使用的指令元数据（仅在成功的那次尝试触发一次）
            apply_enhancement: 是否在本方法中对最后一条用户消息做指令增强（默认 False）
            
        Yields:
            str: 每个流式回复片段
        """
        for attempt in range(max_retries):
            try:
                print(f"🔄 AI生成尝试 #{attempt + 1}/{max_retries}")

                # 前两次使用 Grok，第三次使用 Novel
                if attempt < 2:
                    if not self.grok:
                        raise RuntimeError("Grok 调用器未配置")
                    provider = "Grok"
                    caller = self.grok
                    model_env = os.getenv("GROK_MODEL")
                else:
                    if not self.novel:
                        raise RuntimeError("Novel 调用器未配置")
                    provider = "Novel"
                    caller = self.novel
                    model_env = os.getenv("NOVEL_MODEL")

                print(f"🚀 本次尝试使用提供方: {provider} | 模型: {model_env}")

                # 仅在成功开始产出内容后再对上层触发回调，避免失败尝试污染
                used_meta_candidate: Dict[str, Any] = {}
                def _capture_used_instructions(meta: Dict[str, Any]) -> None:
                    # 记录候选元数据，稍后在首次产出时统一上报
                    used_meta_candidate.clear()
                    used_meta_candidate.update(meta or {})
                    # 增补 provider/model
                    used_meta_candidate["provider"] = provider
                    used_meta_candidate["model"] = model_env

                # 使用统一的超时策略（两边 caller 都使用 total=timeout）
                first_chunk_sent = False
                async for chunk in self.generate_reply_stream(
                    role_data=role_data,
                    history=history,
                    user_input=user_input,
                    timeout=timeout,
                    session_context_source=session_context_source,
                    caller=caller,
                    model_name=model_env,
                    on_used_instructions=_capture_used_instructions,
                    apply_enhancement=apply_enhancement
                ):
                    if not first_chunk_sent:
                        # 首次产出内容时再把本次尝试的元数据上报给调用方
                        if on_used_instructions and used_meta_candidate:
                            try:
                                on_used_instructions(dict(used_meta_candidate))
                            except Exception as _e:
                                print(f"⚠️ on_used_instructions 回调执行失败: {_e}")
                        first_chunk_sent = True
                    yield chunk

                # 成功生成，退出重试循环
                print(f"✅ AI生成成功（第{attempt + 1}次尝试，提供方: {provider}）")
                return

            except Exception as e:
                print(f"❌ AI生成失败（第{attempt + 1}次尝试）: {e}")

                if attempt == max_retries - 1:
                    # 最后一次重试失败，返回固定话术
                    print(f"💔 所有重试均失败，返回兜底话术")
                    yield "抱歉，回复出现了问题，后台正在加紧修复，请耐心等待"
                    return
                else:
                    # 继续重试
                    print(f"🔄 准备进行第{attempt + 2}次重试...")
                    continue

    def _safe_for_logging(self, text: str, max_length: int = 50) -> str:
        """安全地截断文本用于日志输出"""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def _select_default_caller(self) -> Optional[object]:
        """
        选择一个默认可用的调用器：
        优先 Novel，其次 Grok；如果都不存在则返回 None
        """
        if self.novel:
            return self.novel
        if self.grok:
            return self.grok
        return None
    
    # get_last_used_instructions 已废弃（移除）


# ✅ 全局唯一实例（临时占位，实际使用时应通过容器获取）
# 在应用启动时，应该通过容器创建并替换这个实例
ai_completion_port = None  # 将在容器中初始化
