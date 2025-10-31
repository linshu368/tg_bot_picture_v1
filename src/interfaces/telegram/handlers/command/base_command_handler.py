"""
基础命令处理器
提供通用的命令处理功能和错误处理
"""

import logging
from typing import Dict, Any, Optional
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ...ui_handler import UIHandler, escape_markdown


def safe_command_handler(func):
    """装饰器：为命令处理器添加统一的错误处理"""
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(self, update, context, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"命令处理器 {func.__name__} 失败: {e}")
            
            try:
                error_message = (
                    "❌ **命令执行遇到问题**\n\n"
                    "请稍后重试，或使用其他功能\n\n"
                    "💡 您可以使用 /start 重新开始"
                )
                
                await update.message.reply_text(
                    error_message,
                    reply_markup=self.ui_handler.create_main_menu_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                
            except Exception as e2:
                self.logger.error(f"发送错误恢复消息也失败: {e2}")
    
    return wrapper


class BaseCommandHandler:
    """命令处理器基类"""
    
    def __init__(self, bot_instance, admin_user_id: int = None):
        self.bot = bot_instance
        self.admin_user_id = admin_user_id
        self.logger = logging.getLogger(__name__)
        
        # 核心组件
        self.ui_handler: UIHandler = bot_instance.ui_handler
       
        
        # 服务依赖
        self.user_service = bot_instance.user_service
        self.image_service = bot_instance.image_service
        self.payment_service = bot_instance.payment_service
        # 新增会话和行为记录服务
        self.session_service = bot_instance.session_service
        self.action_record_service = bot_instance.action_record_service
    
    async def _safe_get_user(self, telegram_id: int):
        """安全获取用户信息"""
        try:
            return await self.user_service.get_user_by_telegram_id(telegram_id)
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {telegram_id}, 错误: {e}")
            return None
    
    async def _check_user_exists(self, update: Update) -> Optional[Dict[str, Any]]:
        """检查用户是否存在，不存在时发送提示消息"""
        user_data = await self._safe_get_user(update.effective_user.id)
        if not user_data:
            await update.message.reply_text("❌ 用户不存在，请先使用 /start")
            return None
        return user_data
    
    def get_command_handlers(self) -> Dict[str, callable]:
        """获取此处理器提供的命令处理方法映射
        
        子类应该重写此方法返回 {command_name: handler_method} 的字典
        """
        return {} 