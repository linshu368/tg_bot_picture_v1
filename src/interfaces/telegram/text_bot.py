import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


class TextBot:
    """最小文字Bot：仅支持 /start 与文本回声

    支持两种启动方式：
    - run(): 同步方式，内部管理事件循环（适合快速本地验证）
    - start()/stop(): 异步方式，便于与现有异步应用编排
    """

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.logger = logging.getLogger(__name__)
        self._application: Optional[Application] = None

    # ------------------------
    # Public APIs
    # ------------------------
    def run(self) -> None:
        """同步运行，使用 polling 方式"""
        app = self._build_application()
        self.logger.info("🤖 TextBot 以 polling 模式启动（同步）")
        app.run_polling()  # 默认关闭 loop，避免残留问题

    async def start(self) -> None:
        """异步启动（polling）"""
        app = self._build_application()
        self.logger.info("🤖 TextBot 以 polling 模式启动（异步）")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()  # 简化逻辑，直接使用 updater

    async def stop(self) -> None:
        """异步停止并清理资源"""
        if not self._application:
            return
        app = self._application
        self.logger.info("🛑 TextBot 停止中…")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        self.logger.info("✅ TextBot 已停止")

    # ------------------------
    # Internal helpers
    # ------------------------
    def _build_application(self) -> Application:
        if self._application is not None:
            return self._application

        if not self.bot_token:
            raise ValueError("TEXT_BOT_TOKEN 未配置")

        app = ApplicationBuilder().token(self.bot_token).build()

        # 注册命令与消息处理器
        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))

        self._application = app
        return app

    # ------------------------
    # Handlers
    # ------------------------
    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.message is None:
            return
        user_first_name = update.effective_user.first_name or ""
        self.logger.info("📥 /start user_id=%s name=%s", update.effective_user.id, user_first_name)
        await update.message.reply_text(
            """让AI为你提供理想陪伴：
• 💕 甜蜜的恋爱互动
• 💌 深夜的暧昧幻想
• 📝 令人社保的文爱体验
• 💫 或任何你想要的剧情...

✨ 独特体验：
• 海量精品角色等你来选（/list 查看角色世界）
• 支持上传自定义角色，打造你的理想女/男友（/create 创建角色）
• 细腻的文字描写能力，对话自然动人
• 支持语音交互，可自定义声优
• 支持白嫖，签到拉人均可获取积分，价格也不贵

🎮 开始体验:
1. 直接发送消息即可与默认女友"塞拉芬娜"对话
2. 使用/list 查看角色列表，或在角色卡频道选择更多角色（高级用户：可发送酒馆v2 PNG格式角色卡来导入你喜欢的角色）
3. 输入"/"查看所有互动指令”"""
        )

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or not update.message.text:
            return
        self.logger.info("📥 消息 user_id=%s text=%s", update.effective_user.id, update.message.text)
        await update.message.reply_text(update.message.text)


