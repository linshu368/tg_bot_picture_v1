import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import uuid
from telegram.ext import ContextTypes
from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
from ...ui_handler import UIHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

class TextBotCallbackHandler(BaseCallbackHandler):
    """文字 Bot 的回调处理器"""

    def __init__(self, bot_instance):
        super().__init__(bot_instance)
        self.logger = logging.getLogger(__name__)
        
        # 从 bot_instance 获取服务依赖（通过依赖注入）
        self.session_service = bot_instance.session_service
        self.role_service = bot_instance.role_service
        
        # ✅ 从全局模块获取已初始化的服务（在 initialize_global_services 后可用）
        from src.domain.services.message_service import message_service
        from src.domain.services.ai_completion_port import ai_completion_port
        self.message_service = message_service
        self.ai_completion_port = ai_completion_port
        self.snapshot_service = bot_instance.snapshot_service

    def get_callback_handlers(self):
        """定义本 Bot 支持的回调动作"""
        handlers = {
            "regenerate": self._on_regenerate,
            "new_session": self._on_new_session,
            "save_snapshot": self._on_save_snapshot,
            "save_snapshot_direct": self._on_save_snapshot_direct,
            "delete_snapshot": self._on_delete_snapshot,
            "open_snapshot": self._on_open_snapshot,
        }
        self.logger.info(f"✅ 注册回调 handlers: {list(handlers.keys())}")
        return handlers

    # -------------------------
    # 工具方法
    # -------------------------
    def _get_role_predefined_message(self, role: dict) -> str:
        """
        从角色数据中提取预置消息
        
        Args:
            role: 角色数据字典
            
        Returns:
            预置消息内容，如果不存在则返回默认消息
        """
        # 从 history 字段的第一条消息获取预置对话
        history = role.get("history", [])
        if history and len(history) > 0:
            first_message = history[0]
            if isinstance(first_message, dict) and first_message.get("role") == "assistant":
                return first_message.get("content", "你好！")
        
        # 降级兜底
        return "你好！"
    
    async def _update_message(self, query, reply_text: str, session_id: str = "", user_message_id: str = ""):
        await query.edit_message_text(
            text=reply_text,
            reply_markup=UIHandler.build_reply_keyboard(session_id, user_message_id),
        )

    # -------------------------
    # 回调方法
    # -------------------------
    @robust_callback_handler
    async def _on_regenerate(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 重新生成 按钮 - 流式重新生成"""
        self.logger.info(f"📥 收到回调 action=regenerate data={query.data} user_id={query.from_user.id}")
        user_id = str(query.from_user.id)
        raw_data = query.data

        # 从 callback_data 中解析
        parts = raw_data.split(":")
        action = parts[0]
        session_id = parts[1] if len(parts) > 1 else None
        user_message_id = parts[2] if len(parts) > 2 else None

        self.logger.info(
            f"📥 回调 regenerate: user_id={user_id}, session_id={session_id}, user_message_id={user_message_id}"
        )

        try:
            # 1. 检查每日消息限制（重新生成也算作一次AI调用）
            limit_check = await self.message_service.check_daily_limit(user_id)
            if not limit_check["allowed"]:
                self.logger.warning(f"🚫 用户重新生成超出每日限制: user_id={user_id}, current_count={limit_check['current_count']}, limit={limit_check['limit']}")
                
                # 保存Bot的限制提示回复到数据库
                limit_message = "您今日的免费体验次数已用完，明日0点重置。感谢您的使用！"
                bot_message_id = self.message_service.save_message(session_id, "assistant", limit_message)
                self.logger.info(f"💾 已保存重新生成限制提示消息: bot_message_id={bot_message_id}")
                
                await query.answer(limit_message, show_alert=True)
                return
            
            # 2. 从会话获取绑定的角色ID
            role_id = await self.session_service.get_session_role_id(session_id)
            self.logger.info(f"📥 获取会话角色: session_id={session_id}, role_id={role_id}")
            
            # 3. 获取角色数据，如果角色不存在则使用默认角色
            if role_id:
                role_data = self.role_service.get_role_by_id(role_id)
            else:
                role_data = None
                
            if not role_data:
                # 降级到默认角色 (从bot实例获取默认角色ID)
                default_role_id = getattr(self.bot, 'default_role_id', '46')
                role_data = self.role_service.get_role_by_id(default_role_id)
                self.logger.warning(f"⚠️ 角色不存在，使用默认角色: role_id={role_id} -> default={default_role_id}")
            
            if not role_data:
                await query.answer("❌ 角色配置错误，请联系管理员")
                return
                
            self.logger.info(f"✅ 使用角色: {role_data.get('name', 'Unknown')} (ID: {role_data.get('role_id', 'Unknown')})")
            
            # 4. 获取会话上下文来源（判断是否为快照会话）
            session_obj = await self.session_service.get_session(session_id)
            context_source = session_obj.get("context_source") if session_obj else None
            
            # 5. 禁用原消息按钮
            await query.edit_message_reply_markup(reply_markup=None)
            
            # 6. 截断历史记录并获取用户消息内容
            user_input = self.message_service.truncate_history_after_message(session_id, user_message_id)
            if not user_input:
                await query.message.reply_text("❌ 无法找到指定的用户消息")
                return
            
            # 7. 发送新的初始消息
            initial_msg = await query.message.reply_text("✍️输入中...")
            
            # 8. 执行流式重新生成
            await self._execute_regenerate_stream_reply(
                initial_msg=initial_msg,
                role_data=role_data,
                session_id=session_id,
                user_message_id=user_message_id,
                user_input=user_input,
                context_source=context_source
            )
            
        except Exception as e:
            self.logger.error(f"❌ 重新生成失败: {e}")
            try:
                await query.answer("❌ 重新生成失败，请重试")
            except:
                pass

    async def _execute_regenerate_stream_reply(self, initial_msg, role_data, session_id, 
                                             user_message_id, user_input, context_source):
        """
        执行重新生成专用的流式处理
        复用StreamMessageService的核心逻辑
        """
        from src.domain.services.ai_completion_port import ai_completion_port
        
        # 获取历史记录（已截断）- 使用实例的message_service
        history = self.message_service.get_history(session_id)
        
        # 流式控制参数（与StreamMessageService保持一致）
        accumulated_text = ""
        char_count = 0
        first_chars_threshold = 5  # 前5个字符立即显示
        regular_update_interval = 2.0  # 2秒间隔
        last_update_time = 0
        
        # 阶段标记
        phase = "collecting_first_chars"  # collecting_first_chars -> regular_updates -> completed
        
        self.logger.info(f"🚀 开始重新生成流式回复: threshold={first_chars_threshold}, interval={regular_update_interval}s")
        
        # 使用列表来传递引用，确保在整个方法中可访问
        accumulated_text_ref = [accumulated_text]
        phase_ref = [phase]
        last_update_time_ref = [last_update_time]
        
        try:
            # 使用带重试机制的流式生成
            async for chunk in ai_completion_port.generate_reply_stream_with_retry(
                role_data=role_data,
                history=history,
                user_input=user_input,
                session_context_source=context_source
            ):
                # 对大块进行字符级分割处理（复用StreamMessageService的逻辑）
                await self._process_chunk_with_granular_control(
                    chunk=chunk,
                    accumulated_text_ref=accumulated_text_ref,
                    phase_ref=phase_ref,
                    first_chars_threshold=first_chars_threshold,
                    regular_update_interval=regular_update_interval,
                    last_update_time_ref=last_update_time_ref,
                    initial_msg=initial_msg
                )
            
            # 从引用中获取最终值
            accumulated_text = accumulated_text_ref[0]
            
            # 阶段3：立即最终更新
            if accumulated_text:
                try:
                    # 添加回复键盘
                    reply_markup = UIHandler.build_reply_keyboard(
                        session_id=session_id,
                        user_message_id=user_message_id
                    )
                    
                    await initial_msg.edit_text(self._safe_text_for_telegram(accumulated_text), reply_markup=reply_markup)
                    self.logger.info(f"✅ 重新生成最终更新完成: {len(accumulated_text)} 字符")
                except Exception as e:
                    self.logger.error(f"重新生成最终更新消息失败: {e}")
                
                # 保存完整回复到数据库
                self.message_service.save_message(session_id, "assistant", accumulated_text)
                
                # 🆕 AI重新生成完成后，获取实际使用的指令并保存用户消息（带指令）
                if self.message_service.message_repository and hasattr(self.message_service, 'session_service'):
                    try:
                        from src.domain.services.ai_completion_port import ai_completion_port
                        used_instructions = ai_completion_port.get_last_used_instructions()
                        system_instructions = used_instructions.get("system_instructions")
                        ongoing_instructions = used_instructions.get("ongoing_instructions")
                        
                        if system_instructions or ongoing_instructions:
                            # 获取session_id中的user_id和role_id
                            try:
                                session_info = await self.message_service._get_session_info(session_id)
                                if session_info:
                                    user_id = session_info.get("user_id")
                                    role_id = session_info.get("role_id")
                                    
                                    if user_id:
                                        # 异步保存带指令的用户消息（不阻塞主流程）
                                        self.message_service.message_repository.save_user_message_with_real_instructions_async(
                                            user_id=str(user_id),
                                            role_id=str(role_id) if role_id else None,
                                            session_id=session_id,
                                            message=user_input,
                                            system_instructions=system_instructions,
                                            ongoing_instructions=ongoing_instructions
                                        )
                                        self.logger.info(f"🔄 已异步保存带指令的用户消息(重新生成): session_id={session_id}")
                            except Exception as inner_e:
                                self.logger.error(f"❌ 获取会话信息失败(重新生成): {inner_e}")
                    except Exception as e:
                        self.logger.error(f"❌ 保存带指令的用户消息失败(重新生成): {e}")
            else:
                # 重新生成完成但无内容，记录详细错误信息
                self.logger.error(f"❌ 重新生成完成但无内容: session_id={session_id}, user_message_id={user_message_id}")
                self.logger.error(f"❌ 原始用户输入: {user_input}")
                self.logger.error(f"❌ 角色数据: role_id={role_data.get('id', 'unknown') if role_data else 'None'}")
                self.logger.error(f"❌ 上下文来源: {context_source}")
                # 向用户显示统一的友好错误信息
                await initial_msg.edit_text("抱歉，回复出现了问题，后台正在加紧修复，请耐心等待")
                
        except Exception as e:
            # 详细记录错误信息
            import traceback
            error_details = f"类型: {type(e).__name__}, 消息: {str(e)}"
            self.logger.error(f"重新生成流式处理失败 - {error_details}")
            self.logger.error(f"完整堆栈:\n{traceback.format_exc()}")
            
            # 向用户显示更详细的错误信息
            error_msg = str(e) if str(e) else f"{type(e).__name__} (无详细信息)"
            await initial_msg.edit_text(f"❌ 重新生成失败: {error_msg}")

    async def _process_chunk_with_granular_control(self, chunk, accumulated_text_ref, phase_ref, 
                                                 first_chars_threshold, regular_update_interval, 
                                                 last_update_time_ref, initial_msg):
        """
        对大块进行字符级分割处理，实现精细化控制
        复用StreamMessageService的逻辑
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
                        last_update_time = current_time
                        self.logger.info(f"📤 重新生成首段更新完成: {char_count} 字符")
                    except Exception as e:
                        self.logger.debug(f"重新生成首段更新失败: {e}")
                        
            elif phase == "regular_updates":
                # 阶段2：每2秒更新一次
                if current_time - last_update_time >= regular_update_interval:
                    try:
                        await initial_msg.edit_text(self._safe_text_for_telegram(accumulated_text))
                        last_update_time = current_time
                        self.logger.info(f"📤 重新生成定时更新: {char_count} 字符")
                    except Exception as e:
                        self.logger.debug(f"重新生成定时更新失败: {e}")
        
        # 更新引用
        accumulated_text_ref[0] = accumulated_text
        phase_ref[0] = phase
        last_update_time_ref[0] = last_update_time

    def _safe_text_for_telegram(self, text: str) -> str:
        """Sanitize text to avoid Unicode surrogate encoding errors when sending to Telegram."""
        try:
            if text is None:
                return ""
            return text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
        except Exception:
            return ""

    @robust_callback_handler
    async def _on_new_session(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 新的对话 按钮"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        
        # 从 callback_data 中解析当前session_id
        parts = raw_data.split(":")
        current_session_id = parts[1] if len(parts) > 1 else None
        
        self.logger.info(f"📥 新对话请求: user_id={user_id}, current_session_id={current_session_id}")
        
        try:
            # 1. 获取当前会话的角色ID，保持角色不变
            current_role_id = await self.session_service.get_session_role_id(current_session_id)
            if not current_role_id:
                # 如果当前会话没有角色，使用默认角色
                current_role_id = getattr(self.bot, 'default_role_id', '46')
                self.logger.info(f"📥 当前会话无角色，使用默认角色: {current_role_id}")
            
            # 2. 创建新会话，保持相同角色
            new_session = await self.session_service.new_session(user_id, current_role_id)
            new_session_id = new_session["session_id"]
            
            self.logger.info(f"✅ 创建新对话: session_id={new_session_id}, role_id={current_role_id}")
            
            # 3. 获取角色信息，发送角色欢迎语
            role_data = self.role_service.get_role_by_id(current_role_id)
            if role_data:
                # 从 history 字段的第一条消息获取预置对话
                predefined_msg = self._get_role_predefined_message(role_data)
                welcome_msg = f"🆕 已开启新对话\n\n💫 当前角色：{role_data.get('name', '未知角色')}\n\n{predefined_msg}"
            else:
                welcome_msg = "🆕 已开启新对话"
            
            await self._update_message(query, welcome_msg, session_id=new_session_id, user_message_id="")
            
        except Exception as e:
            self.logger.error(f"❌ 创建新对话失败: {e}")
            await self._update_message(query, "❌ 创建新对话失败，请重试", session_id="", user_message_id="")

    @robust_callback_handler
    async def _on_save_snapshot(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 保存对话 按钮"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        parts = raw_data.split(":")
        session_id = parts[1] if len(parts) > 1 else None
        self.logger.info(f"📥 保存对话请求: user_id={user_id}, session_id={session_id}")

        if not session_id:
            await query.answer("❌ 无效的会话")
            return

        try:
            # 标记命名待输入（进程内状态）
            setattr(self.bot, "pending_snapshot", getattr(self.bot, "pending_snapshot", {}))
            self.bot.pending_snapshot[user_id] = {"session_id": session_id}

            # 提示用户输入名称，附带“直接保存（未命名）”按钮
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("直接保存", callback_data=f"save_snapshot_direct:{session_id}")]])
            await query.message.reply_text(
                "请发送本次历史聊天的名称，或点击下方按钮直接保存",
                reply_markup=keyboard
            )
            await query.answer()
        except Exception as e:
            self.logger.error(f"❌ 保存对话失败: {e}")
            await query.answer("❌ 保存失败，请重试")

    @robust_callback_handler
    async def _on_save_snapshot_direct(self, query, context: ContextTypes.DEFAULT_TYPE):
        """直接保存"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        parts = raw_data.split(":")
        session_id = parts[1] if len(parts) > 1 else None
        if not session_id:
            await query.answer("❌ 无效的会话")
            return
        try:
            snapshot_id = await self.snapshot_service.save_snapshot(user_id=user_id, session_id=session_id, user_title="未命名")
            self.logger.info(f"✅ 快照已保存(直接): snapshot_id={snapshot_id}")
            # 清理可能存在的命名态
            if getattr(self.bot, "pending_snapshot", None):
                self.bot.pending_snapshot.pop(user_id, None)
            await query.answer()
            await query.message.reply_text("✅ 保存成功，可在主菜单点击「🗂 历史聊天」查看保存结果")
        except Exception as e:
            self.logger.error(f"❌ 直接保存失败: {e}")
            await query.answer("❌ 保存失败，请重试")

    @robust_callback_handler
    async def _on_delete_snapshot(self, query, context: ContextTypes.DEFAULT_TYPE):
        """删除记忆（硬删除）"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        parts = raw_data.split(":")
        snapshot_id = parts[1] if len(parts) > 1 else None
        if not snapshot_id:
            await query.answer("❌ 无效的快照")
            return
        try:
            ok = await self.snapshot_service.delete_snapshot(user_id=user_id, snapshot_id=snapshot_id)
            if ok:
                await query.edit_message_text("🗑️ 已删除该记忆\n可在主菜单点击「🗂 历史聊天」查看当前记录")
                await query.answer()
            else:
                await query.answer("❌ 快照不存在或无权访问")
        except Exception as e:
            self.logger.error(f"❌ 删除记忆失败: {e}")
            await query.answer("❌ 删除失败，请重试")

    @robust_callback_handler
    async def _on_open_snapshot(self, query, context: ContextTypes.DEFAULT_TYPE):
        """基于快照开启新对话"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        parts = raw_data.split(":")
        snapshot_id = parts[1] if len(parts) > 1 else None
        if not snapshot_id:
            await query.answer("❌ 无效的快照")
            return

        try:
            # 1) 读取快照并校验归属
            snap = await self.snapshot_service.get_snapshot(user_id=user_id, snapshot_id=snapshot_id)
            if not snap:
                await query.answer("❌ 快照不存在或无权访问")
                return

            role_id = snap.get("role_id") or getattr(self.bot, 'default_role_id', '46')

            # 2) 创建新会话并绑定角色
            new_session = await self.session_service.new_session(user_id, role_id)
            new_session_id = new_session["session_id"]

            # 3) 预置历史消息（快照中的 messages 已包含预置与实际）
            # 🔄 只在内存中恢复历史，不保存到数据库（避免重复记录）
            messages = snap.get("messages", [])
            restored_count = self.message_service.restore_history_to_memory(new_session_id, messages)

            # 4) 写入会话上下文覆写（MVP：直接附加到会话字典）
            session_obj = await self.session_service.get_session(new_session_id)
            if session_obj is not None:
                session_obj["model"] = snap.get("model", "")
                session_obj["system_prompt"] = snap.get("system_prompt", "")
                session_obj["context_source"] = "snapshot"

            # 5) 用户反馈
            role_data = self.role_service.get_role_by_id(role_id)
            role_name = role_data.get('name', '未知角色') if role_data else '未知角色'
            welcome_msg = f"🆕 已基于快照开启新对话\n\n💫 当前角色：{role_name}"
            await self._update_message(query, welcome_msg, session_id=new_session_id, user_message_id="")
        except Exception as e:
            self.logger.error(f"❌ 打开快照失败: {e}")
            await self._update_message(query, "❌ 创建新对话失败，请重试", session_id="", user_message_id="")