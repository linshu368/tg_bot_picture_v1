# stream_message_service.py - 流式消息处理服务（应用核心层）
import time
import json
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from telegram import Update
import re
from src.infrastructure.monitoring.metrics import (
    BOT_FIRST_RESPONSE_LATENCY,
    BOT_FULL_RESPONSE_LATENCY,
    BOT_RESPONSE_SUCCESS_TOTAL,
    BOT_RESPONSE_FAILURE_TOTAL
)

# 统一的系统级兜底错误提示
FALLBACK_ERROR_MESSAGE = "抱歉，回复出现了问题，后台正在加紧修复，请耐心等待"

# 去除形如 <...> 的标签（HTML/样式标记等）
_TAG_PATTERN = re.compile(r"<[^>]*>")

class StreamMessageService:
    """
    流式消息处理服务 - 应用核心层
    
    职责：
    1. 编排流式消息处理的业务流程
    2. 控制流式更新的节奏和粒度
    3. 协调各个领域服务
    4. 处理错误和降级策略
    """
    
    def __init__(self, role_service=None):
        """
        初始化流式消息服务
        
        Args:
            role_service: 角色服务实例（通过依赖注入）
        """
        self.logger = logging.getLogger(__name__)
        self.role_service = role_service

    def _safe_text_for_telegram(self, text: str) -> str:
        """Sanitize outgoing text:
        1) remove all <...> tags; 2) drop unencodable characters for Telegram.
        """
        try:
            if text is None:
                return ""
            # 正则清洗：去掉 <...> 结构
            cleaned = _TAG_PATTERN.sub("", str(text))
            # 编码安全：忽略不可编码字符
            return cleaned.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
        except Exception:
            return ""
    
    async def handle_stream_message(self, update: Update, user_id: str, content: str, ui_handler=None, start_time: Optional[float] = None) -> None:
        """
        处理流式回复消息的主要业务流程
        🆕 增强异常处理，确保用户状态正确释放
        
        Args:
            update: Telegram Update 对象
            user_id: 用户ID
            content: 消息内容
            ui_handler: UI处理器（用于构建回复键盘）
            start_time: 消息开始处理的时间戳 (T1指标用)
            
        Raises:
            Exception: 重新抛出异常，让调用方（TextBot）处理状态释放
        """
        initial_msg = None
        
        try:
            # 1. 发送初始消息
            initial_msg = await update.message.reply_text("✍️输入中...")
            self.logger.info(f"🚀 开始处理用户 {user_id} 的流式消息")
            
            # 2. 获取会话和角色信息
            session_info = await self._get_session_and_role(user_id, content)
            
            if session_info["code"] != 0:
                # 处理错误情况（非业务预期内的系统错误需兜底）
                # 业务错误码通常是 4002(过长), 4003(限额)，这些不需要兜底话术
                # 但如果是其他未知错误，则视为工程侧异常
                if session_info["code"] not in [4002, 4003]:
                    BOT_RESPONSE_FAILURE_TOTAL.labels(error_type=f"session_error_{session_info['code']}").inc()
                    await initial_msg.edit_text(FALLBACK_ERROR_MESSAGE)
                else:
                    # 业务预期错误，直接显示原消息
                    error_text = f"❌ {session_info['message']}"
                await initial_msg.edit_text(error_text)
                    
                self.logger.warning(f"⚠️ 用户 {user_id} 会话获取失败: {session_info['message']}")
                return
            
            data = session_info["data"]
            session_id = data["session_id"]
            role_data = data["role_data"]
            history = data["history"]
            context_source = data.get("context_source")
            
            self.logger.info(f"📊 用户 {user_id} 会话信息: session_id={session_id}, history_count={len(history)}")
            
            # 获取用户模型偏好
            model_mode = "immersive"
            try:
                from src.domain.services.session_service_base import session_service
                if session_service and session_service.redis_store:
                    model_mode = await session_service.redis_store.get_user_model_mode(user_id)
            except Exception as e:
                self.logger.debug(f"获取用户模型偏好失败: {e}")

            # 3. 执行精细化流式回复
            await self._execute_granular_stream_reply(
                initial_msg=initial_msg,
                role_data=role_data,
                history=history,
                content=content,
                context_source=context_source,
                session_id=session_id,
                user_message_id=data.get("user_message_id", ""),
                ui_handler=ui_handler,
                start_time=start_time,
                model_mode=model_mode
            )
            
            self.logger.info(f"✅ 用户 {user_id} 流式消息处理完成")
            
            # 🟢 T0 & T1: 记录成功与完整耗时
            if start_time:
                duration = time.time() - start_time
                BOT_FULL_RESPONSE_LATENCY.observe(duration)
            
            role_id_tag = role_data.get("id", "unknown") if role_data else "unknown"
            BOT_RESPONSE_SUCCESS_TOTAL.inc()
                
        except Exception as e:
            # 🆕 详细记录异常信息
            import traceback
            error_details = f"类型: {type(e).__name__}, 消息: {str(e)}, 用户: {user_id}"
            self.logger.error(f"❌ 流式消息处理失败 - {error_details}")
            self.logger.error(f"完整堆栈:\n{traceback.format_exc()}")
            
            # 🆕 尽力向用户显示错误信息
            try:
                BOT_RESPONSE_FAILURE_TOTAL.labels(error_type=type(e).__name__).inc()
                if initial_msg:
                    await initial_msg.edit_text(FALLBACK_ERROR_MESSAGE)
                else:
                    await update.message.reply_text(FALLBACK_ERROR_MESSAGE)
            except Exception as msg_e:
                self.logger.error(f"❌ 发送错误消息也失败: {msg_e}")
            
            # 🆕 重新抛出异常，让TextBot的finally块处理状态释放
            raise

    async def _execute_granular_stream_reply(self, initial_msg, role_data, history, content, 
                                           context_source, session_id, user_message_id, ui_handler, start_time=None, model_mode="immersive"):
        """
        执行精细化的流式回复控制
        """
        from src.domain.services.ai_completion_port import ai_completion_port
        from src.domain.services.message_service import message_service
        
        # 流式控制参数
        accumulated_text = ""
        char_count = 0
        first_chars_threshold = 5  # 前5个字符立即显示
        regular_update_interval = 2.0  # 2秒间隔
        last_update_time = 0
        
        # 阶段标记
        phase = "collecting_first_chars"  # collecting_first_chars -> regular_updates -> completed
        
        self.logger.info(f"🚀 开始精细化流式回复: threshold={first_chars_threshold}, interval={regular_update_interval}s")
        
        # 使用列表来传递引用，确保在整个方法中可访问
        accumulated_text_ref = [accumulated_text]
        phase_ref = [phase]
        last_update_time_ref = [last_update_time]
        first_latency_ref = [None]  # 🆕 用于捕获首响耗时
        
        try:
            # 使用带重试机制的流式生成
            # 用于接收AI端回传的指令使用信息（避免使用全局共享状态）
            execution_context = {}
            
            async for chunk in ai_completion_port.generate_reply_stream_with_retry(
                role_data=role_data,
                history=history,
                user_input=content,
                session_context_source=context_source,
                execution_context=execution_context,
                apply_enhancement=True,
                model_mode=model_mode
            ):
                # 对大块进行字符级分割处理
                await self._process_chunk_with_granular_control(
                    chunk=chunk,
                    accumulated_text_ref=accumulated_text_ref,
                    phase_ref=phase_ref,
                    first_chars_threshold=first_chars_threshold,
                    regular_update_interval=regular_update_interval,
                    last_update_time_ref=last_update_time_ref,
                    initial_msg=initial_msg,
                    start_time=start_time,
                    first_latency_ref=first_latency_ref
                )
            
            # 从引用中获取最终值
            accumulated_text = accumulated_text_ref[0]
            
            # 阶段3：立即最终更新
            if accumulated_text:
                try:
                    # 添加回复键盘
                    reply_markup = None
                    if ui_handler:
                        reply_markup = ui_handler.build_reply_keyboard(
                            session_id=session_id,
                            user_message_id=user_message_id
                        )
                    
                    await initial_msg.edit_text(self._safe_text_for_telegram(accumulated_text), reply_markup=reply_markup)
                    self.logger.info(f"✅ 最终更新完成: {len(accumulated_text)} 字符")
                except Exception as e:
                    self.logger.error(f"最终更新消息失败: {e}")
                
                # 保存完整回复到数据库
                await message_service.save_message(session_id, "assistant", self._safe_text_for_telegram(accumulated_text))
                
                # 🆕 AI生成完成后，使用回调传回的实际使用指令，重新保存用户消息（带指令）
                if message_service.message_repository and hasattr(message_service, 'session_service'):
                    try:
                        system_instructions = execution_context.get("system_instructions")
                        ongoing_instructions = execution_context.get("ongoing_instructions")
                        # 🆕 新字段写入逻辑：确定本轮实际使用的 instructions（非简单拼接，按真实使用选择其一）
                        instruction_type = execution_context.get("instruction_type")
                        instructions = execution_context.get("instructions")
                        if instructions is None:
                            # 兼容旧回调，仅在未显式提供 instructions 时按类型选择
                            if instruction_type == "system":
                                instructions = system_instructions
                            elif instruction_type == "ongoing":
                                instructions = ongoing_instructions
                            else:
                                # 未识别类型则择优取其一
                                instructions = system_instructions or ongoing_instructions
                        
                        # 🆕 新字段写入逻辑：模型名称
                        model_name = execution_context.get("model_name") or execution_context.get("model")
                        
                        # 🆕 新字段写入逻辑：history（100%复现）
                        # 优先使用回调给到的 final_messages；否则按当前逻辑构造
                        final_messages = execution_context.get("final_messages")
                        if not isinstance(final_messages, list) or not final_messages:
                            # 构造尽量接近的 messages（兜底）
                            constructed = []
                            if isinstance(role_data, dict) and role_data.get("system_prompt"):
                                constructed.append({"role": "system", "content": role_data.get("system_prompt")})
                            if context_source != "snapshot" and isinstance(role_data, dict) and role_data.get("history"):
                                constructed.extend(role_data.get("history") or [])
                            constructed.extend(history or [])
                            final_messages = constructed
                        # 仅将 final_messages 作为 JSON 字符串写入 history，model_name 单独写入字段
                        try:
                            history_json_str = json.dumps(final_messages, ensure_ascii=False)
                        except Exception:
                            # 兜底序列化
                            history_json_str = json.dumps({"fallback": True}, ensure_ascii=False)
                        
                        # 🆕 新字段写入逻辑：round（以 session 维度的用户消息序号计算）
                        try:
                            # 从 DB 获取已存储的轮次（不含当前），+1 即为当前轮次
                            # 这样即使 Redis 历史被截断，也能得到正确的总轮数（前提是 Repo 实现了对应方法）
                            stored_count = await message_service.get_session_user_turn_count(session_id)
                            round_num = stored_count + 1
                        except Exception:
                            round_num = None
                        
                        # 🆕 新字段写入逻辑：完整响应耗时
                        full_response_latency = execution_context.get("full_response_latency")
                        
                        # 🆕 新字段写入逻辑：首响耗时与尝试次数
                        first_response_latency = first_latency_ref[0]
                        attempt_count = execution_context.get("attempt_count", 1)
                        
                        if system_instructions or ongoing_instructions:
                            # 获取session_id中的user_id和role_id
                            try:
                                session_info = await message_service._get_session_info(session_id)
                                if session_info:
                                    user_id = session_info.get("user_id")
                                    role_id = session_info.get("role_id")
                                    
                                    if user_id:
                                        # 异步保存用户消息（不阻塞主流程）
                                        message_service.message_repository.save_user_message_with_real_instructions_async(
                                            user_id=str(user_id),
                                            role_id=str(role_id) if role_id else None,
                                            session_id=session_id,
                                            # 🆕 新字段写入逻辑
                                            instructions=instructions,
                                            bot_reply=self._safe_text_for_telegram(accumulated_text),
                                            history=history_json_str,
                                            model_name=model_name,
                                            user_input=content,
                                            round=round_num,
                                            full_response_latency=full_response_latency,
                                            first_response_latency=first_response_latency,  # 🆕 传入首响耗时
                                            retry_attempt=attempt_count                     # 🆕 传入尝试次数
                                        )
                                        self.logger.info(f"🔄 已异步保存带指令的用户消息: session_id={session_id}, duration={full_response_latency}, first_latency={first_response_latency}, attempt={attempt_count}")
                            except Exception as inner_e:
                                self.logger.error(f"❌ 获取会话信息失败: {inner_e}")
                        
                        # 🆕 OpenRouter 统计信息获取 (仅打印验证)
                        generation_id = execution_context.get("generation_id")
                        api_key = execution_context.get("api_key")
                        if generation_id and api_key:
                            import asyncio
                            self.logger.info(f"🎫 捕获到 OpenRouter generation_id: {generation_id}，启动后台查询任务...")
                            asyncio.create_task(ai_completion_port.fetch_openrouter_stats(generation_id, api_key))
                            
                    except Exception as e:
                        self.logger.error(f"❌ 保存带指令的用户消息失败: {e}")
            else:
                # 流式处理完成但无内容，记录详细错误信息
                self.logger.error(f"❌ 流式处理完成但无内容: session_id={session_id}, user_message_id={user_message_id}")
                self.logger.error(f"❌ 原始用户输入: {content}")
                self.logger.error(f"❌ 角色数据: role_id={role_data.get('id', 'unknown') if role_data else 'None'}")
                
                BOT_RESPONSE_FAILURE_TOTAL.labels(error_type="EmptyResponse").inc()
                await initial_msg.edit_text(FALLBACK_ERROR_MESSAGE)
                
        except Exception as e:
            # 详细记录错误信息
            import traceback
            error_details = f"类型: {type(e).__name__}, 消息: {str(e)}"
            self.logger.error(f"流式生成过程失败 - {error_details}")
            self.logger.error(f"完整堆栈:\n{traceback.format_exc()}")
            
            # 向用户显示更详细的错误信息
            BOT_RESPONSE_FAILURE_TOTAL.labels(error_type=type(e).__name__).inc()
            await initial_msg.edit_text(FALLBACK_ERROR_MESSAGE)

    async def _process_chunk_with_granular_control(self, chunk, accumulated_text_ref, phase_ref, 
                                                 first_chars_threshold, regular_update_interval, 
                                                 last_update_time_ref, initial_msg, start_time=None, first_latency_ref=None):
        """
        对大块进行字符级分割处理，实现精细化控制
        
        Args:
            chunk: 从AI接收到的文本块
            accumulated_text_ref: 累积文本的引用列表
            phase_ref: 阶段标记的引用列表
            first_latency_ref: 首响耗时引用列表
            其他参数: 控制参数
        """
        import time
        
        # 获取当前状态
        accumulated_text = accumulated_text_ref[0]
        phase = phase_ref[0]
        last_update_time = last_update_time_ref[0]
        
        # 逐字符处理（对于中文和英文都适用）
        for char in chunk:
            accumulated_text += char
            char_count = len(accumulated_text)
            current_time = time.time()
            
            if phase == "collecting_first_chars":
                # 阶段1：收集前N个字符后立即更新
                if char_count >= first_chars_threshold:
                    try:
                        await initial_msg.edit_text(self._safe_text_for_telegram(accumulated_text))
                        phase = "regular_updates"
                        
                        # ⏱️ T1: 记录首响耗时（用户体验）
                        if start_time:
                            latency = time.time() - start_time
                            BOT_FIRST_RESPONSE_LATENCY.observe(latency)
                            if first_latency_ref is not None:
                                first_latency_ref[0] = latency  # 🆕 记录首响值
                            
                        last_update_time = current_time
                        self.logger.info(f"📤 首段更新完成: {char_count} 字符")
                    except Exception as e:
                        self.logger.debug(f"首段更新失败: {e}")
                        
            elif phase == "regular_updates":
                # 阶段2：每2秒更新一次
                if current_time - last_update_time >= regular_update_interval:
                    try:
                        await initial_msg.edit_text(self._safe_text_for_telegram(accumulated_text))
                        last_update_time = current_time
                        self.logger.info(f"📤 定时更新: {char_count} 字符")
                    except Exception as e:
                        self.logger.debug(f"定时更新失败: {e}")
        
        # 更新引用
        accumulated_text_ref[0] = accumulated_text
        phase_ref[0] = phase
        last_update_time_ref[0] = last_update_time

    async def _get_session_and_role(self, user_id: str, content: str) -> dict:
        """获取会话和角色信息（从领域服务获取）"""
        from src.domain.services.session_service_base import session_service
        from src.domain.services.message_service import message_service
        
        # 简单校验
        if len(content) > 10000:
            return {"code": 4002, "message": "消息过长，最大长度 10000", "data": None}

        # 检查每日消息限制
        limit_check = await message_service.check_daily_limit(user_id)
        if not limit_check["allowed"]:
            self.logger.warning(f"🚫 用户超出每日消息限制: user_id={user_id}, current_count={limit_check['current_count']}, limit={limit_check['limit']}")
            
            # 获取或创建会话（用于保存限制提示消息）
            session = await session_service.get_or_create_session(user_id)
            session_id = session["session_id"]
            
            # 保存用户原始消息
            user_message_id = await message_service.save_message(session_id, "user", content)
            
            # 保存Bot的限制提示回复
            limit_message = "您今日的免费体验次数已用完，明日0点重置。感谢您的使用！"
            bot_message_id = await message_service.save_message(session_id, "assistant", limit_message)
            
            self.logger.info(f"💾 已保存限制提示消息: user_message_id={user_message_id}, bot_message_id={bot_message_id}")
            
            return {
                "code": 4003, 
                "message": limit_message, 
                "data": None
            }

        # 获取或创建会话
        session = await session_service.get_or_create_session(user_id)
        session_id = session["session_id"]
        
        # 获取会话的角色ID
        current_role_id = session.get("role_id")
        
        # 兜底机制：如果会话没有角色ID，设置默认角色
        if not current_role_id:
            self.logger.warning(f"⚠️ 会话无角色ID，触发兜底机制: user_id={user_id}, session_id={session_id}")
            default_role_id = '46'
            await session_service.set_session_role_id(session_id, default_role_id)
            current_role_id = default_role_id
        
        # 获取角色数据（使用注入的 role_service）
        role_data = self.role_service.get_role_by_id(current_role_id)
        if not role_data:
            # 二次降级：角色ID对应的角色不存在
            self.logger.warning(f"⚠️ 角色不存在: role_id={current_role_id}，降级到默认角色")
            default_role_id = '46'
            role_data = self.role_service.get_role_by_id(default_role_id)
            if role_data:
                await session_service.set_session_role_id(session_id, default_role_id)
        
        if not role_data:
            self.logger.error(f"❌ 角色配置错误: 默认角色也不存在")
            return {"code": 4001, "message": "角色配置错误", "data": None}

   

        # 保存用户原始消息并获取历史
        user_message_id = await message_service.save_message(session_id, "user", content)
        history = await message_service.get_history(session_id)
        # 清洗历史消息内容，确保与展示一致
        cleaned_history = []
        for msg in history or []:
            try:
                msg_copy = dict(msg) if isinstance(msg, dict) else msg
                if isinstance(msg_copy, dict) and "content" in msg_copy:
                    # 仅清洗 bot 输出，用户输入保持原样
                    if msg_copy.get("role") == "assistant":
                        msg_copy["content"] = self._safe_text_for_telegram(msg_copy.get("content"))
                cleaned_history.append(msg_copy)
            except Exception:
                cleaned_history.append(msg)
        history = cleaned_history

        
        # 获取会话上下文来源
        context_source = session.get("context_source") if session else None
        
        return {
            "code": 0,
            "message": "success",
            "data": {
                "session_id": session_id,
                "user_message_id": user_message_id,
                "role_data": role_data,
                "history": history,
                "context_source": context_source
            }
        }
    
stream_message_service = None  # 将在容器中初始化
