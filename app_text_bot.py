#!/usr/bin/env python3
"""
文字 Bot 独立启动入口（支持 Metrics Server）
运行方式：
  python app_text_bot.py
需要环境变量：
  TEXT_BOT_TOKEN
  PORT (默认 8000, for Railway)
"""

import logging
import os
import sys
import asyncio
from aiohttp import web
from dotenv import load_dotenv, find_dotenv
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# 优先从当前工作目录查找 .env
load_dotenv(find_dotenv(usecwd=True), override=False)


def _setup_logging() -> None:
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=log_format, level=logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)


async def metrics_handler(request):
    """暴露 Prometheus 指标的端点"""
    try:
        data = generate_latest()
        # prometheus_client 的 CONTENT_TYPE_LATEST 通常包含 charset，
        # 但 aiohttp 的 content_type 参数不允许包含 charset。
        # 我们需要手动解析或直接指定 'text/plain'，并在 charset 参数中指定编码。
        content_type_str = str(CONTENT_TYPE_LATEST).split(';')[0]
        return web.Response(
            body=data,
            content_type=content_type_str,
            charset='utf-8'
        )
    except Exception as e:
        logging.error(f"Metrics generation failed: {e}")
        return web.Response(status=500, text="Metrics generation failed")


async def health_check(request):
    """简单的健康检查"""
    return web.Response(text="OK")


async def start_background_tasks(app):
    """在 Web 服务启动时后台运行 Bot"""
    text_bot = app['text_bot']
    app['bot_task'] = asyncio.create_task(text_bot.start())


async def cleanup_background_tasks(app):
    """清理后台任务"""
    text_bot = app['text_bot']
    await text_bot.stop()
    app['bot_task'].cancel()
    await app['bot_task']


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)

    try:
        from src.utils.config.settings import get_text_settings, get_settings
        from src.core.container import setup_container, initialize_global_services
        
        # 1. 加载配置
        text_settings = get_text_settings()
        app_settings = get_settings()
        
        if not getattr(text_settings.text_bot, 'token', ''):
            logger.error("❌ TEXT_BOT_TOKEN 未配置。")
            sys.exit(1)
        
        # 2. 初始化容器
        container = setup_container(app_settings)
        logger.info("✅ 依赖注入容器已初始化")
        
        # 3. 初始化 Supabase
        supabase_manager = container.get("supabase_manager")
        # 注意：这里不能用 asyncio.run，因为我们将进入 aiohttp 的循环
        # 我们在 app 启动前手动初始化一次 loop 或者在 startup 钩子做
        # 简单起见，这里先同步运行初始化（如果是纯异步库可能需要放到 startup）
        # supabase-py 现在的 initialize 通常是同步或不需要显式 await，如果是 async，则需放入 startup
        # 假设 supabase_manager.initialize() 是 async
        
        # 4. 初始化全局服务
        initialize_global_services(container)
        
        # 5. 获取服务
        session_service = container.get("session_service")
        role_service = container.get("role_service")
        snapshot_service = container.get("snapshot_service")
        
        # 6. 创建 Bot 实例
        from src.interfaces.telegram.text_bot import TextBot
        text_bot = TextBot(
            bot_token=text_settings.text_bot.token,
            role_service=role_service,
            snapshot_service=snapshot_service,
            session_service=session_service
        )

        # 7. 配置 Web Server (Metrics + Health)
        app = web.Application()
        app['text_bot'] = text_bot
        app['supabase_manager'] = supabase_manager
        
        # 注册路由
        app.router.add_get('/', health_check)
        app.router.add_get('/metrics', metrics_handler)
        
        # 注册生命周期钩子
        async def on_startup(app):
            await app['supabase_manager'].initialize()
            logger.info("✅ Supabase 连接已初始化")
            await start_background_tasks(app)
            
        app.on_startup.append(on_startup)
        app.on_cleanup.append(cleanup_background_tasks)
        
        # 8. 启动服务
        port = int(os.getenv("PORT", 8000))
        logger.info(f"🚀 启动 Web Server (端口 {port}) 与 Text Bot...")
        
        # 这种方式适用于 Railway，它会由 aiohttp 接管主进程
        web.run_app(app, port=port, print=None)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception("❌ 启动失败: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
