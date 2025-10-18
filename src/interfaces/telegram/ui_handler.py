from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
import logging

class UIHandler:
    """文字 Bot 的 UI 渲染器（融合版）"""

    @staticmethod
    def build_reply_keyboard(session_id: str="", user_message_id: str="") -> InlineKeyboardMarkup:
        """生成消息下方的操作按钮（内联键盘）"""
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
    
    @staticmethod
    def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
        """创建主菜单键盘（底部常驻键盘）"""
        keyboard = [
            [KeyboardButton("💳 充值积分")],
            [KeyboardButton("👤 个人中心"), KeyboardButton("🎁 每日签到")],
            [KeyboardButton("🎭 选择角色")],
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

