from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
import logging

class UIHandler:
    """文字 Bot 的 UI 渲染器（融合版）"""

    @staticmethod
    def build_reply_keyboard(session_id: str="", user_message_id: str="") -> InlineKeyboardMarkup:
        """生成消息下方的操作按钮（内联键盘）"""
        # 情况1：没有 session_id，暂不提供任何按钮（隐藏新对话入口）
        if not session_id:
            logging.warning(f"⚠️ callback_data 被禁用: session_id={session_id}, user_message_id={user_message_id}")
            keyboard = []
        # 情况2：有 session_id 但没有 user_message_id，暂时仅显示保存
        elif not user_message_id:
            keyboard = [[
                InlineKeyboardButton("💾 保存对话", callback_data=f"save_snapshot:{session_id}")
            ]]
        # 情况3：二者都有，仅显示保存（新对话入口下线）
        else:
            keyboard = [[
                InlineKeyboardButton("💾 保存对话", callback_data=f"save_snapshot:{session_id}")
            ]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
        """创建主菜单键盘（底部常驻键盘）"""
        keyboard = [
            [KeyboardButton("🎭 选择角色")],
            [KeyboardButton("🗂 历史聊天")],
            [KeyboardButton("⚙️ 设置"), KeyboardButton("❓ 帮助")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    

