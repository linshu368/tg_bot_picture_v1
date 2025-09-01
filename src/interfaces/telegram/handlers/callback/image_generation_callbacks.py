"""
图像生成回调处理器
处理自定义脱衣、参数选择等复杂图像生成相关回调
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
from ...ui_handler import format_user_preferences
from ...user_state_manager import States, DataKeys
from src.utils.config.app_config import (
    POSE_OPTIONS, BODY_TYPE_OPTIONS, BREAST_SIZE_OPTIONS, 
    BUTT_SIZE_OPTIONS, AGE_OPTIONS
)


class ImageGenerationCallbackHandler(BaseCallbackHandler):
    """图像生成回调处理器"""
    
    def get_callback_handlers(self):
        """返回图像生成回调处理方法映射"""
        return {
            # 自定义脱衣相关
            "custom_cloth_options": self.handle_custom_cloth_options,
            "custom_pose_options": self.handle_custom_pose_options,
            "custom_preferences": self.handle_custom_preferences,
            "start_custom_undress": self.handle_start_custom_undress,
            "back_to_custom_undress": self.handle_back_to_custom_undress,
            
            # 分页相关
            "cloth_page": self.handle_cloth_page,
            "pose_page": self.handle_pose_page,
            
            # 选择相关
            "select_cloth": self.handle_cloth_selection,
            "select_pose": self.handle_pose_selection,
            "pref": self.handle_preference_type_selection,
            "set_pref": self.handle_preference_value_selection,
            
            # 图片上传后的功能选择
            "start_quick_undress": self.handle_start_quick_undress_from_photo,
            "start_custom_undress": self.handle_start_custom_undress_from_photo,
            
            # 确认生成
            "confirm_quick_undress": self.handle_confirm_quick_undress,
            "confirm_custom_undress": self.handle_confirm_custom_undress,
        }
    
    @robust_callback_handler
    async def handle_custom_cloth_options(self, query, context):
        """处理自定义衣服选项回调"""
        message = "👔 **衣服选项**\n\n请选择要穿的衣服类型："
        keyboard = self.ui_handler.create_cloth_options_keyboard(0)
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_custom_pose_options(self, query, context):
        """处理自定义姿势选项回调"""
        message = f"🤸 **姿势选项**\n\n请选择姿势（共{len(POSE_OPTIONS)}种）："
        keyboard = self.ui_handler.create_pose_options_keyboard(0)
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_custom_preferences(self, query, context):
        """处理自定义偏好设置回调"""
        user_id = query.from_user.id
        
        # 获取当前用户偏好
        current_prefs = {}
        for key in [DataKeys.BODY_TYPE, DataKeys.BREAST_SIZE, DataKeys.BUTT_SIZE, DataKeys.AGE]:
            value = self.state_helper.state_manager.get_user_data(user_id, key)
            if value:
                current_prefs[key] = value
        
        message = "⚙️ **偏好设置**\n\n设置您的个人偏好参数："
        
        if current_prefs:
            message += format_user_preferences(current_prefs)
        
        keyboard = self.ui_handler.create_preferences_keyboard()
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_start_custom_undress(self, query, context):
        """处理开始自定义脱衣回调"""
        user_id = query.from_user.id
        
        # 检查用户是否已经上传了图片
        photo_file_id = self.state_helper.state_manager.get_user_data(user_id, DataKeys.PHOTO_FILE_ID)
        
        if photo_file_id:
            # 用户已有图片，显示配置菜单
            message = (
                "🎨 **自定义脱衣**\n\n"
                "📸 图片已准备好\n"
                "🔧 请配置生成参数："
            )
            keyboard = self.ui_handler.create_custom_undress_menu_keyboard()
        else:
            # 用户没有图片，提示上传
            # 设置状态为等待图片
            self.state_manager.update_user_state(user_id, States.CUSTOM_UNDRESS_WAITING_PHOTO)
            
            message = (
                "📸 **准备生成**\n\n"
                "请发送要处理的图片\n\n"
                "💡 支持JPG、PNG格式\n"
                "📏 建议图片尺寸不超过5MB"
            )
            keyboard = self.ui_handler.create_back_and_cancel_keyboard("back_to_main")
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_back_to_custom_undress(self, query, context):
        """处理返回自定义脱衣菜单回调"""
        message = (
            "🎨 **自定义脱衣**\n\n"
            "配置您的生成参数："
        )
        
        keyboard = self.ui_handler.create_custom_undress_menu_keyboard()
        
        await self._safe_edit_message(query, message, keyboard)
    
    # 分页回调
    @robust_callback_handler
    async def handle_cloth_page(self, query, context, page: int):
        """处理衣服选项分页回调"""
        message = "👔 **衣服选项**\n\n请选择要穿的衣服类型："
        keyboard = self.ui_handler.create_cloth_options_keyboard(page)
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_pose_page(self, query, context, page: int):
        """处理姿势选项分页回调"""
        message = f"🤸 **姿势选项**\n\n请选择姿势（共{len(POSE_OPTIONS)}种）："
        keyboard = self.ui_handler.create_pose_options_keyboard(page)
        
        await self._safe_edit_message(query, message, keyboard)
    
    # 选择回调
    @robust_callback_handler
    async def handle_cloth_selection(self, query, context, cloth: str):
        """处理衣服选择回调"""
        user_id = query.from_user.id
        
        # 保存用户选择
        self.state_helper.set_cloth_selection(user_id, cloth)
        
        message = f"✅ 已选择衣服：**{cloth.title()}**\n\n继续配置其他选项或开始生成"
        keyboard = self.ui_handler.create_custom_undress_menu_keyboard()
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_pose_selection(self, query, context, pose_index: int):
        """处理姿势选择回调"""
        user_id = query.from_user.id
        
        if 0 <= pose_index < len(POSE_OPTIONS):
            pose_name = POSE_OPTIONS[pose_index]
            
            # 保存用户选择
            self.state_helper.set_pose_selection(user_id, pose_index, pose_name)
            
            message = f"✅ 已选择姿势：**{pose_name}**\n\n继续配置其他选项或开始生成"
            keyboard = self.ui_handler.create_custom_undress_menu_keyboard()
            
            await self._safe_edit_message(query, message, keyboard)
        else:
            await self._safe_edit_message(query, "❌ 姿势选择错误")
    
    @robust_callback_handler
    async def handle_preference_type_selection(self, query, context, pref_type: str):
        """处理偏好类型选择回调"""
        type_names = {
            "body_type": "体型",
            "breast_size": "胸部大小",
            "butt_size": "臀部大小", 
            "age": "年龄"
        }
        
        message = f"⚙️ **{type_names.get(pref_type, pref_type)}设置**\n\n请选择："
        keyboard = self.ui_handler.create_preference_options_keyboard(pref_type)
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_preference_value_selection(self, query, context, data: str):
        """处理偏好值选择回调"""
        user_id = query.from_user.id
        
        # 解析回调数据: set_pref_{type}_{value}
        parts = data.replace("set_pref_", "").split("_", 1)
        if len(parts) == 2:
            pref_type, value = parts
            
            # 保存用户偏好
            self.state_helper.set_user_preference(user_id, pref_type, value)
            
            type_names = {
                "body_type": "体型",
                "breast_size": "胸部大小",
                "butt_size": "臀部大小",
                "age": "年龄"
            }
            
            message = f"✅ 已设置{type_names.get(pref_type, pref_type)}：**{value.title()}**\n\n继续设置其他偏好或返回主菜单"
            keyboard = self.ui_handler.create_preferences_keyboard()
            
            await self._safe_edit_message(query, message, keyboard)
        else:
            await self._safe_edit_message(query, "❌ 设置参数错误")
    
    @robust_callback_handler
    async def handle_start_quick_undress_from_photo(self, query, context):
        """从图片功能选择开始快速脱衣"""
        user_id = query.from_user.id
        
        # 设置状态为快速脱衣确认
        self.state_manager.update_user_state(user_id, States.QUICK_UNDRESS_CONFIRM)
        
        from src.utils.config.app_config import QUICK_UNDRESS_DEFAULTS, COST_QUICK_UNDRESS
        from ...ui_handler import format_generation_summary
        
        params = QUICK_UNDRESS_DEFAULTS.copy()
        summary = format_generation_summary(params, COST_QUICK_UNDRESS)
        
        keyboard = self.ui_handler.create_generation_confirmation_keyboard("quick_undress")
        
        await self._safe_edit_message(query, summary, keyboard)
    
    @robust_callback_handler
    async def handle_start_custom_undress_from_photo(self, query, context):
        """从图片功能选择开始自定义脱衣"""
        user_id = query.from_user.id
        
        # 设置状态为自定义脱衣菜单
        self.state_manager.update_user_state(user_id, States.CUSTOM_UNDRESS_MENU)
        
        message = (
            "🎨 **自定义脱衣**\n\n"
            "📸 图片已准备好\n"
            "🔧 请配置生成参数："
        )
        
        keyboard = self.ui_handler.create_custom_undress_menu_keyboard()
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_confirm_quick_undress(self, query, context):
        """处理确认快速脱衣"""
        # 导入图像处理模块
        from ..image_processing import ImageProcessingHandler
        
        # 创建图像处理器并调用处理方法
        image_processor = ImageProcessingHandler(self.bot)
        await image_processor.process_quick_undress_confirmation(query, context)
    
    @robust_callback_handler
    async def handle_confirm_custom_undress(self, query, context):
        """处理确认自定义脱衣"""
        # 导入图像处理模块
        from ..image_processing import ImageProcessingHandler
        
        # 创建图像处理器并调用处理方法
        image_processor = ImageProcessingHandler(self.bot)
        await image_processor.process_custom_undress_confirmation(query, context) 