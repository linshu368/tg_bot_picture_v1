"""
消息处理器
处理图片消息、文本消息和各种用户输入
"""

import logging
import asyncio
from typing import Dict, Any, Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..ui_handler import UIHandler, escape_markdown, format_generation_summary
from ..user_state_manager import UserStateManager, UserStateHelper, States, DataKeys
from src.utils.config.app_config import (
    COST_QUICK_UNDRESS, COST_CUSTOM_UNDRESS, QUICK_UNDRESS_DEFAULTS, 
    UID_PREFIX, UID_LENGTH
)




class MessageHandler:
    """消息处理器"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.logger = logging.getLogger(__name__)
        self.ui_handler: UIHandler = bot_instance.ui_handler
        self.state_manager: UserStateManager = bot_instance.state_manager
        self.state_helper: UserStateHelper = bot_instance.state_helper
        
        # 服务依赖
        self.user_service = bot_instance.user_service
        self.image_service = bot_instance.image_service
        self.payment_service = bot_instance.payment_service
        # 新增会话和行为记录服务
        self.session_service = bot_instance.session_service
        self.action_record_service = bot_instance.action_record_service
    
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
      
    async def _safe_get_user(self, user_id: int):
        """安全获取用户信息"""
        self.logger.info(f"开始获取用户信息: telegram_id={user_id}")
        try:
            user = await self.user_service.get_user_by_telegram_id(user_id)
            if user:
                self.logger.info(f"获取用户信息成功: telegram_id={user_id}, user_id={user.get('id')}, uid={user.get('uid')}")
            else:
                self.logger.warning(f"未找到用户: telegram_id={user_id}")
            return user
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {user_id}, 错误: {e}")
            return None

    async def _handle_button_dispatch(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """分发按钮处理，每个功能独立错误处理"""
        self.logger.info(f"🔍 [BUTTON_DISPATCH] 开始处理文本按钮: '{text}'")
    
        function_map = {
            "💳 充值积分": self._handle_buy_button,
            "👤 个人中心": self._handle_profile_button,
            "🎁 每日签到": self._handle_checkin_button
        }
        
        if text in function_map:
            self.logger.info(f"🔍 [BUTTON_DISPATCH] 匹配到功能按钮: '{text}' -> {function_map[text].__name__}")
            await self._safe_handle_function(function_map[text], update, context)
        else:
            self.logger.info(f"🔍 [BUTTON_DISPATCH] 未匹配到功能按钮: '{text}'，发送默认提示")
            # 默认提示
            await update.message.reply_text(
                "🎨 /start - 显示主菜单\n"
                "💎 /points - 查看积分\n"
            )

    async def _safe_handle_function(self, func, update, context, *args):
        """安全执行功能函数，提供独立的错误处理"""
        function_name = getattr(func, '__name__', '未知功能')
        self.logger.info(f"🔍 [SAFE_HANDLE] 开始执行功能: {function_name}")
        try:
            await func(update, context, *args)
            self.logger.info(f"🔍 [SAFE_HANDLE] 功能执行完成: {function_name}")

        except Exception as e:
            self.logger.error(f"🔍 [SAFE_HANDLE] 功能 {function_name} 执行失败: {e}")
            
            # 根据功能类型提供不同的错误处理
            error_message = self._get_function_error_message(function_name)
            
            try:
                await update.message.reply_text(error_message)
            except Exception as e2:
                self.logger.error(f"发送错误消息失败: {e2}")

   

    async def _handle_text_message_error(self, update: Update, user_id: int, error: Exception):
        """处理文本消息的全局错误"""
        try:
            # 清除可能的错误状态
            self.state_manager.reset_user_state(user_id)
            
            error_message = (
                "❌ **系统遇到问题**\n\n"
                "已自动重置您的状态\n\n"
                "💡 建议操作：\n"
                "• 使用底部菜单重新选择功能\n"
                "• 发送 /start 重新开始\n"
                "• 如问题持续，请联系客服"
            )
            
            keyboard = self.ui_handler.create_main_menu_keyboard()
            await update.message.reply_text(
                error_message, 
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            self.logger.error(f"文本消息错误恢复失败: {e}")
            # 最后的保险措施
            try:
                await update.message.reply_text("❌ 系统问题，请使用 /start 重新开始")
            except:
                pass

   
    async def _handle_buy_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理充值按钮"""
        # 调用支付命令处理器的逻辑
        from .command.payment_commands import PaymentCommandHandler
        payment_handler = PaymentCommandHandler(self.bot)
        await payment_handler.handle_buy_command(update, context)

    async def _handle_profile_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理个人中心按钮"""
        user = update.effective_user
        
        user_data = await self.user_service.get_user_by_telegram_id(user.id)
        if not user_data:
            await update.message.reply_text("❌ 用户不存在，请先使用 /start")
            return
        
        points_balance = await self.user_service.get_user_points_balance(user_data['id'])
        
        # 获取用户统计信息
        username_display = escape_markdown(
            user.username if user.username else "未设置"
        )
        
        message = "👤 **个人中心**\n\n"
        message += f"👤 用户名：{username_display}\n"
        message += f"💎 当前积分：{points_balance}\n\n"
        
        # 统计信息
        message += "📊 **统计信息**\n"
        message += f"💰 累计消费：¥{user_data.get('total_paid', 0):.2f}\n"
        message += f"🔥 累计使用：{user_data.get('total_points_spent', 0)}积分\n"
        message += f"📅 注册时间：{user_data.get('created_at', 'N/A')[:10]}\n\n"
        message += "请选择功能："
        
        keyboard = self.ui_handler.create_profile_menu_keyboard()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    async def _handle_checkin_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理签到按钮"""
        # 调用用户命令处理器的逻辑
        from .command.user_commands import UserCommandHandler
        user_handler = UserCommandHandler(self.bot)
        await user_handler.handle_checkin_command(update, context)

    