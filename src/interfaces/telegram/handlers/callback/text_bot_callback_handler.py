import logging
from telegram import Update
from telegram.ext import ContextTypes
from .base_callback_handler import BaseCallbackHandler, robust_callback_handler

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
    # 回调方法
    # -------------------------
    @robust_callback_handler
    async def _on_regenerate(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 重新生成 按钮"""
        await self._safe_edit_message(query, "⚙️ 功能开发中...")

    @robust_callback_handler
    async def _on_new_session(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 新的对话 按钮"""
        await self._safe_edit_message(query, "⚙️ 功能开发中...")
