# stream_message_service.py - 流式消息处理服务（应用核心层）
import time
import logging
from typing import Any, Dict, Optional
from telegram import Update

class StreamMessageService:
    """
    流式消息处理服务 - 应用核心层
    
    职责：
    1. 编排流式消息处理的业务流程
    2. 控制流式更新的节奏和粒度
    3. 协调各个领域服务
    4. 处理错误和降级策略
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def handle_stream_message(self, update: Update, user_id: str, content: str, ui_handler=None) -> None:
        """
        处理流式回复消息的主要业务流程
        
        Args:
            update: Telegram Update 对象
            user_id: 用户ID
            content: 消息内容
            ui_handler: UI处理器（用于构建回复键盘）
        """
        try:
            # 1. 发送初始消息
            initial_msg = await update.message.reply_text("✍️输入中...")
            
            # 2. 获取会话和角色信息
            session_info = await self._get_session_and_role(user_id, content)
            
            if session_info["code"] != 0:
                # 处理错误情况
                error_text = f"❌ 出错: {session_info['message']} (code={session_info['code']})"
                await initial_msg.edit_text(error_text)
                return
            
            data = session_info["data"]
            session_id = data["session_id"]
            role_data = data["role_data"]
            history = data["history"]
            context_source = data.get("context_source")
            
            # 3. 执行精细化流式回复
            await self._execute_granular_stream_reply(
                initial_msg=initial_msg,
                role_data=role_data,
                history=history,
                content=content,
                context_source=context_source,
                session_id=session_id,
                user_message_id=data.get("user_message_id", ""),
                ui_handler=ui_handler
            )
                
        except Exception as e:
            self.logger.error(f"流式消息处理失败: {e}")
            try:
                await initial_msg.edit_text(f"❌ 处理失败: {str(e)}")
            except:
                await update.message.reply_text(f"❌ 处理失败: {str(e)}")

    async def _execute_granular_stream_reply(self, initial_msg, role_data, history, content, 
                                           context_source, session_id, user_message_id, ui_handler):
        """
        执行精细化的流式回复控制
        
        流式回复节奏：
        1. 立即响应："✍️输入中..." (已完成)
        2. 快速首段：收到前5个字符后立即显示
        3. 定时更新：之后每2秒更新一次
        4. 立即完成：生成完成后立即显示最终结果
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
        
        try:
            async for chunk in ai_completion_port.generate_reply_stream(
                role_data=role_data,
                history=history,
                user_input=content,
                session_context_source=context_source
            ):
                # 对大块进行字符级分割处理
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
                    reply_markup = None
                    if ui_handler:
                        reply_markup = ui_handler.build_reply_keyboard(
                            session_id=session_id,
                            user_message_id=user_message_id
                        )
                    
                    await initial_msg.edit_text(accumulated_text, reply_markup=reply_markup)
                    self.logger.info(f"✅ 最终更新完成: {len(accumulated_text)} 字符")
                except Exception as e:
                    self.logger.error(f"最终更新消息失败: {e}")
                
                # 保存完整回复到数据库
                message_service.save_message(session_id, "assistant", accumulated_text)
            else:
                await initial_msg.edit_text("❌ 生成回复失败，请重试")
                
        except Exception as e:
            self.logger.error(f"流式生成过程失败: {e}")
            await initial_msg.edit_text(f"❌ 生成失败: {str(e)}")

    async def _process_chunk_with_granular_control(self, chunk, accumulated_text_ref, phase_ref, 
                                                 first_chars_threshold, regular_update_interval, 
                                                 last_update_time_ref, initial_msg):
        """
        对大块进行字符级分割处理，实现精细化控制
        
        Args:
            chunk: 从AI接收到的文本块
            accumulated_text_ref: 累积文本的引用列表
            phase_ref: 阶段标记的引用列表
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
                        await initial_msg.edit_text(accumulated_text)
                        phase = "regular_updates"
                        last_update_time = current_time
                        self.logger.info(f"📤 首段更新完成: {char_count} 字符")
                    except Exception as e:
                        self.logger.debug(f"首段更新失败: {e}")
                        
            elif phase == "regular_updates":
                # 阶段2：每2秒更新一次
                if current_time - last_update_time >= regular_update_interval:
                    try:
                        await initial_msg.edit_text(accumulated_text)
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
        from src.domain.services.role_service import role_service
        
        # 简单校验
        if len(content) > 10000:
            return {"code": 4002, "message": "消息过长，最大长度 10000", "data": None}

        # 获取或创建会话
        session = await session_service.get_or_create_session(user_id)
        session_id = session["session_id"]
        
        # 获取会话的角色ID
        current_role_id = session.get("role_id")
        
        # 兜底机制：如果会话没有角色ID，设置默认角色
        if not current_role_id:
            self.logger.warning(f"⚠️ 会话无角色ID，触发兜底机制: user_id={user_id}, session_id={session_id}")
            default_role_id = '1'
            await session_service.set_session_role_id(session_id, default_role_id)
            current_role_id = default_role_id
        
        # 获取角色数据
        role_data = role_service.get_role_by_id(current_role_id)
        if not role_data:
            # 二次降级：角色ID对应的角色不存在
            self.logger.warning(f"⚠️ 角色不存在: role_id={current_role_id}，降级到默认角色")
            default_role_id = '1'
            role_data = role_service.get_role_by_id(default_role_id)
            if role_data:
                await session_service.set_session_role_id(session_id, default_role_id)
        
        if not role_data:
            self.logger.error(f"❌ 角色配置错误: 默认角色也不存在")
            return {"code": 4001, "message": "角色配置错误", "data": None}

        # 保存用户消息并获取历史
        user_message_id = message_service.save_message(session_id, "user", content)
        history = message_service.get_history(session_id)
        
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


# 全局单例实例
stream_message_service = StreamMessageService()
