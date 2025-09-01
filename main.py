#!/usr/bin/env python3
"""
重构后的Telegram Bot主启动文件
"""

import asyncio
import logging
import signal
import socket
from contextlib import closing
from typing import Optional
import os

from src.utils.config.settings import get_settings
from src.core.container import setup_container
from src.interfaces.telegram.bot import TelegramBot


class BotApplication:
    """Bot应用管理类"""
    
    def __init__(self):
        self.settings = get_settings()
        self.container = setup_container(self.settings)
        self.telegram_bot: Optional[TelegramBot] = None
        self.logger = logging.getLogger(__name__)
        
        # 设置日志
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 确保日志目录存在
        os.makedirs('logs', exist_ok=True)
        
        # 配置日志格式和处理器
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            format=log_format,
            level=logging.INFO,
            handlers=[
                logging.FileHandler('logs/bot_v1.log'),
                logging.StreamHandler()
            ]
        )
        
        # 设置第三方库日志级别
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('telegram').setLevel(logging.WARNING)
    
    async def initialize(self):
        """初始化应用"""
        try:
            self.logger.info("🚀 正在初始化AI图像处理Bot...")
            
            # 初始化数据库
            db_manager = self.container.get("supabase_manager")
            await db_manager.initialize()
            self.logger.info("✅ 数据库初始化完成")
            
            # 获取Telegram Bot实例
            self.telegram_bot = self.container.get("telegram_bot")
            self.logger.info("✅ Telegram Bot实例创建完成")
            
            # 获取支付webhook处理器
            self.payment_webhook = self.container.get("payment_webhook_handler")
            self.logger.info("✅ 支付回调处理器创建完成")
            
            # 获取图片webhook处理器
            self.image_webhook = self.container.get("image_webhook_handler")
            self.logger.info("✅ 图片回调处理器创建完成")
            
            # 构建Bot应用
            self.telegram_bot.build_application()
            self.logger.info("✅ Bot应用构建完成")
            
            self.logger.info("🎉 应用初始化成功")
            
        except Exception as e:
            self.logger.error(f"❌ 应用初始化失败: {e}")
            raise

    def _find_available_port(self, start_port: int = 5002, max_attempts: int = 10) -> int:
        """🔧 新增：查找可用端口"""
        for port in range(start_port, start_port + max_attempts):
            try:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                    sock.bind(('', port))
                    return port
            except OSError:
                continue
        raise RuntimeError(f"无法找到可用端口，尝试范围: {start_port}-{start_port + max_attempts - 1}")

    async def start(self):
        """启动应用"""
        try:
            await self.initialize()
            
            self.logger.info("🤖 正在启动Telegram Bot...")

            # 🔧 修复：动态查找可用端口
            payment_webhook_port = self._find_available_port(5002, 10)
            self.logger.info(f"🔍 找到支付回调可用端口: {payment_webhook_port}")
            
            image_webhook_port = self._find_available_port(5003, 10)
            self.logger.info(f"🔍 找到图片回调可用端口: {image_webhook_port}")
            
            # 启动支付回调服务器（在后台线程中）- 使用动态端口避免冲突
            import threading
            payment_webhook_thread = threading.Thread(
                target=self.payment_webhook.run,
                kwargs={'host': '0.0.0.0', 'port': payment_webhook_port, 'debug': False},
                daemon=True
            )
            payment_webhook_thread.start()
            self.logger.info(f"🌐 支付回调服务器已启动 (端口{payment_webhook_port})")
            
            # 启动图片回调服务器（在后台线程中）- 使用动态端口避免冲突
            image_webhook_thread = threading.Thread(
                target=self.image_webhook.run,
                kwargs={'host': '0.0.0.0', 'port': image_webhook_port, 'debug': False},
                daemon=True
            )
            image_webhook_thread.start()
            self.logger.info(f"🖼️ 图片回调服务器已启动 (端口{image_webhook_port})")
            
            # 启动Telegram Bot
            await self.telegram_bot.start()
            
            self.logger.info("✅ Bot启动成功，等待用户消息...")
            self.logger.info(f"📊 配置信息:")
            self.logger.info(f"   - Bot Token: {'已配置' if self.settings.bot.token else '❌ 未配置'}")
            self.logger.info(f"   - 数据库: Supabase ({self.settings.database.supabase_url})")
            self.logger.info(f"   - 管理员ID: {getattr(self.settings.bot, 'admin_user_id', '未设置')}")
            self.logger.info(f"   - 支付回调: http://localhost:{payment_webhook_port}/payment/notify")
            self.logger.info(f"   - 图片回调: http://localhost:{image_webhook_port}/webhook/image-process")
            
            # 等待停止信号
            await asyncio.Event().wait()
            
        except KeyboardInterrupt:
            self.logger.info("🛑 接收到停止信号")
        except Exception as e:
            self.logger.error(f"❌ Bot运行异常: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """停止应用"""
        try:
            self.logger.info("🛑 正在停止应用...")
            
            if self.telegram_bot:
                await self.telegram_bot.stop()
                self.logger.info("✅ Telegram Bot已停止")
            
            # 关闭数据库连接
            db_manager = self.container.get("supabase_manager")
            await db_manager.close()
            self.logger.info("✅ 数据库连接已关闭")
            
            self.logger.info("👋 应用已完全停止")
            
        except Exception as e:
            self.logger.error(f"❌ 停止应用时发生错误: {e}")


async def main():
    """主入口函数"""
    app = BotApplication()
    await app.start()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}") 