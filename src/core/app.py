"""
应用核心类
负责整体应用的启动、运行和生命周期管理
"""

import asyncio
import logging
import threading
from typing import Optional

from .container import setup_container
from .lifecycle import LifecycleManager
from src.utils.config.settings import AppSettings


class Application:
    """应用主类"""
    
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.container = setup_container(settings)
        self.lifecycle = LifecycleManager()
        
        # 组件引用
        self.telegram_bot = None
        self.webhook_server = None
        
        self.logger.info("应用实例创建完成")
    
    async def initialize(self):
        """初始化应用组件"""
        self.logger.info("开始初始化应用组件...")
        
        try:
            # 初始化数据库
            db_manager = self.container.get("database_manager")
            await db_manager.initialize()
            self.logger.info("数据库初始化完成")
            
            # 初始化Telegram Bot
            self.telegram_bot = self.container.get("telegram_bot")
            await self.telegram_bot.initialize()
            self.logger.info("Telegram Bot初始化完成")
            
            # 初始化Webhook服务器
            self.webhook_server = self._create_webhook_server()
            self.logger.info("Webhook服务器初始化完成")
            
            # 注册生命周期钩子
            self.lifecycle.register_startup_hook(self._on_startup)
            self.lifecycle.register_shutdown_hook(self._on_shutdown)
            
            self.logger.info("应用组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"应用初始化失败: {e}")
            raise
    
    def _create_webhook_server(self):
        """创建Webhook服务器"""
        from src.infrastructure.messaging.webhook_server import WebhookServer
        return WebhookServer(
            self.settings.bot.webhook_url,
            self.container.get("image_service"),
            self.container.get("payment_service"),
            self.telegram_bot
        )
    
    async def _on_startup(self):
        """启动钩子"""
        self.logger.info("执行启动钩子...")
        # 可以在这里添加启动时需要执行的任务
    
    async def _on_shutdown(self):
        """关闭钩子"""
        self.logger.info("执行关闭钩子...")
        
        # 停止Telegram Bot
        if self.telegram_bot:
            await self.telegram_bot.stop()
        
        # 停止Webhook服务器
        if self.webhook_server:
            await self.webhook_server.stop()
        
        # 关闭数据库连接
        db_manager = self.container.get("database_manager")
        await db_manager.close()
    
    async def run(self):
        """运行应用"""
        try:
            # 初始化
            await self.initialize()
            
            # 执行启动钩子
            await self.lifecycle.run_startup_hooks()
            
            # 启动Webhook服务器（后台线程）
            webhook_thread = threading.Thread(
                target=self.webhook_server.run,
                daemon=True
            )
            webhook_thread.start()
            self.logger.info("Webhook服务器已启动")
            
            # 启动Telegram Bot（主线程）
            self.logger.info("启动Telegram Bot...")
            await self.telegram_bot.run()
            
        except Exception as e:
            self.logger.error(f"应用运行失败: {e}")
            raise
        finally:
            # 执行关闭钩子
            await self.lifecycle.run_shutdown_hooks()
            self.logger.info("应用已停止") 