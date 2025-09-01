"""
回调管理器 - 简化版本
只处理基本的回调分发，移除复杂的熔断和监控机制
"""

import logging
from typing import Dict, Callable

from telegram import Update
from telegram.ext import ContextTypes

from .callback.function_callbacks import FunctionCallbackHandler
from .callback.profile_callbacks import ProfileCallbackHandler
from .callback.payment_callbacks import PaymentCallbackHandler
from .callback.image_generation_callbacks import ImageGenerationCallbackHandler


class CallbackManager:
    """简化的回调管理器"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.logger = logging.getLogger(__name__)
        
        # 服务依赖
        self.user_service = bot_instance.user_service
        self.image_service = bot_instance.image_service
        self.payment_service = bot_instance.payment_service
        # 新增会话和行为记录服务
        self.session_service = bot_instance.session_service
        self.action_record_service = bot_instance.action_record_service
        
        # 初始化各种回调处理器
        self.function_handler = FunctionCallbackHandler(bot_instance)
        self.profile_handler = ProfileCallbackHandler(bot_instance)
        self.payment_handler = PaymentCallbackHandler(bot_instance)
        self.image_generation_handler = ImageGenerationCallbackHandler(bot_instance)
        
        # 构建回调映射表
        self.callback_mapping = self._build_callback_mapping()
    
    def _build_callback_mapping(self) -> Dict[str, Callable]:
        """构建回调数据到处理方法的映射表"""
        mapping = {}
        
        # 添加各种处理器的回调映射
        handlers = [
            self.function_handler,
            self.profile_handler,
            self.payment_handler,
            self.image_generation_handler
        ]
        
        for handler in handlers:
            handler_mapping = handler.get_callback_handlers()
            for prefix, method in handler_mapping.items():
                mapping[prefix] = method
        
        self.logger.info(f"构建回调映射完成，总共 {len(mapping)} 个回调处理器")
        return mapping
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """统一的回调查询处理入口"""
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id
        
        # 应答回调查询
        try:
            await query.answer()
        except Exception as e:
            self.logger.error(f"应答回调查询失败: {e}")
        
        self.logger.info(f"收到回调: {data} from user {user_id}")
        
        # 记录用户行为：点击回调按钮
        try:
            user_data = await self.user_service.get_user_by_telegram_id(user_id)
            if user_data:
                session = await self.session_service.get_or_create_session(user_data['id'])
                if session:
                    await self.action_record_service.record_action(
                        user_id=user_data['id'],
                        session_id=session['session_id'],
                        action_type='callback_query',
                        parameters={'callback_data': data},
                        message_context=f'用户点击回调按钮: {data}'
                    )
        except Exception as e:
            self.logger.error(f"记录回调行为失败: {e}")
        
        # 清除等待UID状态（如果用户点击其他按钮）
        try:
            from ..user_state_manager import States
            current_state = self.bot.state_manager.get_current_state(user_id)
            if current_state == States.WAITING_UID_INPUT:
                self.logger.info(f"用户 {user_id} 正在等待UID输入，但点击了其他功能，清除状态")
                self.bot.state_manager.reset_user_state(user_id)
        except Exception as e:
            self.logger.error(f"检查/清除用户状态失败: {e}")
        
        try:
            # 查找并调用处理器
            handler_method = self._find_handler(data)
            
            if handler_method:
                # 检查是否需要参数
                if self._needs_parameters(data):
                    parameters = self._extract_parameters(data)
                    await handler_method(query, context, *parameters)
                else:
                    await handler_method(query, context)
            else:
                self.logger.warning(f"未找到处理器: {data}")
                await self._handle_unknown_callback(query)
                
        except Exception as e:
            self.logger.error(f"处理回调查询失败: {data}, 错误: {e}")
            await self._handle_callback_error(query, user_id)
    
    def _find_handler(self, callback_data: str) -> Callable:
        """查找匹配的回调处理器"""
        # 直接匹配
        if callback_data in self.callback_mapping:
            return self.callback_mapping[callback_data]
        
        # 前缀匹配 - 处理带参数的回调
        for prefix, handler in self.callback_mapping.items():
            if callback_data.startswith(f"{prefix}_"):
                return handler
        
        return None
    
    async def _handle_unknown_callback(self, query):
        """处理未知的回调"""
        try:
            await query.edit_message_text("❓ 未知操作，请重新选择")
        except Exception as e:
            self.logger.error(f"处理未知回调失败: {e}")
    
    async def _handle_callback_error(self, query, user_id: int):
        """处理回调错误"""
        try:
            # 清除可能的错误状态
            self.bot.state_manager.reset_user_state(user_id)
            
            # 提供简单的错误恢复
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="back_to_main")]
            ]
            
            await query.edit_message_text(
                "❌ 操作遇到问题，已重置状态\n\n点击返回主菜单重新开始",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            self.logger.error(f"错误恢复处理失败: {e}")
            # 最后的保险措施
            try:
                await query.message.reply_text(
                    "❌ 系统遇到问题，请使用 /start 重新开始",
                    reply_markup=self.bot.ui_handler.create_main_menu_keyboard()
                )
            except Exception as e2:
                self.logger.error(f"最终错误恢复也失败: {e2}") 
    
    def _needs_parameters(self, callback_data: str) -> bool:
        """判断回调数据是否包含参数"""
        parameterized_prefixes = [
            "cloth_page_", "pose_page_", "select_cloth_", "select_pose_",
            "set_pref_", "select_package_", "buy_package_", "check_order_",
            "cancel_order_", "pref_", "pay_method_"
        ]
        return any(callback_data.startswith(prefix) for prefix in parameterized_prefixes)
    
    def _extract_parameters(self, callback_data: str) -> list:
        """从回调数据中提取参数"""
        if callback_data.startswith("cloth_page_"):
            page = int(callback_data.replace("cloth_page_", ""))
            return [page]
        elif callback_data.startswith("pose_page_"):
            page = int(callback_data.replace("pose_page_", ""))
            return [page]
        elif callback_data.startswith("select_cloth_"):
            cloth = callback_data.replace("select_cloth_", "")
            return [cloth]
        elif callback_data.startswith("select_pose_"):
            pose_index = int(callback_data.replace("select_pose_", ""))
            return [pose_index]
        elif callback_data.startswith("pref_"):
            pref_type = callback_data.replace("pref_", "")
            return [pref_type]
        elif callback_data.startswith("set_pref_"):
            return [callback_data]  # 整个数据作为参数传递
        elif callback_data.startswith("select_package_"):
            package_id = callback_data.replace("select_package_", "")
            return [package_id]
        elif callback_data.startswith("buy_package_"):
            # 格式: buy_package_{method_id}_{package_id}
            parts = callback_data.replace("buy_package_", "").split("_", 1)
            if len(parts) == 2:
                return parts
            return []
        elif callback_data.startswith("pay_method_"):
            # 格式: pay_method_{method_id}_{package_id}
            parts = callback_data.replace("pay_method_", "").split("_", 1)
            if len(parts) == 2:
                return parts
            return []
        elif callback_data.startswith("check_order_"):
            order_no = callback_data.replace("check_order_", "")
            return [order_no]
        elif callback_data.startswith("cancel_order_"):
            order_no = callback_data.replace("cancel_order_", "")
            return [order_no]
        
        return [] 