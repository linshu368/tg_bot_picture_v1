from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
import logging

class UIHandler:
    """文字 Bot 的 UI 渲染器（融合版）"""

    @staticmethod
    def build_reply_keyboard(session_id: str="", user_message_id: str="") -> InlineKeyboardMarkup:
        """生成消息下方的操作按钮（内联键盘）"""
        # 情况1：没有 session_id，仅提供新对话
        if not session_id:
            logging.warning(f"⚠️ callback_data 被禁用: session_id={session_id}, user_message_id={user_message_id}")
            keyboard = [[InlineKeyboardButton("🆕 新的对话", callback_data="new_session")]]
        # 情况2：有 session_id 但没有 user_message_id，仅显示新对话与保存
        elif not user_message_id:
            keyboard = [[
                InlineKeyboardButton("🆕 新的对话", callback_data=f"new_session:{session_id}"),
                InlineKeyboardButton("💾 保存对话", callback_data=f"save_snapshot:{session_id}")
            ]]
        # 情况3：二者都有，仍只显示新对话与保存（暂时下线重新生成）
        else:
            keyboard = [[
                InlineKeyboardButton("🆕 新的对话", callback_data=f"new_session:{session_id}"),
                InlineKeyboardButton("💾 保存对话", callback_data=f"save_snapshot:{session_id}")
            ]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
        """创建主菜单键盘（底部常驻键盘）"""
        keyboard = [
            [KeyboardButton("🎭 选择角色")],
            [KeyboardButton("🗂 历史聊天")],
            [KeyboardButton("❓ 帮助")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    

