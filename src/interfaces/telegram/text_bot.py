import logging
import os
from typing import Optional

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
from src.interfaces.telegram.controllers.session_controller import process_message
from src.interfaces.telegram.handlers.callback.text_bot_callback_handler import TextBotCallbackHandler
from src.interfaces.telegram.ui_handler import UIHandler
from src.domain.services.role_service import RoleService
from src.domain.services.session_service_base import session_service
from src.domain.services.snapshot_service import snapshot_service


class DummyService:
    def __getattr__(self, item):
        return lambda *args, **kwargs: None

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
        self.ui_handler = UIHandler()
        self.role_service = RoleService()
        self.default_role_id = "1" #默认角色ID
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
        # --------------------------------------------------
        self.callback_handler = TextBotCallbackHandler(self)
        # 用于保存快照命名的临时状态：user_id -> {session_id}
        self.pending_snapshot = {}
        
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
                session = await session_service.new_session(user_id, role_id)
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
                await update.message.reply_text(role["predefined_messages"])
            else:
                # 角色不存在，降级到默认角色
                self.logger.warning(f"⚠️ 角色不存在: role_id={role_id}，使用默认角色")
                await update.message.reply_text(f"❌ 角色不存在，使用默认角色")
                
                # 使用默认角色创建会话
                session = await session_service.new_session(user_id, self.default_role_id)
                role = self.role_service.get_role_by_id(self.default_role_id)
                if role:
                    await update.message.reply_text(role["predefined_messages"])
        
        # 情况A：正常启动（无参数），使用默认角色
        else:
            self.logger.info(f"🆕 正常启动，使用默认角色: role_id={self.default_role_id}")
            
            # 1. 发送通用欢迎语（带底部主菜单和角色图鉴按钮）
            main_menu = self.ui_handler.create_main_menu_keyboard()
            role_gallery_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 浏览角色图鉴", url=self.role_channel_url)]
            ])
            await update.message.reply_text(
                """让AI为你提供理想陪伴：
• 💕 甜蜜的恋爱互动
• 💌 深夜的暧昧幻想
• 📝 令人社保的文爱体验
• 💫 或任何你想要的剧情...

✨ 独特体验：
• 海量精品角色等你来选
• 细腻的文字描写能力，对话自然动人
• 支持白嫖，签到拉人均可获取积分，价格也不贵

🎮 开始体验:
1. 直接发送消息即可与默认女友"小鹿"对话
2. 点击「选择角色」 查看角色图鉴，或在角色卡频道选择更多角色""",
                reply_markup=role_gallery_keyboard
            )
            
            # 2. 创建会话并绑定默认角色
            session = await session_service.create_session_with_role(user_id, self.default_role_id)
            self.logger.info(f"✅ 创建会话: session_id={session['session_id']}, role_id={self.default_role_id}")
            
            # 3. 获取默认角色数据
            role = self.role_service.get_role_by_id(self.default_role_id)
            
            # 4. 发送默认角色预置消息
            if role:
                await update.message.reply_text(role["predefined_messages"])
            else:
                await update.message.reply_text("❌ 默认角色不存在")

    async def _handle_snapshot_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, snapshot_id: str) -> None:
        """通过 deeplink 打开某个快照的预览：角色卡预览 + 最后一条消息 + 操作按钮"""
        try:
            snap = await snapshot_service.get_snapshot(user_id=user_id, snapshot_id=snapshot_id)
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
        
        user_id = str(update.effective_user.id) if update.effective_user else "unknown"
        content = update.message.text
        self.logger.info("📥 消息 user_id=%s text=%s", user_id, content)

        # 命名态拦截：优先处理保存快照命名
        if self.pending_snapshot.get(user_id):
            session_id = self.pending_snapshot[user_id].get("session_id")
            try:
                title = content.strip() if content.strip() else "未命名"
                snapshot_id = await snapshot_service.save_snapshot(user_id=user_id, session_id=session_id, user_title=title)
                self.logger.info(f"✅ 快照已保存(命名): snapshot_id={snapshot_id}")
                await update.message.reply_text("✅ 保存成功，可在主菜单点击「🗂 历史聊天」查看保存结果。也可直接发送消息继续对话")
            except Exception as e:
                self.logger.error(f"❌ 保存快照失败(命名): {e}")
                await update.message.reply_text("❌ 保存失败，请重试")
            finally:
                self.pending_snapshot.pop(user_id, None)
            return

        # 处理底部主菜单按钮
        if content == "👤 个人中心":
            await self._handle_profile(update, user_id)
            return
        elif content == "💳 充值积分":
            await self._handle_buy_credits(update, user_id)
            return
        elif content == "🎁 每日签到":
            await self._handle_daily_checkin(update, user_id)
            return
        elif content == "🎭 选择角色":
            await self._handle_role_selection(update, user_id)
            return
        elif content == "🗂 历史聊天":
            await self._handle_history_list(update, context, user_id)
            return
        elif content == "❓ 帮助":
            await self._handle_help(update, user_id)
            return

        # 使用应用层的流式消息服务处理
        from src.core.services.stream_message_service import stream_message_service
        await stream_message_service.handle_stream_message(update, user_id, content, self.ui_handler)

        self.logger.info("📥 消息 user_id=%s text=%s", update.effective_user.id, update.message.text)


    # -------------------------
    # 底部菜单处理方法
    # -------------------------
    async def _handle_profile(self, update: Update, user_id: str) -> None:
        """处理个人中心"""
        self.logger.info(f"👤 个人中心 user_id={user_id}")
        
        # TODO: 从数据库获取真实用户信息
        profile_text = f"""👤 **个人中心**

🆔 用户ID: `{user_id}`
💰 当前积分: 100
🎁 签到天数: 3
📅 注册时间: 2025-01-01

💡 提示：使用下方按钮查看更多详情
"""
        
        keyboard = self.ui_handler.create_profile_menu_keyboard()
        await update.message.reply_text(profile_text, reply_markup=keyboard, parse_mode='Markdown')
    
    async def _handle_buy_credits(self, update: Update, user_id: str) -> None:
        """处理充值积分"""
        self.logger.info(f"💳 充值积分 user_id={user_id}")
        
        # TODO: 实现真实的充值逻辑
        buy_text = """💳 **充值积分**

📦 充值套餐：
• 💎 小额套餐：10元 = 100积分
• 💎 标准套餐：30元 = 350积分
• 💎 超值套餐：50元 = 600积分
• 💎 豪华套餐：100元 = 1300积分

💡 提示：首次充值享受额外赠送！

⚠️ 充值功能开发中，敬请期待...
"""
        
        await update.message.reply_text(buy_text, parse_mode='Markdown')
    
    async def _handle_daily_checkin(self, update: Update, user_id: str) -> None:
        """处理每日签到"""
        self.logger.info(f"🎁 每日签到 user_id={user_id}")
        
        # TODO: 实现真实的签到逻辑
        checkin_text = """🎁 **每日签到**

✅ 签到成功！
🎉 获得 10 积分奖励

📊 签到统计：
• 连续签到：3天
• 累计签到：15天
• 本月签到：8天

💡 提示：连续签到7天可获得额外奖励！
"""
        
        await update.message.reply_text(checkin_text, parse_mode='Markdown')
    
    async def _handle_help(self, update: Update, user_id: str) -> None:
        """处理帮助"""
        self.logger.info(f"❓ 帮助 user_id={user_id}")
        
        help_text = """❓ **帮助中心**

📚 **功能说明：**

💬 **对话功能**
• 直接发送消息与AI角色对话
• 使用 /list 查看角色列表
• 使用 /create 创建自定义角色

👤 **个人中心**
• 查看积分余额和签到记录
• 查看订单历史
• 管理个人资料

💳 **充值积分**
• 多种充值套餐可选
• 首次充值享额外赠送
• 支持多种支付方式

🎁 **每日签到**
• 每日签到获得免费积分
• 连续签到获得额外奖励

🔄 **重新生成**
• 对AI回复不满意？点击"🔄 重新生成"按钮

🆕 **新的对话**
• 想要开始新话题？点击"🆕 新的对话"按钮

📞 **联系我们：**
• 遇到问题请联系客服
• 客服Telegram: @support

💡 更多功能开发中，敬请期待...
"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def _handle_history_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str) -> None:
        """历史聊天列表：以 deeplink 链接形式展示最近快照"""
        self.logger.info(f"🗂 历史聊天列表 user_id={user_id}")
        try:
            snapshots = await snapshot_service.list_snapshots(user_id)
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
            self.logger.warning(f"⚠️ 未知回调 action={action}, data={raw_data}, 可用 handlers={list(handlers.keys())}")
            await query.answer("未知操作")

