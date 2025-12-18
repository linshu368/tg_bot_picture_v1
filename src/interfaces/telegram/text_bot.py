import logging
import os
import asyncio
import time
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from src.interfaces.telegram.handlers.callback.text_bot_callback_handler import TextBotCallbackHandler
from src.interfaces.telegram.ui_handler import UIHandler
from src.infrastructure.monitoring.metrics import BOT_RESPONSE_FAILURE_TOTAL
from src.core.services.stream_message_service import FALLBACK_ERROR_MESSAGE


class DummyService:
    def __getattr__(self, item):
        return lambda *args, **kwargs: None

class TextBot:
    """最小文字Bot：仅支持 /start 与文本回声

    支持两种启动方式：
    - run(): 同步方式，内部管理事件循环（适合快速本地验证）
    - start()/stop(): 异步方式，便于与现有异步应用编排
    """

    def __init__(self, bot_token: str, role_service=None, snapshot_service=None, session_service=None):
        """
        初始化 TextBot
        
        Args:
            bot_token: Bot Token
            role_service: 角色服务实例（通过容器注入）
            snapshot_service: 快照服务实例（通过容器注入）
            session_service: 会话服务实例（通过容器注入）
        """
        self.bot_token = bot_token
        self.logger = logging.getLogger(__name__)
        self._application: Optional[Application] = None
        self.ui_handler = UIHandler()
        
        # 依赖注入的服务
        self.role_service = role_service
        self.snapshot_service = snapshot_service
        self.session_service = session_service
        
        self.default_role_id = "46" #默认角色ID
        # 从环境变量读取角色频道URL，根据MODE选择默认值
        mode = os.getenv("MODE", "staging")
        default_role_url = "https://t.me/ai_role_list" if mode == "production" else "https://t.me/ai_role_list_test"
        self.role_channel_url = os.getenv("ROLE_CHANNEL_URL", default_role_url)
        # ✅ 最小占位依赖，避免 BaseCallbackHandler 报错
        self.state_manager = DummyService()
        self.state_helper = DummyService()
        self.user_service = DummyService()
        self.image_service = DummyService()
        self.payment_service = DummyService()
        self.action_record_service = DummyService()
        # --------------------------------------------------
        self.callback_handler = TextBotCallbackHandler(self)
        # 用于保存快照命名的临时状态：user_id -> {session_id}
        self.pending_snapshot = {}
    
    def _get_role_predefined_message(self, role: Dict[str, Any]) -> str:
        """
        从角色数据中提取预置消息
        
        Args:
            role: 角色数据字典
            
        Returns:
            预置消息内容，如果不存在则返回默认消息
        """
        # 从 history 字段的第一条消息获取预置对话
        history = role.get("history", [])
        if history and len(history) > 0:
            first_message = history[0]
            if isinstance(first_message, dict) and first_message.get("role") == "assistant":
                return first_message.get("content", "你好！")
        
        # 降级兜底
        return "你好！"
        
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

        # 允许并发处理更新，以便在一条消息处理中时，下一条消息能及时进入过滤并发送提示
        app = ApplicationBuilder().token(self.bot_token).concurrent_updates(True).build()

        # 注册命令与消息处理器
        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))

        app.add_handler(CallbackQueryHandler(self._on_callback_dispatch))  
              
        self._application = app
        return app

    # ------------------------
    # Handlers
    # ------------------------
    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.message is None:
            return

        user_id = str(update.effective_user.id)
        user_first_name = update.effective_user.first_name or ""
        self.logger.info("📥 /start user_id=%s name=%s", user_id, user_first_name)
        
        # 解析 Deep Link 参数
        deep_link_param = context.args[0] if context.args else None
        self.logger.info(f"📥 Deep Link参数: {deep_link_param}")
        
        # 情况C：Deep Link 快照预览
        if deep_link_param and deep_link_param.startswith("snap_"):
            snapshot_id = deep_link_param.replace("snap_", "")
            self.logger.info(f"🔍 打开快照预览: snapshot_id={snapshot_id}")
            await self._handle_snapshot_preview(update, context, user_id, snapshot_id)
            return
        
        # 情况B：Deep Link 角色切换
        if deep_link_param and deep_link_param.startswith("role_"):
            role_id = deep_link_param.replace("role_", "")
            self.logger.info(f"🔄 Deep Link角色切换: role_id={role_id}")
            
            # 1. 校验角色存在
            role = self.role_service.get_role_by_id(role_id)
            
            if role:
                # 2. 创建新会话并绑定指定角色（强制替换旧会话）
                session = await self.session_service.new_session(user_id, role_id)
                self.logger.info(f"✅ 创建新会话: session_id={session['session_id']}, role_id={role_id}")
                
                # 3. 发送角色切换提示 + 角色卡预览（合并消息）
                main_menu = self.ui_handler.create_main_menu_keyboard()
                post_link = role.get("post_link")
                
                if post_link:
                    try:
                        # 将切换提示作为链接文本，触发角色卡预览
                        await update.message.reply_text(
                            f"<a href=\"{post_link}\">回到角色卡频道</a>",
                            parse_mode="HTML",
                            reply_markup=main_menu,
                            disable_web_page_preview=False
                        )
                    except Exception as e:
                        self.logger.error(f"❌ 发送角色卡预览失败: {e}")
                        # 降级方案：分开发送
                        await update.message.reply_text(
                            "回到角色卡频道", 
                            reply_markup=main_menu
                        )
                        await update.message.reply_text(
                            post_link,
                            disable_web_page_preview=False
                        )
                else:
                    # 没有 post_link 时的普通提示
                    await update.message.reply_text(
                        "回到角色卡频道", 
                        reply_markup=main_menu
                    )
                
                # 5. 发送角色预置消息
                predefined_msg = self._get_role_predefined_message(role)
                await update.message.reply_text(predefined_msg)
            else:
                # 角色不存在，降级到默认角色
                self.logger.warning(f"⚠️ 角色不存在: role_id={role_id}，使用默认角色")
                await update.message.reply_text(f"❌ 角色不存在，使用默认角色")
                
                # 使用默认角色创建会话
                session = await self.session_service.new_session(user_id, self.default_role_id)
                role = self.role_service.get_role_by_id(self.default_role_id)
                if role:
                    predefined_msg = self._get_role_predefined_message(role)
                    await update.message.reply_text(predefined_msg)
        
        # 情况A：正常启动（无参数），使用默认角色
        else:
            self.logger.info(f"🆕 正常启动，使用默认角色: role_id={self.default_role_id}")
            
            # 1. 发送通用欢迎语（带底部主菜单和角色图鉴按钮）
            main_menu = self.ui_handler.create_main_menu_keyboard()
            role_gallery_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 浏览角色图鉴", url=self.role_channel_url)]
            ])
            # 创建组合键盘：底部键盘 + 内联键盘
            combined_message = await update.message.reply_text(
                """让AI为你提供理想陪伴：
• 💕 甜蜜的恋爱互动
• 💌 深夜的暧昧幻想
• 📝 令人社保的文爱体验
• 💫 或任何你想要的剧情...

✨ 独特体验：
• 海量精品角色等你来选
• 细腻的文字描写能力，对话自然动人


🎮 开始体验:
1. 直接发送消息即可以和角色对话
2. 点击「选择角色」 查看角色图鉴，选择更多角色

当前为试运营阶段，每天可免费交互30轮次

📚 点击下方按钮选择各种角色""",
                reply_markup=role_gallery_keyboard
            )
            
            # 发送一条空消息来设置底部键盘
            await update.message.reply_text(
                "🍬 已进入对话 ⬇️",
                reply_markup=main_menu
            )
            
            # 2. 创建会话并绑定默认角色
            session = await self.session_service.create_session_with_role(user_id, self.default_role_id)
            self.logger.info(f"✅ 创建会话: session_id={session['session_id']}, role_id={self.default_role_id}")
            
            # 3. 获取默认角色数据
            role = self.role_service.get_role_by_id(self.default_role_id)
            
            # 4. 发送默认角色卡预览（如果有post_link）
            if role:
                post_link = role.get("post_link")
                if post_link:
                    try:
                        # 发送角色卡预览
                        await update.message.reply_text(
                            f"<a href=\"{post_link}\">回到角色卡频道</a>",
                            parse_mode="HTML",
                            disable_web_page_preview=False
                        )
                    except Exception as e:
                        self.logger.error(f"❌ 发送默认角色卡预览失败: {e}")
                        # 降级方案：直接发送链接
                        await update.message.reply_text(
                            post_link,
                            disable_web_page_preview=False
                        )
                
                # 5. 发送默认角色预置消息
                predefined_msg = self._get_role_predefined_message(role)
                await update.message.reply_text(predefined_msg)
            else:
                await update.message.reply_text("❌ 默认角色不存在")

    async def _handle_snapshot_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, snapshot_id: str) -> None:
        """通过 deeplink 打开某个快照的预览：角色卡预览 + 最后一条消息 + 操作按钮"""
        try:
            snap = await self.snapshot_service.get_snapshot(user_id=user_id, snapshot_id=snapshot_id)
        except Exception as e:
            self.logger.error(f"❌ 获取快照失败: {e}")
            await update.message.reply_text("❌ 获取快照失败")
            return

        if not snap:
            await update.message.reply_text("❌ 快照不存在或无权访问")
            return

        role_id = snap.get("role_id")
        role = self.role_service.get_role_by_id(role_id) if role_id else None

        # 1) 角色卡预览（如有）
        post_link = role.get("post_link") if role else None
        if post_link:
            try:
                await update.message.reply_text(
                    f"<a href=\"{post_link}\">回到角色卡频道</a>",
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )
            except Exception as e:
                self.logger.error(f"❌ 发送角色卡预览失败: {e}")
                await update.message.reply_text(post_link, disable_web_page_preview=False)

        # 2) 发送最后一条消息（不截断）
        messages = snap.get("messages", [])
        if messages:
            last_msg = messages[-1]
            content = last_msg.get("content", "")
            preview_text = f"最新对话:\n{content}"
            await update.message.reply_text(preview_text)

        # 3) 操作键盘：继续聊天 / 删除记忆
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("继续聊天", callback_data=f"open_snapshot:{snapshot_id}"),
                InlineKeyboardButton("删除记忆", callback_data=f"delete_snapshot:{snapshot_id}"),
            ]
        ])
        await update.message.reply_text("请选择要进行的操作", reply_markup=keyboard)

    # -------------------------
    # 消息处理
    # -------------------------
    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or not update.message.text:
            return
        
        # ⏱️ T1: 记录起始时间（用户发送消息到达 bot 的时刻）
        start_time = time.time()
        
        user_id = str(update.effective_user.id) if update.effective_user else "unknown"
        content = update.message.text
        self.logger.info("📥 消息 user_id=%s text=%s", user_id, content)

        # 🆕 最早时刻埋点：收到用户文本消息即上报（仅 user_id 与 timestamp）
        try:
            from datetime import datetime, timezone
            from src.infrastructure.analytics.analytics import track_event_background as _track_bg, is_enabled as _analytics_enabled
            if _analytics_enabled():
                self.logger.info("📊 埋点触发: event=message_received user_id=%s", user_id)
                # 若在此处无法获取会话与角色，则传空字符串
                session_id = ""
                role_id = ""
                _track_bg(
                    distinct_id=str(user_id),
                    event="message_received",
                    properties={
                        # "timestamp": datetime.now(timezone.utc).isoformat(),
                        "session_id": session_id,
                        "role_id": role_id
                    }
                )
            else:
                self.logger.info("📊 埋点未启用: 跳过 event=message_received user_id=%s", user_id)
        except Exception as _e:
            # 任何异常不得影响主流程
            self.logger.debug(f"analytics skipped: {_e}")

        # 🆕 导入用户状态管理器
        from src.core.services.user_processing_state import user_processing_state
        # 🆕 先基于消息发送时间做窗口过滤：忽略在上一/当前处理窗口内发送的消息
        try:
            msg_dt = update.message.date  # Telegram 提供UTC时间
            if await user_processing_state.should_ignore_message(user_id, msg_dt):
                warning_msg = await update.message.reply_text("⏳ 请等待上一条消息完成")
                asyncio.create_task(self._delete_message_after_delay(
                    context.bot, warning_msg.chat_id, warning_msg.message_id, 30
                ))
                self.logger.info(f"🚫 用户 {user_id} 消息被忽略（属于处理窗口期间发送）: {content}")
                return
        except Exception as _e:
            self.logger.debug(f"ignore-window check skipped: {_e}")
        
        # 🆕 直接尝试获取处理锁；若失败（并发竞争）则提示并返回
        if not await user_processing_state.start_processing(user_id):
            warning_msg = await update.message.reply_text("⏳ 请等待上一条消息完成")
            asyncio.create_task(self._delete_message_after_delay(
                context.bot, warning_msg.chat_id, warning_msg.message_id, 30
            ))
            self.logger.info(f"🚫 用户 {user_id} 消息被忽略（加锁失败并发竞争）: {content}")
            return

        try:
            # 命名态拦截：优先处理保存快照命名
            if self.pending_snapshot.get(user_id):
                session_id = self.pending_snapshot[user_id].get("session_id")
                try:
                    title = content.strip() if content.strip() else "未命名"
                    snapshot_id = await self.snapshot_service.save_snapshot(user_id=user_id, session_id=session_id, user_title=title)
                    self.logger.info(f"✅ 快照已保存(命名): snapshot_id={snapshot_id}")
                    await update.message.reply_text("✅ 保存成功，可在主菜单点击「🗂 历史聊天」查看保存结果。也可直接发送消息继续对话")
                except Exception as e:
                    self.logger.error(f"❌ 保存快照失败(命名): {e}")
                    await update.message.reply_text("❌ 保存失败，请重试")
                finally:
                    self.pending_snapshot.pop(user_id, None)
                return

            # 处理底部主菜单按钮
            if content == "🎭 选择角色":
                await self._handle_role_selection(update, user_id)
                return
            elif content == "🗂 历史聊天":
                await self._handle_history_list(update, context, user_id)
                return
            elif content == "⚙️ 设置":
                await self._handle_settings(update, user_id)
                return
            elif content == "💳 购买积分":
                # 路由到 /buy 逻辑，最大化复用原有回调链
                try:
                    from src.interfaces.telegram.handlers.command.payment_commands import PaymentCommandHandler
                    payment_cmd = PaymentCommandHandler(self)
                    await payment_cmd.handle_buy_command(update, context)
                except Exception as e:
                    self.logger.error(f"❌ 购买积分入口失败: {e}")
                    await update.message.reply_text("试运营中，积分购买即将开放，敬请期待")
                return
            elif content == "❓ 帮助":
                await self._handle_help(update, user_id)
                return

            # 使用应用层的流式消息服务处理
            from src.core.services.stream_message_service import stream_message_service
            await stream_message_service.handle_stream_message(update, user_id, content, self.ui_handler, start_time=start_time)

        except Exception as e:
            # 🔴 T0: 记录回复失败
            BOT_RESPONSE_FAILURE_TOTAL.labels(error_type=type(e).__name__).inc()
            
            self.logger.error(f"❌ 消息处理失败: {e}")
            try:
                await update.message.reply_text(FALLBACK_ERROR_MESSAGE)
            except:
                pass
        finally:
            # 🆕 确保在所有情况下都释放锁
            await user_processing_state.finish_processing(user_id)

    # 🆕 添加消息自动删除方法
    async def _delete_message_after_delay(self, bot, chat_id, message_id, delay_seconds):
        """延迟删除消息
        
        Args:
            bot: Telegram Bot 实例
            chat_id: 聊天ID
            message_id: 消息ID
            delay_seconds: 延迟时间（秒）
        """
        await asyncio.sleep(delay_seconds)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            self.logger.info(f"🗑️ 已删除提示消息: chat_id={chat_id}, message_id={message_id}")
        except Exception as e:
            self.logger.debug(f"删除消息失败（可能已被删除）: {e}")

    # -------------------------
    # 底部菜单处理方法
    # -------------------------
    
    
    
    async def _handle_help(self, update: Update, user_id: str) -> None:
        """处理帮助"""
        self.logger.info(f"❓ 帮助 user_id={user_id}")
        
        help_text = """❓ **帮助中心**

📚 **功能说明：**

💬 **对话功能**
• 直接发送消息与AI角色对话
• 点击“🎭 选择角色” 查看角色列表
• 点击“🗂 历史聊天” 查看历史聊天记录

⚙️ **设置**
• 点击“⚙️ 设置” 可切换AI回复模式（快餐/剧情）

🔄 **重新生成**
• 对角色回复不满意？点击"🔄 重新生成"按钮

🆕 **新的对话**
• 想要开始新对话？点击"🆕 新的对话"按钮

📞 **联系我们：**
• 遇到问题请联系客服
• 客服Telegram: @Isyuyuya

💡 更多功能开发中，敬请期待...
"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def _handle_settings(self, update: Update, user_id: str) -> None:
        """处理设置菜单"""
        self.logger.info(f"⚙️ 设置菜单 user_id={user_id}")
        
        # 获取当前模式
        current_mode = "immersive"
        if self.session_service and self.session_service.redis_store:
            current_mode = await self.session_service.redis_store.get_user_model_mode(user_id)
        
        mode_text = "🎦 中级模型B"
        if current_mode == "fast":
            mode_text = "🍔 基础模型"
        elif current_mode == "story":
            mode_text = "📖 中级模型A"
            
        text = f"⚙️ **设置中心**\n\n当前模型：**{mode_text}**"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 模型选择", callback_data="settings_model_select")],
            [InlineKeyboardButton("关闭设置", callback_data="close_settings")]
        ])
        
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
    
    async def _handle_history_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str) -> None:
        """历史聊天列表：以 deeplink 链接形式展示最近快照"""
        self.logger.info(f"🗂 历史聊天列表 user_id={user_id}")
        try:
            snapshots = await self.snapshot_service.list_snapshots(user_id)
        except Exception as e:
            self.logger.error(f"❌ 拉取历史聊天失败: {e}")
            await update.message.reply_text("❌ 拉取历史聊天失败，请稍后重试")
            return

        if not snapshots:
            await update.message.reply_text("🗂 暂无历史聊天")
            return

        # 获取 Bot 用户名用于生成 deeplink
        username = getattr(context.bot, "username", None)
        if not username:
            try:
                me = await context.bot.get_me()
                username = me.username
            except Exception:
                username = None

        if not username:
            await update.message.reply_text("❌ 无法生成历史聊天链接（缺少 Bot 用户名配置）")
            return

        # 取前10条，按 created_at 已在服务层倒序
        lines = []
        for s in snapshots[:10]:
            sid = s.get("snapshot_id", "")
            name = s.get("name", sid)
            url = f"https://t.me/{username}?start=snap_{sid}"
            lines.append(f"<a href=\"{url}\">{name}</a>")

        text = "\n".join(lines)
        await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
    
    async def _handle_role_selection(self, update: Update, user_id: str) -> None:
        """处理选择角色"""
        self.logger.info(f"🎭 选择角色 user_id={user_id}")
        
        role_text = """🎭 **选择你的专属角色**

📚 在角色图鉴频道中浏览海量精品角色：
• 🌟 经典人物角色
• 💖 恋爱互动角色
• 🎮 游戏动漫角色
• ✨ 更多精品角色...

💡 点击下方按钮进入角色图鉴频道 👇"""
        
        # 创建内联键盘，带URL按钮
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 浏览角色图鉴", url=self.role_channel_url)]
        ])
        
        await update.message.reply_text(role_text, reply_markup=keyboard, parse_mode='Markdown')

     # -------------------------
    # 回调分发
    # -------------------------
    async def _on_callback_dispatch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if query is None:
            return
        
        raw_data = query.data
        action = raw_data.split(":")[0] if ":" in raw_data else raw_data

        handlers = self.callback_handler.get_callback_handlers()

        self.logger.info(f"📥 收到回调 raw_data={raw_data} 解析action={action}")

        if action in handlers:
            await handlers[action](query, context)
        else:
            # 支付相关回调前缀匹配（兼容形如 select_package_xxx / buy_package_method_pkg）
            try:
                from src.interfaces.telegram.handlers.callback.payment_callbacks import PaymentCallbackHandler
                pay_handler = PaymentCallbackHandler(self)
                
                data = raw_data
                if data == "buy_credits":
                    await pay_handler.handle_buy_credits_callback(query, context)
                    return
                if data.startswith("select_package_"):
                    package_id = data.replace("select_package_", "", 1)
                    await pay_handler.handle_package_selection(query, context, package_id)
                    return
                if data.startswith("buy_package_"):
                    # buy_package_{method_id}_{package_id}
                    parts = data.split("_", 3)
                    # parts: ["buy", "package", method_id, package_id]
                    if len(parts) >= 4:
                        method_id = parts[2]
                        package_id = parts[3]
                        await pay_handler.handle_package_purchase(query, context, method_id, package_id)
                        return
                if data.startswith("check_order_"):
                    order_no = data.replace("check_order_", "", 1)
                    await pay_handler.handle_check_order_callback(query, context, order_no)
                    return
                if data.startswith("cancel_order_"):
                    order_no = data.replace("cancel_order_", "", 1)
                    await pay_handler.handle_cancel_order_callback(query, context, order_no)
                    return
                if data == "back_to_buy":
                    await pay_handler.handle_back_to_buy(query, context)
                    return
                if data == "cancel_buy":
                    await pay_handler.handle_cancel_buy(query, context)
                    return
            except Exception as e:
                self.logger.error(f"❌ 支付回调分发失败: {e}")
            
            self.logger.warning(f"⚠️ 未知回调 action={action}, data={raw_data}, 可用 handlers={list(handlers.keys())}")
            await query.answer("未知操作")

