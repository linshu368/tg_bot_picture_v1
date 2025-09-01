"""
个人中心回调处理器
处理个人信息、积分记录、身份码等相关回调
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
from ...ui_handler import escape_markdown


class ProfileCallbackHandler(BaseCallbackHandler):
    """个人中心回调处理器"""
    
    def get_callback_handlers(self):
        """返回个人中心回调处理方法映射"""
        return {
            "profile": self.handle_profile_callback,
            "profile_view_records": self.handle_profile_view_records,
            "profile_view_uid": self.handle_profile_view_uid,
            "profile_view_orders": self.handle_profile_view_orders,
            "profile_buy_credits": self.handle_profile_buy_credits,
            "back_to_profile": self.handle_back_to_profile,
            "view_records": self.handle_view_records_callback,
        }
    
    @robust_callback_handler
    async def handle_profile_callback(self, query, context):
        """处理个人中心回调"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        points_balance = await self.user_service.get_user_points_balance(user_data['id'])
        username_display = escape_markdown(
            query.from_user.username if query.from_user.username else "未设置"
        )
        
        message = "👤 **个人中心**\n\n"
        message += f"🆔 身份码：`{user_data.get('uid', 'N/A')}`\n"
        message += f"👤 用户名：{username_display}\n"
        message += f"🎖️ 等级：{user_data.get('level', 1)}\n"
        message += f"💎 当前积分：{points_balance}\n\n"
        
        # 统计信息
        message += "📊 **统计信息**\n"
        message += f"💰 累计消费：¥{user_data.get('total_paid', 0):.2f}\n"
        message += f"🔥 累计使用：{user_data.get('total_points_spent', 0)}积分\n"
        message += f"📅 注册时间：{user_data.get('created_at', 'N/A')[:10]}\n\n"
        message += "请选择功能："
        
        keyboard = self.ui_handler.create_profile_menu_keyboard()
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_profile_view_records(self, query, context):
        """处理查看积分记录"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在")
            return
        
        # 获取积分记录
        records = await self.user_service.get_user_points_history(user_data['id'], limit=10)
        
        message = "📊 **积分记录**\n\n"
        
        if records:
            for record in records:
                change = record.get('points_change', 0)
                action = record.get('action_type', '未知操作')
                date = record.get('created_at', 'N/A')[:10]
                
                if change > 0:
                    message += f"✅ +{change}积分 - {action} ({date})\n"
                else:
                    message += f"❌ {change}积分 - {action} ({date})\n"
        else:
            message += "暂无积分记录"
        
        keyboard = [[InlineKeyboardButton("🔙 返回个人中心", callback_data="back_to_profile")]]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_profile_view_uid(self, query, context):
        """处理查看身份码"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在")
            return
        
        uid = user_data.get('uid', 'N/A')
        
        message = "🆔 **我的身份码**\n\n"
        message += f"您的身份码：`{uid}`\n\n"
        message += "⚠️ **重要提醒：**\n"
        message += "• 请妥善保存此身份码\n"
        message += "• 可用于找回账号和积分\n"
        message += "• 请勿泄露给他人\n\n"
        message += "💡 建议截图保存或写在备忘录中"
        
        keyboard = [[InlineKeyboardButton("🔙 返回个人中心", callback_data="back_to_profile")]]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_profile_view_orders(self, query, context):
        """处理查看订单记录"""
        message = "📋 **订单记录**\n\n"
        message += "订单记录功能开发中...\n\n"
        message += "敬请期待！"
        
        keyboard = [[InlineKeyboardButton("🔙 返回个人中心", callback_data="back_to_profile")]]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_profile_buy_credits(self, query, context):
        """处理个人中心中的充值积分"""
        # 直接调用回调管理器中已有的支付处理器，避免创建重复实例
        await self.bot.callback_manager.payment_handler.handle_buy_credits_callback(query, context)
    
    @robust_callback_handler
    async def handle_back_to_profile(self, query, context):
        """返回个人中心"""
        await self.handle_profile_callback(query, context)
    
    @robust_callback_handler
    async def handle_view_records_callback(self, query, context):
        """处理查看记录回调"""
        await self._safe_edit_message(query, "📊 积分记录功能开发中...") 