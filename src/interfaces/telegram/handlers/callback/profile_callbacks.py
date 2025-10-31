"""
个人中心回调处理器
处理个人信息、积分记录、身份码等相关回调
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
# from ...ui_handler import escape_markdown


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
       
        
        await self._safe_edit_message(query, message, keyboard)
    
    @robust_callback_handler
    async def handle_profile_view_records(self, query, context):
        """处理查看积分记录"""
      
        
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