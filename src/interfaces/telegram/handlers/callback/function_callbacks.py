"""
功能回调处理器
处理基础功能相关的回调，如签到、充值、帮助等
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
from src.utils.config.app_config import COST_QUICK_UNDRESS, COST_CUSTOM_UNDRESS


class FunctionCallbackHandler(BaseCallbackHandler):
    """功能回调处理器"""
    
    def get_callback_handlers(self):
        """返回功能回调处理方法映射"""
        return {
            "quick_undress": self.handle_quick_undress_callback,
            "custom_undress": self.handle_custom_undress_callback,
            "daily_checkin": self.handle_checkin_callback,
            "show_help": self.handle_show_help_callback,
            "back_to_main": self.handle_back_to_main,
            "cancel_generation": self.handle_cancel_generation,
            "select_faceswap_photo": self.handle_select_faceswap_photo,
            "select_faceswap_video": self.handle_select_faceswap_video,
            "select_image_generation": self.handle_select_image_generation,
            "select_video_generation": self.handle_select_video_generation,
        }
    
    @robust_callback_handler
    async def handle_quick_undress_callback(self, query, context):
        """处理快速脱衣回调"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        # 检查积分
        points_balance = await self.user_service.get_user_points_balance(user_data['id'])
        if points_balance < COST_QUICK_UNDRESS:
            message = f"❌ 积分不足！\n\n快速脱衣需要：{COST_QUICK_UNDRESS}积分\n您当前积分：{points_balance}\n\n请先获取积分："
            keyboard = self.ui_handler.create_insufficient_points_keyboard()
            await self._safe_edit_message(query, message, keyboard)
            return
        
        # 设置用户状态为等待上传图片
        self.state_helper.start_quick_undress_flow(user_id)
        
        # 使用与按钮处理一致的消息格式
        message = "👕 **快速脱衣**\n\n"
        message += "最优秀最经典的呈现！\n\n"
        message += "直接**上传图片**————建议上传站立，单人，无遮挡，主体人物清晰的照片 无奇怪动作姿势\n\n"
        message += f"图片去衣：{COST_QUICK_UNDRESS}积分/图片\n\n"
        message += "===================\n"
        message += "注意事项：\n"
        message += "1.使用我们的服务即表示您同意 用户协议且不得用于非法用途。\n"
        message += "2.严禁输入未成年相关的任何图片。\n\n"
        message += "24小时开放"
        
        await self._safe_edit_message(query, message)
    
    @robust_callback_handler
    async def handle_custom_undress_callback(self, query, context):
        """处理自定义脱衣回调"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        # 检查积分
        points_balance = await self.user_service.get_user_points_balance(user_data['id'])
        if points_balance < COST_CUSTOM_UNDRESS:
            message = f"❌ 积分不足！\n\n自定义脱衣需要：{COST_CUSTOM_UNDRESS}积分\n您当前积分：{points_balance}\n\n请先获取积分："
            keyboard = self.ui_handler.create_insufficient_points_keyboard()
            await self._safe_edit_message(query, message, keyboard)
            return
        
        # 设置用户状态
        self.state_helper.start_custom_undress_flow(user_id)
        
        message = (
            f"🎨 **自定义脱衣**\n\n"
            f"💰 消耗积分：{COST_CUSTOM_UNDRESS}\n\n"
            f"🔧 可自定义参数：\n"
            f"👔 衣服选项（14种）\n"
            f"🤸 姿势选项（100+种）\n"
            f"⚙️ 偏好设置（体型、年龄等）\n\n"
            f"请先配置参数，然后上传图片"
        )
        
        keyboard = self.ui_handler.create_custom_undress_menu_keyboard()
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_checkin_callback(self, query, context):
        """处理签到回调"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        # 调用签到服务
        result = await self.user_service.daily_checkin(user_data['id'])
        
        if result['success']:
            message = f"🎉 {result['message']}\n\n💰 获得积分: +{result.get('points', 0)}"
        else:
            message = f"ℹ️ {result['message']}"
        
        await self._safe_edit_message(query, message)
    
    @robust_callback_handler
    async def handle_show_help_callback(self, query, context):
        """处理显示帮助回调"""
        help_text = f"""
🤖 **AI图像生成机器人使用指南**

**基础功能：**
👕 快速去衣 - 一键体验，使用最优参数
🎨 自定义去衣 - 自由选择衣服、姿势、偏好

**积分消耗：**
- 快速去衣：{COST_QUICK_UNDRESS}积分
- 自定义去衣：{COST_CUSTOM_UNDRESS}积分

**使用流程：**
1. 发送图片或点击功能按钮
2. 选择处理类型和参数
3. 确认生成并等待结果

如有问题请联系客服 👨‍💻
        """
        
        await self._safe_edit_message(query, help_text)
    
    @robust_callback_handler
    async def handle_back_to_main(self, query, context):
        """处理返回主菜单回调"""
        user_id = query.from_user.id
        
        # 清除用户状态
        self.state_helper.clear_user_flow(user_id)
        
        welcome_message = (
            "🎉 **AI图像处理bot**\n\n"
            "您可以使用底部菜单或发送图片开始处理"
        )
        
        await self._safe_edit_message(query, welcome_message)
    
    @robust_callback_handler
    async def handle_cancel_generation(self, query, context):
        """处理取消生成回调"""
        user_id = query.from_user.id
        
        # 清除用户状态
        self.state_helper.clear_user_flow(user_id)
        
        await self._safe_edit_message(query, "❌ 已取消操作")
    
    @robust_callback_handler
    async def handle_select_faceswap_photo(self, query, context):
        """处理图片换脸功能选择"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        # TODO: 检查积分和设置状态
        message = (
            "🔄 **图片换脸**\n\n"
            "🚧 此功能正在开发中，敬请期待！\n\n"
            "您可以先试试其他功能："
        )
        
        keyboard = [
            [InlineKeyboardButton("👕 快速脱衣", callback_data="quick_undress")],
            [InlineKeyboardButton("🎨 自定义脱衣", callback_data="custom_undress")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_select_faceswap_video(self, query, context):
        """处理视频换脸功能选择"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        message = (
            "🎭 **视频换脸**\n\n"
            "🚧 此功能正在开发中，敬请期待！\n\n"
            "您可以先试试其他功能："
        )
        
        keyboard = [
            [InlineKeyboardButton("👕 快速脱衣", callback_data="quick_undress")],
            [InlineKeyboardButton("🎨 自定义脱衣", callback_data="custom_undress")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_select_image_generation(self, query, context):
        """处理图像生成功能选择"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        message = (
            "🖼️ **图像生成**\n\n"
            "🚧 此功能正在开发中，敬请期待！\n\n"
            "您可以先试试其他功能："
        )
        
        keyboard = [
            [InlineKeyboardButton("👕 快速脱衣", callback_data="quick_undress")],
            [InlineKeyboardButton("🎨 自定义脱衣", callback_data="custom_undress")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_select_video_generation(self, query, context):
        """处理视频动画功能选择"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        message = (
            "🎬 **视频动画**\n\n"
            "🚧 此功能正在开发中，敬请期待！\n\n"
            "您可以先试试其他功能："
        )
        
        keyboard = [
            [InlineKeyboardButton("👕 快速脱衣", callback_data="quick_undress")],
            [InlineKeyboardButton("🎨 自定义脱衣", callback_data="custom_undress")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard)) 