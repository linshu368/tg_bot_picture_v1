"""
基础回调处理器 - 简化版本
提供最基本的回调处理功能
"""

import logging
from typing import Dict, Any

from telegram import InlineKeyboardMarkup

from ...ui_handler import UIHandler


def robust_callback_handler(func):
    """简化的装饰器：基本的错误处理"""
    async def wrapper(self, query, context, *args, **kwargs):
        try:
            return await func(self, query, context, *args, **kwargs)
        except Exception as e:
            # 简单的错误处理
            self.logger.error(f"回调处理器 {func.__name__} 失败: {e}")
            
            # 重置用户状态
            user_id = query.from_user.id
            if hasattr(self, 'state_manager'):
                self.state_manager.reset_user_state(user_id)
            
            # 发送简单的错误信息
            try:
                await query.edit_message_text("❌ 操作失败，已重置状态")
            except:
                pass
                
            return None
    return wrapper


class BaseCallbackHandler:
    """简化的基础回调处理器"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.logger = logging.getLogger(__name__)
        
        # 依赖注入
        self.ui_handler: UIHandler = bot_instance.ui_handler
       
        
        # 服务依赖
        self.user_service = bot_instance.user_service
        self.image_service = bot_instance.image_service
        self.payment_service = bot_instance.payment_service
    
    async def _safe_get_user(self, user_id: int):
        """安全获取用户信息"""
        try:
            return await self.user_service.get_user_by_telegram_id(user_id)
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {user_id}, 错误: {e}")
            return None
    
    async def _safe_edit_message(self, query, text: str, reply_markup: InlineKeyboardMarkup = None):
        """安全编辑消息"""
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except Exception as e:
            self.logger.error(f"编辑消息失败: {e}")
    
    def get_callback_handlers(self) -> Dict[str, callable]:
        """子类需要实现此方法"""
        raise NotImplementedError("子类必须实现get_callback_handlers方法") 