#!/usr/bin/env python3
"""
文字 Bot 独立启动入口（Polling 优先）
原位置：src/app_text_bot.py（将移动到项目根目录与 main.py 同级）
移动后运行方式（在项目根目录）：
  python app_text_bot.py
需要环境变量：TEXT_BOT_TOKEN
"""

import logging
import os
import sys

from dotenv import load_dotenv, find_dotenv

# 优先从当前工作目录查找 .env
load_dotenv(find_dotenv(usecwd=True), override=False)


def _setup_logging() -> None:
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=log_format, level=logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)

    try:
        from src.utils.config.settings import get_text_settings, get_settings
        from src.core.container import setup_container, initialize_global_services
        
        # 1. 加载配置
        text_settings = get_text_settings()
        app_settings = get_settings()  # 加载完整配置（包含 Supabase 配置）
        
        # 基本校验
        if not getattr(text_settings.text_bot, 'token', ''):
            logger.error("❌ TEXT_BOT_TOKEN 未配置。请设置环境变量 TEXT_BOT_TOKEN 再重试。")
            sys.exit(1)
        
        # 2. 初始化依赖注入容器
        container = setup_container(app_settings)
        logger.info("✅ 依赖注入容器已初始化")
        
        # 3. 初始化 Supabase 连接
        import asyncio
        supabase_manager = container.get("supabase_manager")
        asyncio.run(supabase_manager.initialize())
        logger.info("✅ Supabase 连接已初始化")
        
        # 4. 初始化全局服务实例（为了向后兼容其他模块）
        initialize_global_services(container)
        logger.info("✅ 全局服务实例已初始化")
        
        # 5. 从容器获取已配置好的服务
        session_service = container.get("session_service")
        role_service = container.get("role_service")
        snapshot_service = container.get("snapshot_service")
        
        # 6. 创建并启动 Bot（通过构造函数注入依赖）
        from src.interfaces.telegram.text_bot import TextBot
        text_bot = TextBot(
            bot_token=text_settings.text_bot.token,
            role_service=role_service,
            snapshot_service=snapshot_service,
            session_service=session_service
        )

        logger.info("🤖 正在启动文字 Bot（Polling）…")
        text_bot.run()

    except KeyboardInterrupt:
        logger.info("🛑 接收到停止信号，正在退出…")
    except Exception as e:
        logger.exception("❌ 文字 Bot 启动失败: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()


