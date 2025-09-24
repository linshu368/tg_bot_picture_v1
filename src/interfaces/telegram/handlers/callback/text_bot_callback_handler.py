import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import uuid
from telegram.ext import ContextTypes
from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
from ...ui_handler import UIHandler
from src.domain.services.session_service_base import SessionService
# 初始化全局 SessionService（轻量版，内存存储）
session_service = SessionService()

class TextBotCallbackHandler(BaseCallbackHandler):
    """文字 Bot 的回调处理器"""

    def __init__(self, bot_instance):
        super().__init__(bot_instance)
        self.logger = logging.getLogger(__name__)

    def get_callback_handlers(self):
        """定义本 Bot 支持的回调动作"""
        return {
            "regenerate": self._on_regenerate,
            "new_session": self._on_new_session,
        }

    # -------------------------
    # 工具方法
    # -------------------------
    async def _update_message(self, query, reply_text: str):
        """统一的消息更新方法（actions 暂时由 UIHandler 固定）"""        
        await query.edit_message_text(
            text=reply_text,
            reply_markup=UIHandler.build_reply_keyboard(),
        )

    # -------------------------
    # 回调方法
    # -------------------------
    @robust_callback_handler
    async def _on_regenerate(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 重新生成 按钮"""
        user_id = str(query.from_user.id)
        last_message_id = str(uuid.uuid4())  # TODO: 未来从 MessageService 获取

         # 暂时用 Mock 回复，未来接入 AICompletionPort
        reply = f"这是重新生成的回复 (last_message_id={last_message_id})"

        await self._update_message(query, reply)

    @robust_callback_handler
    async def _on_new_session(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 新的对话 按钮"""
        user_id = str(query.from_user.id)

        # 调用 Service 创建新会话
        session = await session_service.new_session(user_id)

        reply = f"已开启新对话 (session_id={session['session_id']})"

        await self._update_message(query, reply)