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

# # ----------------------------------
# # 兼容老项目依赖的 escape_markdown
# # ----------------------------------
# def escape_markdown(text: str, version: int = 2) -> str:
#     """
#     转义 Markdown 特殊字符，避免 Telegram 格式化出错
#     默认使用 MarkdownV2。
#     """
#     escape_chars = r'_*[]()~`>#+-=|{}.!'
#     if version == 2:
#         return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)
#     return text





# """
# Telegram UI处理器
# 负责生成各种键盘菜单和用户界面
# """

# import math
# from typing import List, Dict, Any, Optional, Tuple
# from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
# from src.utils.config.app_config import (
#     COST_QUICK_UNDRESS, COST_CUSTOM_UNDRESS, COST_FACESWAP_PHOTO, 
#     COST_FACESWAP_VIDEO, QUICK_UNDRESS_DEFAULTS,
#     CLOTH_OPTIONS, POSE_OPTIONS, CLOTH_PER_PAGE, POSE_PER_PAGE,
#     BODY_TYPE_OPTIONS, BREAST_SIZE_OPTIONS, BUTT_SIZE_OPTIONS, AGE_OPTIONS,
#     PAYMENT_METHODS, CREDIT_PACKAGES, FIRST_CHARGE_BONUS, REGULAR_CHARGE_BONUS
# )


# class UIHandler:
#     """UI界面处理器"""
    
#     def __init__(self):
#         pass
    
#     def create_main_menu_keyboard(self) -> ReplyKeyboardMarkup:
#         """创建主菜单键盘（底部常驻键盘）"""
#         keyboard = [
#             [KeyboardButton("👕 快速脱衣"), KeyboardButton("🎨 自定义脱衣")],
#             [KeyboardButton("🔄 快速换脸"), KeyboardButton("💳 充值积分")],
#             [KeyboardButton("👤 个人中心"), KeyboardButton("🎁 每日签到")],
#             [KeyboardButton("🔁 找回账号"), KeyboardButton("❓ 帮助")],
#         ]
#         return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
#     def create_profile_menu_keyboard(self) -> InlineKeyboardMarkup:
#         """创建个人中心菜单键盘"""
#         keyboard = [
#             [
#                 InlineKeyboardButton("📊 积分记录", callback_data="profile_view_records")
#             ],
#             [
#                 InlineKeyboardButton("🆔 我的身份码", callback_data="profile_view_uid")
#             ],
#             [
#                 InlineKeyboardButton("📋 我的订单", callback_data="profile_view_orders")
#             ],
#             [
#                 InlineKeyboardButton("🛒 充值积分", callback_data="profile_buy_credits")
#             ],
#             [
#                 InlineKeyboardButton("🎁 每日签到", callback_data="daily_checkin")
#             ]
#         ]
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_function_selection_keyboard(self) -> InlineKeyboardMarkup:
#         """创建功能选择键盘（图片上传后显示）"""
#         keyboard = [
#             [
#                 InlineKeyboardButton("👕 快速脱衣", callback_data="start_quick_undress")
#             ],
#             [
#                 InlineKeyboardButton("🎨 自定义脱衣", callback_data="start_custom_undress")
#             ],
#             [
#                 InlineKeyboardButton("🔄 图片换脸", callback_data="select_faceswap_photo")
#             ],
#             [
#                 InlineKeyboardButton("🎭 人脸视频", callback_data="select_faceswap_video")
#             ],
#             [
#                 InlineKeyboardButton("🖼️ 图像生成", callback_data="select_image_generation")
#             ],
#             [
#                 InlineKeyboardButton("🎬 视频动画", callback_data="select_video_generation")
#             ]
#         ]
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_custom_undress_menu_keyboard(self) -> InlineKeyboardMarkup:
#         """创建自定义脱衣菜单键盘"""
#         keyboard = [
#             [
#                 InlineKeyboardButton("👔 衣服选项", callback_data="custom_cloth_options")
#             ],
#             [
#                 InlineKeyboardButton("🤸 姿势选项", callback_data="custom_pose_options")
#             ],
#             [
#                 InlineKeyboardButton("⚙️ 偏好设置", callback_data="custom_preferences")
#             ],
#             [
#                 InlineKeyboardButton("▶️ 开始生成", callback_data="confirm_custom_undress")
#             ],
#             [
#                 InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
#             ]
#         ]
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_cloth_options_keyboard(self, page: int = 0) -> InlineKeyboardMarkup:
#         """创建衣服选项分页键盘"""
#         total_pages = math.ceil(len(CLOTH_OPTIONS) / CLOTH_PER_PAGE)
#         start_idx = page * CLOTH_PER_PAGE
#         end_idx = min(start_idx + CLOTH_PER_PAGE, len(CLOTH_OPTIONS))
        
#         keyboard = []
        
#         # 当前页的衣服选项（每行2个）
#         for i in range(start_idx, end_idx, 2):
#             row = []
#             # 第一个按钮
#             cloth = CLOTH_OPTIONS[i]
#             row.append(InlineKeyboardButton(
#                 f"👔 {cloth.title()}", 
#                 callback_data=f"select_cloth_{cloth}"
#             ))
            
#             # 第二个按钮（如果存在）
#             if i + 1 < end_idx:
#                 cloth = CLOTH_OPTIONS[i + 1]
#                 row.append(InlineKeyboardButton(
#                     f"👔 {cloth.title()}", 
#                     callback_data=f"select_cloth_{cloth}"
#                 ))
            
#             keyboard.append(row)
        
#         # 分页导航
#         nav_row = []
#         if page > 0:
#             nav_row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"cloth_page_{page-1}"))
#         if page < total_pages - 1:
#             nav_row.append(InlineKeyboardButton("➡️ 下一页", callback_data=f"cloth_page_{page+1}"))
        
#         if nav_row:
#             keyboard.append(nav_row)
        
#         # 返回按钮
#         keyboard.append([
#             InlineKeyboardButton("🔙 返回", callback_data="back_to_custom_undress")
#         ])
        
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_pose_options_keyboard(self, page: int = 0) -> InlineKeyboardMarkup:
#         """创建姿势选项分页键盘"""
#         total_pages = math.ceil(len(POSE_OPTIONS) / POSE_PER_PAGE)
#         start_idx = page * POSE_PER_PAGE
#         end_idx = min(start_idx + POSE_PER_PAGE, len(POSE_OPTIONS))
        
#         keyboard = []
        
#         # 当前页的姿势选项（每行2个）
#         for i in range(start_idx, end_idx, 2):
#             row = []
#             # 第一个按钮
#             pose = POSE_OPTIONS[i]
#             row.append(InlineKeyboardButton(
#                 f"🤸 {pose}", 
#                 callback_data=f"select_pose_{i}"
#             ))
            
#             # 第二个按钮（如果存在）
#             if i + 1 < end_idx:
#                 pose = POSE_OPTIONS[i + 1]
#                 row.append(InlineKeyboardButton(
#                     f"🤸 {pose}", 
#                     callback_data=f"select_pose_{i+1}"
#                 ))
            
#             keyboard.append(row)
        
#         # 分页导航
#         nav_row = []
#         if page > 0:
#             nav_row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"pose_page_{page-1}"))
#         if page < total_pages - 1:
#             nav_row.append(InlineKeyboardButton("➡️ 下一页", callback_data=f"pose_page_{page+1}"))
        
#         if nav_row:
#             keyboard.append(nav_row)
        
#         # 返回按钮
#         keyboard.append([
#             InlineKeyboardButton("🔙 返回", callback_data="back_to_custom_undress")
#         ])
        
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_preferences_keyboard(self) -> InlineKeyboardMarkup:
#         """创建偏好设置键盘"""
#         keyboard = [
#             [
#                 InlineKeyboardButton("👤 体型设置", callback_data="pref_body_type")
#             ],
#             [
#                 InlineKeyboardButton("🍒 胸部设置", callback_data="pref_breast_size")
#             ],
#             [
#                 InlineKeyboardButton("🍑 臀部设置", callback_data="pref_butt_size")
#             ],
#             [
#                 InlineKeyboardButton("🎂 年龄设置", callback_data="pref_age")
#             ],
#             [
#                 InlineKeyboardButton("🔙 返回", callback_data="back_to_custom_undress")
#             ]
#         ]
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_preference_options_keyboard(self, pref_type: str) -> InlineKeyboardMarkup:
#         """创建具体偏好选项键盘"""
#         keyboard = []
        
#         if pref_type == "body_type":
#             options = BODY_TYPE_OPTIONS
#             emojis = ["🍃", "👤", "🍐", "💪"]
#         elif pref_type == "breast_size":
#             options = BREAST_SIZE_OPTIONS
#             emojis = ["🤏", "👌", "🤲"]
#         elif pref_type == "butt_size":
#             options = BUTT_SIZE_OPTIONS
#             emojis = ["🤏", "👌", "🤲"]
#         elif pref_type == "age":
#             options = AGE_OPTIONS
#             emojis = ["🧒"] * len(options)
#         else:
#             return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="custom_preferences")]])
        
#         # 创建选项按钮（每行2个）
#         for i in range(0, len(options), 2):
#             row = []
#             # 第一个按钮
#             option = options[i]
#             emoji = emojis[i] if i < len(emojis) else "⭐"
#             row.append(InlineKeyboardButton(
#                 f"{emoji} {option.title()}", 
#                 callback_data=f"set_pref_{pref_type}_{option}"
#             ))
            
#             # 第二个按钮（如果存在）
#             if i + 1 < len(options):
#                 option = options[i + 1]
#                 emoji = emojis[i + 1] if i + 1 < len(emojis) else "⭐"
#                 row.append(InlineKeyboardButton(
#                     f"{emoji} {option.title()}", 
#                     callback_data=f"set_pref_{pref_type}_{option}"
#                 ))
            
#             keyboard.append(row)
        
#         # 返回按钮
#         keyboard.append([
#             InlineKeyboardButton("🔙 返回", callback_data="custom_preferences")
#         ])
        
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_payment_packages_keyboard(self, is_first_purchase: bool = False) -> InlineKeyboardMarkup:
#         """创建充值套餐键盘"""
        
#         keyboard = []
        
#         for package_id, package_info in CREDIT_PACKAGES.items():
#             name = package_info["name"]
#             credits = package_info["credits"]
#             price = package_info["price"]
            
#             if is_first_purchase:
#                 bonus_rate = FIRST_CHARGE_BONUS.get(package_id, 0)
#                 bonus_credits = int(credits * bonus_rate / 100)
#                 total_credits = credits + bonus_credits
                
#                 if bonus_rate == 0:
#                     text = f"{name} - ¥{price}"
#                 else:
#                     text = f"{name} - ¥{price} (首充+{bonus_rate}%)"
#             else:
#                 bonus_rate = REGULAR_CHARGE_BONUS.get(package_id, 0)
#                 bonus_credits = int(credits * bonus_rate / 100)
#                 total_credits = credits + bonus_credits
                
#                 if bonus_rate == 0:
#                     text = f"{name} - ¥{price}"
#                 else:
#                     text = f"{name} - ¥{price} (+{bonus_rate}%)"
            
#             keyboard.append([InlineKeyboardButton(
#                 text, 
#                 callback_data=f"select_package_{package_id}"
#             )])
        
#         keyboard.append([
#             InlineKeyboardButton("❌ 取消", callback_data="cancel_buy")
#         ])
        
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_payment_methods_keyboard(self, package_id: str) -> InlineKeyboardMarkup:
#         """创建支付方式选择键盘"""
        
#         keyboard = []
        
#         for method_id, method_name in PAYMENT_METHODS.items():
#             keyboard.append([InlineKeyboardButton(
#                 f"💳 {method_name}", 
#                 callback_data=f"pay_method_{method_id}_{package_id}"
#             )])
        
#         keyboard.append([
#             InlineKeyboardButton("🔙 返回套餐选择", callback_data="buy_credits"),
#             InlineKeyboardButton("❌ 取消", callback_data="cancel_buy")
#         ])
        
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_generation_confirmation_keyboard(self, generation_type: str = "image") -> InlineKeyboardMarkup:
#         """创建生成确认键盘"""
#         keyboard = []
        
#         if generation_type == "custom_undress":
#             keyboard.append([
#                 InlineKeyboardButton("✅ 确认生成", callback_data="confirm_custom_undress")
#             ])
#             keyboard.append([
#                 InlineKeyboardButton("🔙 返回设置", callback_data="back_to_custom_undress")
#             ])
#         elif generation_type == "quick_undress":
#             keyboard.append([
#                 InlineKeyboardButton("✅ 确认生成", callback_data="confirm_quick_undress")
#             ])
#         elif generation_type == "faceswap":
#             keyboard.append([
#                 InlineKeyboardButton("✅ 确认换脸", callback_data="confirm_faceswap_generation")
#             ])
#         else:
#             keyboard.append([
#                 InlineKeyboardButton("✅ 确认生成", callback_data="confirm_generation")
#             ])
        
#         keyboard.append([
#             InlineKeyboardButton("❌ 取消", callback_data="cancel_generation")
#         ])
        
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_insufficient_points_keyboard(self) -> InlineKeyboardMarkup:
#         """创建积分不足时的键盘"""
#         keyboard = [
#             [
#                 InlineKeyboardButton("🎁 每日签到", callback_data="daily_checkin")
#             ],
#             [
#                 InlineKeyboardButton("🛒 购买积分", callback_data="buy_credits")
#             ],
#             [
#                 InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
#             ]
#         ]
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_faceswap_type_keyboard(self) -> InlineKeyboardMarkup:
#         """创建人脸交换类型选择键盘"""
#         keyboard = [
#             [
#                 InlineKeyboardButton("🖼️ 图片换脸", callback_data="select_faceswap_photo")
#             ],
#             [
#                 InlineKeyboardButton("🎭 视频换脸", callback_data="select_faceswap_video")
#             ],
#             [
#                 InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
#             ]
#         ]
#         return InlineKeyboardMarkup(keyboard)
    
#     def create_back_and_cancel_keyboard(self, back_callback: str = "back_to_main") -> InlineKeyboardMarkup:
#         """创建返回和取消键盘"""
#         keyboard = [
#             [
#                 InlineKeyboardButton("🔙 返回", callback_data=back_callback),
#                 InlineKeyboardButton("❌ 取消", callback_data="cancel_generation")
#             ]
#         ]
#         return InlineKeyboardMarkup(keyboard)


# def escape_markdown(text: str) -> str:
#     """转义Markdown特殊字符"""
#     if not text:
#         return "未设置"
    
#     special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
#     for char in special_chars:
#         text = text.replace(char, f"\\{char}")
#     return text


# def format_user_preferences(preferences: Dict[str, Any]) -> str:
#     """格式化用户偏好信息"""
#     body_type = preferences.get("body_type", "normal")
#     breast_size = preferences.get("breast_size", "normal") 
#     butt_size = preferences.get("butt_size", "normal")
#     age = preferences.get("age", "25")
    
#     return f"""
# 🔧 **当前偏好设置：**
# 👤 体型：{escape_markdown(body_type.title())}
# 🍒 胸部：{escape_markdown(breast_size.title())}
# 🍑 臀部：{escape_markdown(butt_size.title())}
# 🎂 年龄：{escape_markdown(str(age))}
# """


# def format_generation_summary(params: Dict[str, Any], cost: int) -> str:
#     """格式化生成参数摘要"""
#     cloth = params.get("cloth", "naked")
#     pose = params.get("pose", "未选择")
#     body_type = params.get("body_type", "normal")
    
#     summary = f"""
# 🎨 **生成参数确认：**
# 👔 衣服：{escape_markdown(cloth.title())}
# 🤸 姿势：{escape_markdown(pose)}
# 👤 体型：{escape_markdown(body_type.title())}
# 💰 消耗积分：{cost}

# 确认生成此图像吗？
# """
#     return summary 