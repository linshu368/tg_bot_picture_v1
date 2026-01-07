#AI纯生成器，不涉及任何业务逻辑，应放入GPT/
import time
import random
import os
import copy
import asyncio
import aiohttp
import json
from typing import Optional, Callable, AsyncGenerator, Dict, Any, List
from dataclasses import dataclass
from demo.grok_async import AsyncGrokCaller
from demo.novel_async import AsyncNovelCaller
from demo.gemini_async import AsyncGeminiCaller
from demo.deepseek_async import AsyncDeepseekCaller
from src.infrastructure.monitoring.metrics import (
    AI_PROVIDER_CALLS_TOTAL,
    AI_PROVIDER_CALLS_FAILED_TOTAL,
    AI_FIRST_TOKEN_LATENCY
)

@dataclass
class CallProfile:
    """定义单次AI调用的配置规格"""
    caller_attr: str       # 对应 self 中的实例属性名，如 'deepseek_1'
    model_env_key: str     # 模型名称的环境变量 Key
    timeout_env_key: str   # 首字超时时间的环境变量 Key
    provider_name: str     # 用于日志和监控显示的名称
    default_timeout: float = 3.0 # 默认超时时间
    default_model: str = None    # 默认模型名称（当环境变量未设置时使用）

class AICompletionPort:
    def __init__(self, 
                 grok_caller: Optional[AsyncGrokCaller] = None, 
                 novel_caller: Optional[AsyncNovelCaller] = None, 
                 gemini_caller: Optional[AsyncGeminiCaller] = None, 
                 deepseek_caller_1: Optional[AsyncDeepseekCaller] = None,
                 deepseek_caller_3: Optional[AsyncDeepseekCaller] = None):
        
        self.grok = grok_caller
        self.novel = novel_caller
        self.gemini = gemini_caller
        # 兼容旧代码，如果只传了 deepseek_caller_1 但其他地方还在引用 self.deepseek
        # 我们可以保留一个指向主实例的引用，或者逐步清理
        self.deepseek_1 = deepseek_caller_1
        self.deepseek_3 = deepseek_caller_3
        # 保持对旧代码的兼容性 (如果仍有直接访问 self.deepseek 的情况)
        self.deepseek = deepseek_caller_1

        # 前3轮对话的增强指令模板
        self.early_conversation_instruction = (
            "##系统指令：以下为最高优先级指令。\n"
            "{system_instructions}"
            "##用户指令:{user_context}\n"
        )
        # 第4轮及以后对话的持续指令模板
        self.ongoing_conversation_instruction = (
            "##系统指令：\n"
            "{ongoing_instructions}"
            "#用户指令:{user_context}\n"
        )
        # 取消实例级共享状态，改为通过回调向调用方传递本次使用的指令信息
        # self.last_used_instructions 已移除

        # -------------------------------------------------------------------------
        # 1. 原子能力库 (Profiles): 定义所有可用的原子调用方式
        # -------------------------------------------------------------------------
        self.profiles = {
            # --- DeepSeek 策略 (v1/v2 使用 instance 1) ---
            "deepseek_v1": CallProfile(
                caller_attr="deepseek_1",
                model_env_key="DEEPSEEK_MODEL_1",
                timeout_env_key="DEEPSEEK_1_FIRST_CHUNK_TIMEOUT",
                provider_name="DeepSeek_V1",
                default_timeout=3
            ),
            "deepseek_v2": CallProfile(
                caller_attr="deepseek_1",
                model_env_key="DEEPSEEK_MODEL_2",
                timeout_env_key="DEEPSEEK_2_FIRST_CHUNK_TIMEOUT",
                provider_name="DeepSeek_V2",
                default_timeout=2.5
            ),
            
            # --- DeepSeek 策略 (v3 使用 instance 3 - SiliconFlow) ---
            "deepseek_v3": CallProfile(
                caller_attr="deepseek_3",
                model_env_key="DEEPSEEK_MODEL_3",
                timeout_env_key="DEEPSEEK_3_FIRST_CHUNK_TIMEOUT",
                provider_name="DeepSeek_V3",
                default_timeout=7,
                default_model="Pro/deepseek-ai/DeepSeek-V3.1-Terminus"
            ),
            
            # --- Gemini 策略 ---
            "gemini_v1": CallProfile(
                caller_attr="gemini",
                model_env_key="GEMINI_MODEL", 
                timeout_env_key="GEMINI_1_FIRST_CHUNK_TIMEOUT",
                provider_name="Gemini_V1",
                default_timeout=3.5
            ),
            "gemini_v2": CallProfile(
                caller_attr="gemini",
                model_env_key="GEMINI_MODEL", 
                timeout_env_key="GEMINI_2_FIRST_CHUNK_TIMEOUT",
                provider_name="Gemini_V2",
                default_timeout=3
            ),

            # --- Grok 策略 ---
            "grok_v1": CallProfile(
                caller_attr="grok",
                model_env_key="GROK_MODEL",
                timeout_env_key="GROK_FIRST_CHUNK_TIMEOUT",
                provider_name="Grok",
                default_timeout=3.0
            ),
        }

        # -------------------------------------------------------------------------
        # 2. 策略路由表 (Strategy Map): 定义不同模式下的调用链顺序
        # -------------------------------------------------------------------------
        self.strategies = {
            # fast: Grok -> Gemini -> Grok
            "fast": ["grok_v1", "gemini_v1", "grok_v1"],
            
            # story: Gemini (fast) -> Gemini (retry with longer timeout) -> Grok
            "story": ["gemini_v1", "gemini_v2", "grok_v1"],
            
            # immersive: DeepSeek V3 (SiliconFlow) -> DeepSeek V2 (Official) -> Grok
            "immersive": ["deepseek_v3", "deepseek_v2", "grok_v1"]
        }

        # AI流式生成 - 2. 中间卡顿熔断时长 (默认3.0秒)
        inter_chunk_timeout_str = os.getenv("AI_STREAM_INTER_CHUNK_TIMEOUT")
        try:
            self.stream_inter_chunk_timeout = float(inter_chunk_timeout_str) if inter_chunk_timeout_str else 3.0
        except (TypeError, ValueError):
            print("⚠️ AI_STREAM_INTER_CHUNK_TIMEOUT 配置无效，使用默认值 3.0 秒")
            self.stream_inter_chunk_timeout = 3.0

        # AI流式生成 - 3. 总时长熔断 (默认15.0秒)
        total_timeout_str = os.getenv("AI_STREAM_TOTAL_TIMEOUT")
        try:
            self.stream_total_timeout = float(total_timeout_str) if total_timeout_str else 15.0
        except (TypeError, ValueError):
            print("⚠️ AI_STREAM_TOTAL_TIMEOUT 配置无效，使用默认值 15.0 秒")
            self.stream_total_timeout = 15.0



    async def fetch_openrouter_stats(self, generation_id: str, api_key: str):
        """
        异步获取 OpenRouter 统计信息并打印 (临时调试用)
        支持多次重试，因为 OpenRouter 的统计数据可能不会在流式生成开始时立即就绪。
        """
        if not generation_id or not api_key:
            return

        url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        # 初始等待，避开刚开始的空白期
        await asyncio.sleep(5) 
        
        print(f"🔍 [OpenRouter Stats] 正在查询 generation_id: {generation_id}")
        
        max_retries = 5
        base_delay = 3.0
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            # 简单的检查，看是不是空数据或者占位符（如果需要的话）
                            # 只要成功拿到 200，且包含 data，通常就可以了
                            
                            # 漂亮的打印 JSON
                            print(f"📊 [OpenRouter Stats] 获取成功 (attempt {attempt+1}):\n{json.dumps(data, indent=2, ensure_ascii=False)}")
                            return # 成功后直接退出
                        elif response.status == 404:
                            # 404 表示暂时没生成，需要重试
                            if attempt < max_retries - 1:
                                delay = base_delay * (1.5 ** attempt) # 指数退避: 3, 4.5, 6.75, ...
                                print(f"⏳ [OpenRouter Stats] 404 Not Found, 等待 {delay:.1f}s 后重试 ({attempt+1}/{max_retries})...")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                text = await response.text()
                                print(f"⚠️ [OpenRouter Stats] 最终查询失败: {response.status} - {text}")
                        else:
                            # 其他错误，打印并退出，或者也重试？通常 401/400 没必要重试
                            text = await response.text()
                            print(f"⚠️ [OpenRouter Stats] 查询异常: {response.status} - {text}")
                            return
            except Exception as e:
                print(f"❌ [OpenRouter Stats] 发生异常: {e}")
                # 异常情况下也稍微等等再重试
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return

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

    async def generate_reply_stream(self, role_data, history, user_input, timeout=60, session_context_source=None, caller: Optional[object] = None, model_name: Optional[str] = None, execution_context: Optional[Dict[str, Any]] = None, apply_enhancement: bool = False, model_mode: str = "immersive") -> AsyncGenerator[str, None]:
        """
        流式生成AI回复 - 返回异步生成器，用于Telegram Bot的流式更新
        
        Args:
            role_data: 角色配置数据
            history: 会话历史消息
            user_input: 当前用户指令
            timeout: 超时时间
            session_context_source: 会话上下文来源标记
            execution_context: 可选的上下文容器（字典），用于回传本次调用的元数据（指令、generation_id等）
            apply_enhancement: 是否在本方法中对最后一条用户消息做指令增强（默认 False）
            model_mode: 模型等级/模式（immersive/story/fast）
            
        Yields:
            str: 每个流式回复片段
        """
        # 打印输入的历史记录
        print(f"🧠 AI流式生成回复 | 模式: {model_mode} | 输入历史记录数量: {len(history)} | 上下文来源: {session_context_source or '常规'}")
        
        # 构建 prompt（复用相同逻辑）
        messages = []
        history_for_prompt = copy.deepcopy(history or [])
        
        # 1. 添加 system_prompt
        if "system_prompt" in role_data:
            messages.append({"role": "system", "content": role_data["system_prompt"]})
        
        # 2. 仅在非快照会话时添加角色预置 history（避免重复）
        if session_context_source != "snapshot" and "history" in role_data:
            messages.extend(role_data["history"])
            print(f"✅ 添加角色预置对话: {len(role_data.get('history', []))} 条")
        elif session_context_source == "snapshot":
            print(f"⏭️ 跳过角色预置对话（快照会话已包含完整上下文）")
        
        # 3. 添加实际会话历史（使用副本，避免污染原始记录）
        messages.extend(history_for_prompt)
        
        # 🆕 4. 对话增强指令逻辑（流式版本）
        user_turn_count = self._count_real_user_turns(history)
        
        # 本地元数据收集
        local_meta: Dict[str, Any] = {
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
                local_meta["instruction_type"] = "system"
                local_meta["system_instructions"] = used_instruction
                # 🆕 新字段写入逻辑：记录本轮实际使用的指令（供上层存入 messages.instructions）
                local_meta["instructions"] = used_instruction
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
                local_meta["instruction_type"] = "ongoing"
                local_meta["ongoing_instructions"] = used_instruction
                # 🆕 新字段写入逻辑：记录本轮实际使用的指令（供上层存入 messages.instructions）
                local_meta["instructions"] = used_instruction
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
            local_meta["model_name"] = model_name
            # 100% 复现：记录本次实际投喂的完整 messages
            local_meta["final_messages"] = list(messages)
            local_meta["prompt_payload"] = {
                "system_prompt": role_data.get("system_prompt") if isinstance(role_data, dict) else None,
                "history": history_for_prompt,
                "user_input": user_input,
                "instructions": local_meta.get("instructions"),
                "instruction_type": local_meta.get("instruction_type"),
                # 兼容旧字段的同时，加入最终 messages
                "final_messages": list(messages)
            }
        except Exception:
            pass

        # 同步元数据到外部容器
        if execution_context is not None:
            try:
                execution_context.update(local_meta)
            except Exception as _e:
                print(f"⚠️ 更新 execution_context 失败: {_e}")

        # 准备 OpenRouter 统计回调
        async def _on_generation_id(gen_id: str):
            # 记录 generation_id 到元数据中
            if gen_id:
                # 🛑 安全检查：确认是 OpenRouter 的 URL
                caller_url = getattr(use_caller, 'url', '') or ''
                if "openrouter.ai" not in caller_url:
                    # 如果不是 OpenRouter，忽略这个 ID，避免后续查询报错
                    return

                print(f"🎟️ [Callback] 收到 OpenRouter generation_id: {gen_id}")
                local_meta["generation_id"] = gen_id
                
                # 尝试获取 API Key 以便后续查询
                caller_api_key = getattr(use_caller, 'api_key', '') or ''
                if caller_api_key:
                    local_meta["api_key"] = caller_api_key
                
                # 同步到外部容器
                if execution_context is not None:
                    try:
                        execution_context["generation_id"] = gen_id
                        if caller_api_key:
                            execution_context["api_key"] = caller_api_key
                    except Exception as _e:
                        print(f"⚠️ 更新 execution_context (gen_id) 失败: {_e}")

        # 检查 get_stream_response 是否支持 on_generation_id 参数
        # 这里做一个简单的兼容性处理，如果支持就传
        import inspect
        has_gen_id_param = False
        try:
             sig = inspect.signature(use_caller.get_stream_response)
             if 'on_generation_id' in sig.parameters:
                 has_gen_id_param = True
        except Exception:
             pass

        stream_kwargs = {}
        if has_gen_id_param:
            stream_kwargs['on_generation_id'] = _on_generation_id

        async for partial_reply in use_caller.get_stream_response(messages, use_model, timeout=timeout, **stream_kwargs):
            chunk_count += 1
            total_chars += len(partial_reply)
            safe_chunk_preview = self._safe_for_logging(partial_reply, 50)
            # print(f"🔄 收到chunk #{chunk_count}: {len(partial_reply)} 字符 | 内容预览: {safe_chunk_preview}...")
            yield partial_reply

        # 结束流式生成
        print(f"🤖 AI流式生成完成 | 耗时: {time.time() - start:.2f}秒 | 总chunk数: {chunk_count} | 总字符数: {total_chars}")
        print("🤖" + "="*48)

    async def _stream_managed(self, generator: AsyncGenerator[str, None], first_chunk_timeout: float, inter_chunk_timeout: float = 5.0, total_timeout: float = 20.0, on_chunk_received: Callable[[str], None] = None, provider_name: str = "Unknown", on_duration_calculated: Callable[[float], None] = None) -> AsyncGenerator[str, None]:
        """
        全能流式包装器，实现三道防线超时控制：
        1. 首响超时 (TTFT): 抛出异常 -> 触发重试
        2. 中间卡顿: 停止生成 -> 视为成功
        3. 总时长超时: 停止生成 -> 视为成功
        """
        start_time = None
        is_first_chunk = True
        
        try:
            # Stage 1: First Chunk Timeout
            try:
                first_chunk = await asyncio.wait_for(generator.__anext__(), timeout=first_chunk_timeout)
                start_time = time.time()
                if on_chunk_received:
                    on_chunk_received(first_chunk)
                yield first_chunk
                is_first_chunk = False
            except asyncio.TimeoutError:
                # 第一道防线：首响超时 -> 抛出异常，让上层去重试
                await generator.aclose()
                raise TimeoutError(f"{provider_name} 首个chunk超时（超过{first_chunk_timeout}秒）")
            except StopAsyncIteration:
                await generator.aclose()
                raise RuntimeError(f"{provider_name} 未返回任何内容")
            
            # Stage 2 & 3: Inter-Chunk & Total Timeout
            while True:
                # 计算剩余的总可用时间
                elapsed = time.time() - start_time
                remaining_total = total_timeout - elapsed
                
                if remaining_total <= 0:
                    print(f"⏱️ {provider_name} 达到总时长熔断阈值 ({total_timeout}s)，停止生成")
                    break # 第三道防线：总时长超时 -> 正常结束
                
                # 计算本次 wait 的时间：取 Inter-Chunk 和 Remaining-Total 的较小值
                # 注意：Inter-Chunk 是为了防止单次生成卡死，Remaining-Total 是为了防止总时长过长
                wait_time = min(inter_chunk_timeout, remaining_total)
                
                try:
                    chunk = await asyncio.wait_for(generator.__anext__(), timeout=wait_time)
                    if on_chunk_received:
                        on_chunk_received(chunk)
                    yield chunk
                except asyncio.TimeoutError:
                    # 判断是哪种超时
                    if time.time() - start_time >= total_timeout:
                         print(f"⏱️ {provider_name} 达到总时长熔断阈值 ({total_timeout}s)，停止生成")
                         break # 第三道防线
                    else:
                         print(f"🐢 {provider_name} 中间生成卡顿（超过{inter_chunk_timeout}s），提前截断")
                         break # 第二道防线：中间卡顿 -> 正常结束（截断）
                except StopAsyncIteration:
                    break # 正常结束

        except Exception as e:
            # 确保生成器被关闭
            try:
                await generator.aclose()
            except:
                pass
            if isinstance(e, (TimeoutError, RuntimeError)) and is_first_chunk:
                raise e # 首响相关的错误往上抛，触发重试
            
            # 其他错误（如网络中断），如果不是首响，也可以考虑截断而不是报错？
            if is_first_chunk:
                 raise e
            else:
                 print(f"⚠️ {provider_name} 生成过程中发生异常: {e}，视为截断")
                 # 异常情况下，我们依然可以计算已消耗的时间
                 pass
        
        finally:
             # 在生成结束时，计算并回调实际时长
             if start_time and on_duration_calculated:
                 duration = time.time() - start_time
                 try:
                     on_duration_calculated(duration)
                 except Exception as _e:
                     print(f"⚠️ on_duration_calculated 回调执行失败: {_e}")

    async def generate_reply_stream_with_retry(self, role_data, history, user_input, 
                                             max_retries=3, timeout=60, session_context_source=None,
                                             execution_context: Optional[Dict[str, Any]] = None,
                                             apply_enhancement: bool = False,
                                             model_mode: str = "immersive") -> AsyncGenerator[str, None]:
        """
        带重试机制的流式生成AI回复
        
        Args:
            role_data: 角色配置数据
            history: 会话历史消息
            user_input: 当前用户指令
            max_retries: 最大重试次数，默认3次
            timeout: 超时时间
            session_context_source: 会话上下文来源标记
            execution_context: 可选的上下文容器（字典），用于回传本次调用的元数据
            apply_enhancement: 是否在本方法中对最后一条用户消息做指令增强（默认 False）
            model_mode: 模型等级/模式（immersive/story/fast）
            
        Yields:
            str: 每个流式回复片段
        """
        # 1. 获取当前模式对应的策略链
        # 默认兜底使用 immersive 策略
        strategy_keys = self.strategies.get(model_mode, self.strategies["immersive"])
        
        # 2. 转换为具体的配置对象列表（仅包含有效的配置）
        execution_plan = [self.profiles[key] for key in strategy_keys if key in self.profiles]

        if not execution_plan:
             raise RuntimeError(f"策略 '{model_mode}' 未定义任何有效的执行计划")

        # 限制重试次数不超过计划长度
        total_attempts = min(max_retries, len(execution_plan))

        for attempt in range(total_attempts):
            profile = execution_plan[attempt]
            
            # 动态获取 caller 实例
            caller = getattr(self, profile.caller_attr, None)
            if not caller:
                print(f"⚠️ 调用器 '{profile.caller_attr}' 未初始化，跳过此步骤")
                continue

            # 动态获取环境变量配置
            model_env = os.getenv(profile.model_env_key)
            # 如果环境变量未设置，使用 profile 定义的默认值
            if not model_env and profile.default_model:
                model_env = profile.default_model
                
            timeout_env_val = os.getenv(profile.timeout_env_key)
            try:
                first_chunk_timeout = float(timeout_env_val) if timeout_env_val else profile.default_timeout
            except ValueError:
                first_chunk_timeout = profile.default_timeout

            provider_display_name = profile.provider_name

            try:
                print(f"🔄 AI生成尝试 #{attempt + 1}/{total_attempts}")
                print(f"🚀 本次尝试使用提供方: {provider_display_name} | 模型: {model_env} | 模式: {model_mode} | 首字超时: {first_chunk_timeout}s")

                # 📊 T0: 记录 AI 调用次数
                AI_PROVIDER_CALLS_TOTAL.labels(provider=provider_display_name, model=model_env or "unknown").inc()
                
                # ⏱️ T1: 记录 AI 请求发起时间
                ai_req_start = time.time()

                # 更新 execution_context 中的重试相关信息
                if execution_context is not None:
                    execution_context["provider"] = provider_display_name
                    execution_context["model"] = model_env
                    execution_context["attempt_count"] = attempt + 1
                    # 每次重试时，建议清除可能存在的上一次的 generation_id
                    execution_context.pop("generation_id", None)

                stream = self.generate_reply_stream(
                    role_data=role_data,
                    history=history,
                    user_input=user_input,
                    timeout=timeout,
                    session_context_source=session_context_source,
                    caller=caller,
                    model_name=model_env,
                    execution_context=execution_context,
                    apply_enhancement=apply_enhancement,
                    model_mode=model_mode
                )

                # 追踪累积字符数，以实现"前5个字符"的Latency记录（与 Bot 侧体验指标对齐）
                accumulated_chars_count = 0
                metric_recorded = False
                METRIC_CHAR_THRESHOLD = 5

                def _track_chunk_and_record_metric(chunk_text: str) -> None:
                    nonlocal accumulated_chars_count, metric_recorded
                    
                    if metric_recorded:
                        return

                    # 累加字符
                    accumulated_chars_count += len(chunk_text)
                    
                    # 如果满足条件（字符数>=阈值），则记录指标
                    if accumulated_chars_count >= METRIC_CHAR_THRESHOLD:
                        # ⏱️ T1: 记录 AI "首响"(前5字符)耗时
                        latency = time.time() - ai_req_start
                        AI_FIRST_TOKEN_LATENCY.labels(provider=provider_display_name, model=model_env or "unknown").observe(latency)
                        metric_recorded = True
                
                # 定义接收时长数据的回调
                def _on_duration_calculated(duration: float):
                    # 同步到外部容器
                    if execution_context is not None:
                        execution_context["full_response_latency"] = duration
                    print(f"⏱️ 完整生成耗时: {duration:.2f}s")
                
                # 使用全能包装器 _stream_managed 代替原有的逻辑
                async for chunk in self._stream_managed(
                    generator=stream,
                    first_chunk_timeout=first_chunk_timeout,
                    inter_chunk_timeout=self.stream_inter_chunk_timeout,
                    total_timeout=self.stream_total_timeout,
                    on_chunk_received=_track_chunk_and_record_metric,
                    provider_name=provider_display_name,
                    on_duration_calculated=_on_duration_calculated
                ):
                    yield chunk

                print(f"✅ AI生成成功（第{attempt + 1}次尝试，提供方: {provider_display_name}）")
                
                return

            except Exception as e:
                # 🔴 T0: 记录 AI 调用失败
                AI_PROVIDER_CALLS_FAILED_TOTAL.labels(provider=provider_display_name, error_type=type(e).__name__).inc()
                
                print(f"❌ AI生成失败（第{attempt + 1}次尝试）: {e}")

                if attempt == total_attempts - 1:
                    print(f"💔 所有重试均失败，返回兜底话术")
                    yield "抱歉，回复出现了问题，后台正在加紧修复，请耐心等待"
                    return
                else:
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
        优先 DeepSeek，其次 Gemini，其次 Novel、Grok；如果都不存在则返回 None
        """
        if self.deepseek_1:
            return self.deepseek_1
        if self.gemini:
            return self.gemini
        if self.novel:
            return self.novel
        if self.grok:
            return self.grok
        return None
    
    # get_last_used_instructions 已废弃（移除）


# ✅ 全局唯一实例（临时占位，实际使用时应通过容器获取）
# 在应用启动时，应该通过容器创建并替换这个实例
ai_completion_port = None  # 将在容器中初始化
