#!/usr/bin/env python3
"""
简单的性能测试脚本
通过启动bot并发送/start命令来测试性能
"""

import asyncio
import time
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceTestBot:
    """性能测试Bot"""
    
    def __init__(self, token: str):
        self.token = token
        self.application = None
        self.start_times = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start命令并记录性能"""
        user_id = update.effective_user.id
        start_time = time.time()
        self.start_times[user_id] = start_time
        
        logger.info(f"⏱️  [PERF] 开始: start_command_{user_id} - 处理 /start 命令")
        
        # 模拟用户注册过程
        await asyncio.sleep(0.1)  # 模拟数据库操作
        logger.info(f"⏱️  [PERF] 检查点: start_command_{user_id}.user_registration - 开始用户注册 | 已耗时: 0.100s")
        
        await asyncio.sleep(0.5)  # 模拟用户注册耗时
        logger.info(f"⏱️  [PERF] 检查点: start_command_{user_id}.user_registered - 用户注册完成 | 已耗时: 0.600s")
        
        await asyncio.sleep(0.1)  # 模拟构建消息
        logger.info(f"⏱️  [PERF] 检查点: start_command_{user_id}.building_welcome - 构建欢迎消息 | 已耗时: 0.700s")
        
        await asyncio.sleep(0.1)  # 模拟创建键盘
        logger.info(f"⏱️  [PERF] 检查点: start_command_{user_id}.creating_keyboard - 创建主菜单键盘 | 已耗时: 0.800s")
        
        await asyncio.sleep(0.1)  # 模拟发送消息
        logger.info(f"⏱️  [PERF] 检查点: start_command_{user_id}.sending_message - 发送欢迎消息 | 已耗时: 0.900s")
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        logger.info(f"⏱️  [PERF] 完成: start_command_{user_id} - 处理 /start 命令 | 耗时: {total_duration:.3f}s")
        
        await update.message.reply_text(f"✅ 测试完成！总耗时: {total_duration:.3f}秒")
    
    async def run_test(self):
        """运行性能测试"""
        try:
            # 创建应用
            self.application = Application.builder().token(self.token).build()
            
            # 添加命令处理器
            self.application.add_handler(CommandHandler("start", self.start_command))
            
            # 启动应用
            logger.info("启动性能测试Bot...")
            await self.application.initialize()
            await self.application.start()
            
            logger.info("Bot已启动，请发送 /start 命令进行测试")
            logger.info("按 Ctrl+C 停止测试")
            
            # 保持运行
            await asyncio.Event().wait()
            
        except KeyboardInterrupt:
            logger.info("测试停止")
        except Exception as e:
            logger.error(f"测试失败: {e}")
        finally:
            if self.application:
                await self.application.stop()
                await self.application.shutdown()

async def main():
    """主函数"""
    # 这里需要替换为实际的Bot Token
    token = "YOUR_BOT_TOKEN_HERE"
    
    if token == "YOUR_BOT_TOKEN_HERE":
        logger.error("请先设置正确的Bot Token")
        return
    
    bot = PerformanceTestBot(token)
    await bot.run_test()

if __name__ == "__main__":
    asyncio.run(main())
