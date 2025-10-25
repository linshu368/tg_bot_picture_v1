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
        # 情况2：有 session_id 但没有 user_message_id，不显示重新生成，但允许保存对话
        elif not user_message_id:
            keyboard = [[
                InlineKeyboardButton("🆕 新的对话", callback_data=f"new_session:{session_id}"),
                InlineKeyboardButton("💾 保存对话", callback_data=f"save_snapshot:{session_id}")
            ]]
        # 情况3：二者都有，显示三键
        else:
            callback_data = f"regenerate:{session_id}:{user_message_id}"
            logging.info(f"✅ callback_data={callback_data}")
            keyboard = [[
                InlineKeyboardButton("🔄 重新生成", callback_data=callback_data),
                InlineKeyboardButton("🆕 新的对话", callback_data=f"new_session:{session_id}"),
                InlineKeyboardButton("💾 保存对话", callback_data=f"save_snapshot:{session_id}")
            ]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
        """创建主菜单键盘（底部常驻键盘）"""
        keyboard = [
            [KeyboardButton("💳 充值积分")],
            [KeyboardButton("👤 个人中心"), KeyboardButton("🎁 每日签到")],
            [KeyboardButton("🎭 选择角色")],
            [KeyboardButton("🗂 历史聊天")],
            [KeyboardButton("❓ 帮助")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def create_profile_menu_keyboard() -> InlineKeyboardMarkup:
        """创建个人中心菜单键盘"""
        keyboard = [
            [
                InlineKeyboardButton("📊 积分记录", callback_data="profile_view_records")
            ],
            [
                InlineKeyboardButton("🆔 我的身份码", callback_data="profile_view_uid")
            ],
            [
                InlineKeyboardButton("📋 我的订单", callback_data="profile_view_orders")
            ],
            [
                InlineKeyboardButton("🛒 充值积分", callback_data="profile_buy_credits")
            ],
            [
                InlineKeyboardButton("🎁 每日签到", callback_data="daily_checkin")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_insufficient_points_keyboard() -> InlineKeyboardMarkup:
        """创建积分不足时的键盘"""
        keyboard = [
            [
                InlineKeyboardButton("🎁 每日签到", callback_data="daily_checkin")
            ],
            [
                InlineKeyboardButton("🛒 购买积分", callback_data="buy_credits")
            ],
            [
                InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

