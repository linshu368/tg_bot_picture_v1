from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging

class UIHandler:
    """文字 Bot 的 UI 渲染器"""

    @staticmethod
    def build_reply_keyboard(session_id: str="", user_message_id: str="") -> InlineKeyboardMarkup:
        """生成消息下方的操作按钮"""
        # 如果 user_message_id 为空，就不要生成 regenerate 按钮，避免非法 callback_data
        if not session_id or not user_message_id:
            logging.warning(f"⚠️ callback_data 被禁用: session_id={session_id}, user_message_id={user_message_id}")
            keyboard = [
                [InlineKeyboardButton("🆕 新的对话", callback_data="new_session")]
            ]
        else:
            callback_data = f"regenerate:{session_id}:{user_message_id}"
            logging.info(f"✅ callback_data={callback_data}")
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔄 重新生成", 
                        callback_data=callback_data
                    ),
                    InlineKeyboardButton(
                        "🆕 新的对话", 
                        callback_data="new_session"
                    ),
                ]
            ]
        return InlineKeyboardMarkup(keyboard)

