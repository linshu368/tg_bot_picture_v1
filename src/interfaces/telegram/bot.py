"""
重构后的Telegram Bot主类
整合所有细分的处理器模块，提供清晰的架构
"""

import logging
import asyncio
from typing import Dict, Any, Optional

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler as TelegramMessageHandler, CallbackQueryHandler, ContextTypes, filters

from src.domain.services.user_service import UserService
from src.domain.services.image_service import ImageService
from src.domain.services.payment_service import PaymentService
from src.domain.services.session_service import SessionService
from src.domain.services.action_record_service import ActionRecordService
from src.domain.services.system_config_service import SystemConfigService
from src.infrastructure.messaging.webhook_handler import WebhookProcessor
from src.infrastructure.external_apis.clothoff_api import ClothOffAPI

from .ui_handler import UIHandler
from .user_state_manager import UserStateManager, UserStateHelper
from .handlers.command import UserCommandHandler, AdminCommandHandler, PaymentCommandHandler
from .handlers.message_handlers import MessageHandler
from .handlers.callback_manager import CallbackManager


class TelegramBotRefactored:
    """重构后的Telegram Bot主类"""
    
    def __init__(self, 
                 bot_token: str,
                 user_service: UserService,
                 image_service: ImageService,
                 payment_service: PaymentService,
                 webhook_processor: WebhookProcessor,
                 clothoff_api: ClothOffAPI,
                 session_service: SessionService,  # 新增
                 action_record_service: ActionRecordService,  # 新增
                 system_config_service: SystemConfigService,  # 新增
                 admin_user_id: int = None):
        self.bot_token = bot_token
        self.user_service = user_service
        self.image_service = image_service
        self.payment_service = payment_service
        self.webhook_processor = webhook_processor
        self.clothoff_api = clothoff_api
        self.session_service = session_service  # 新增
        self.action_record_service = action_record_service  # 新增
        self.system_config_service = system_config_service  # 新增
        self.admin_user_id = admin_user_id
        
        self.logger = logging.getLogger(__name__)
        self.app: Optional[Application] = None
        
        # 初始化核心组件
        self._initialize_core_components()
        
        # 初始化处理器
        self._initialize_handlers()
    
    def _initialize_core_components(self):
        """初始化核心组件"""
        self.state_manager = UserStateManager()
        self.state_helper = UserStateHelper(self.state_manager)
        self.ui_handler = UIHandler()
    
    def _initialize_handlers(self):
        """初始化各种处理器"""
        # 命令处理器
        self.user_command_handler = UserCommandHandler(self)
        self.admin_command_handler = AdminCommandHandler(self, self.admin_user_id)
        self.payment_command_handler = PaymentCommandHandler(self)
        
        # 消息处理器
        self.message_handler = MessageHandler(self)
        
        # 回调管理器
        self.callback_manager = CallbackManager(self)
    
    def build_application(self) -> Application:
        """构建Telegram应用"""
        if self.app is not None:
            return self.app
            
        self.app = ApplicationBuilder().token(self.bot_token).build()
        
        # 注册处理器
        self._register_command_handlers()
        self._register_message_handlers()
        self._register_callback_handlers()
        
        self.logger.info(f"Telegram Bot应用构建完成，处理器数量: {len(self.app.handlers)}")
        return self.app
    
    def _register_command_handlers(self):
        """注册命令处理器"""
        # 收集所有命令处理器
        command_handlers = {}
        
        # 用户命令
        command_handlers.update(self.user_command_handler.get_command_handlers())
        
        # 管理员命令
        command_handlers.update(self.admin_command_handler.get_command_handlers())
        
        # 支付相关命令
        command_handlers.update(self.payment_command_handler.get_command_handlers())
        
        # 注册到应用
        for command, handler in command_handlers.items():
            self.app.add_handler(CommandHandler(command, handler))
            self.logger.debug(f"注册命令处理器: /{command}")
        
        self.logger.info(f"注册了 {len(command_handlers)} 个命令处理器")
    
    def _register_message_handlers(self):
        """注册消息处理器"""
        # 图片消息处理
        self.app.add_handler(TelegramMessageHandler(filters.PHOTO, self.message_handler.handle_photo_message))
        
        # 文本消息处理
        self.app.add_handler(TelegramMessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.message_handler.handle_text_message
        ))
        
        self.logger.debug("消息处理器注册完成")
    
    def _register_callback_handlers(self):
        """注册回调处理器"""
        self.app.add_handler(CallbackQueryHandler(self.callback_manager.handle_callback_query))
        self.logger.debug("回调处理器注册完成")
    
    # 运行和管理方法
    async def start(self):
        """启动Bot"""
        if not self.app:
            self.build_application()
        
        self.logger.info("正在启动Telegram Bot...")
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        
        self.logger.info("Telegram Bot启动成功")
    
    async def stop(self):
        """停止Bot"""
        try:
            if self.app:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                self.logger.info("✅ Bot已停止")
        except Exception as e:
            self.logger.error(f"❌ 停止Bot失败: {e}")
    
    async def send_message_to_user(self, telegram_id: int, message: str):
        """发送消息给指定用户"""
        try:
            if self.app and self.app.bot:
                await self.app.bot.send_message(
                    chat_id=telegram_id, 
                    text=message
                )
            else:
                # 创建临时bot发送
                from telegram import Bot
                temp_bot = Bot(token=self.bot_token)
                await temp_bot.send_message(
                    chat_id=telegram_id, 
                    text=message
                )
                
            self.logger.info(f"消息发送成功: {telegram_id}")
            
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
    
    async def run(self):
        """运行Bot（阻塞方式）"""
        try:
            await self.start()
            # 保持运行
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            self.logger.info("接收到停止信号")
        finally:
            await self.stop()


# 为了保持向后兼容性，创建一个别名
TelegramBot = TelegramBotRefactored 