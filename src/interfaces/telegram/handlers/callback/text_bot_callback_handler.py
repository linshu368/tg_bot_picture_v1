import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import uuid
from telegram.ext import ContextTypes
from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
from ...ui_handler import UIHandler
from src.domain.services.message_service import message_service_singleton as message_service
from src.domain.services.ai_completion_port import AICompletionPort
from demo.api import GPTCaller
from demo.role import role_data

# 导入全局单例 session_service，确保与 session_controller 使用同一实例
from src.interfaces.telegram.controllers.session_controller import session_service

ai_port = AICompletionPort(GPTCaller())

class TextBotCallbackHandler(BaseCallbackHandler):
    """文字 Bot 的回调处理器"""

    def __init__(self, bot_instance):
        super().__init__(bot_instance)
        self.logger = logging.getLogger(__name__)

    def get_callback_handlers(self):
        """定义本 Bot 支持的回调动作"""
        handlers = {
            "regenerate": self._on_regenerate,
            "new_session": self._on_new_session,
        }
        self.logger.info(f"✅ 注册回调 handlers: {list(handlers.keys())}")
        return handlers

    # -------------------------
    # 工具方法
    # -------------------------
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
        """点击 重新生成 按钮"""
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
            result = await message_service.regenerate_reply(
                session_id=session_id,
                last_message_id=user_message_id,   # ✅ 用 user_message_id 精确定位
                ai_port=ai_port,
                role_data=role_data,
            )
            reply = result["reply"]
        except TimeoutError:
            reply = "⏱️ 生成超时，请重试"
        except Exception as e:
            self.logger.error(f"❌ regenerate 调用 AI 失败: {e}")
            reply = "⚠️ AI生成失败，请重试"

        # ✅ 更新消息时，把 session_id 和 user_message_id 带下去
        await self._update_message(query, reply, session_id=session_id, user_message_id=user_message_id)

    @robust_callback_handler
    async def _on_new_session(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 新的对话 按钮"""
        self.logger.info(f"📥 收到回调 action=new_session data={query.data} user_id={query.from_user.id}")
        user_id = str(query.from_user.id)

        # 调用 Service 创建新会话
        session = await session_service.new_session(user_id)

        reply = f"已开启新对话 (session_id={session['session_id']})"

        await self._update_message(query, reply, session_id=session["session_id"])