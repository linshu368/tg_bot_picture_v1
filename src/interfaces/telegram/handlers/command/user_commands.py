"""
用户基础命令处理器
处理用户日常使用的基础命令
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import asyncio

from .base_command_handler import BaseCommandHandler, safe_command_handler
from ...ui_handler import escape_markdown
from ...user_state_manager import States
from src.utils.config.app_config import (
    COST_QUICK_UNDRESS, COST_CUSTOM_UNDRESS, UID_PREFIX, UID_LENGTH
)
from src.utils.performance_monitor import get_performance_monitor


class UserCommandHandler(BaseCommandHandler):
    """用户基础命令处理器"""
    
    def get_command_handlers(self):
        """返回用户命令处理方法映射"""
        return {
            "start": self.handle_start_command,
            "help": self.handle_help_command,
            "myid": self.handle_myid_command,
            "points": self.handle_points_command,
            "checkin": self.handle_checkin_command,
            "recover": self.handle_recover_command,
        }
    
    @safe_command_handler
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start命令"""
        # 开始性能监控
        monitor = get_performance_monitor()
        operation_id = f"start_command_{update.effective_user.id}"
        
        async with monitor.async_timer(operation_id, "处理 /start 命令"):
            user = update.effective_user
            
            # 检查点：开始用户注册
            monitor.checkpoint(operation_id, "user_registration", "开始用户注册")
            
            # 注册用户
            registered_user = await self.user_service.register_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            # 检查点：用户注册完成
            monitor.checkpoint(operation_id, "user_registered", "用户注册完成")
            
            if registered_user:
                # 检查点：开始构建欢迎消息
                monitor.checkpoint(operation_id, "building_welcome", "构建欢迎消息")
                
                # 会话创建与行为记录放后台，避免阻塞首条欢迎消息
                async def _background_start_side_effects(user_id: int):
                    try:
                        session_inner = await self.session_service.get_or_create_session(user_id)
                        if not session_inner:
                            return
                        await self.action_record_service.record_action(
                            user_id=user_id,
                            session_id=session_inner['session_id'],
                            action_type='start_command',
                            message_context='用户执行/start命令'
                        )
                    except Exception as e:
                        self.logger.error(f"/start 副作用失败(后台): {e}")

                try:
                    asyncio.create_task(_background_start_side_effects(registered_user['id']))
                except Exception as e:
                    self.logger.error(f"调度 /start 副作用后台任务失败: {e}")
                
                welcome_message = (
                    f"🎉 **欢迎来到AI图像处理bot！**\n\n"
                    f"👤 用户: {escape_markdown(user.first_name or 'Anonymous')}\n"
                    f"🆔 ID: `{user.id}`\n"
                    f"💰 当前积分: {registered_user.get('points', 50)}\n\n"
                    f"🎨 **功能介绍：**\n"
                    f"👕 快速脱衣 - 一键体验，使用最优参数\n"
                    f"🎨 自定义脱衣 - 自由选择衣服、姿势、偏好\n"
                    f"🔄 快速换脸 - 图片/视频人脸交换\n\n"
                    f"💡 **使用说明：**\n"
                    f"直接发送图片开始处理，或点击下方按钮选择功能"
                )
                
                # 检查点：创建UI键盘
                monitor.checkpoint(operation_id, "creating_keyboard", "创建主菜单键盘")
                
                # 使用UI处理器创建主菜单
                reply_markup = self.ui_handler.create_main_menu_keyboard()
                
                # 检查点：发送欢迎消息
                monitor.checkpoint(operation_id, "sending_message", "发送欢迎消息")
                
                await update.message.reply_text(
                    welcome_message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                self.logger.info(f"用户注册成功: {user.id} - {user.first_name}")
            else:
                await update.message.reply_text("❌ 注册失败，请稍后重试")
    
    @safe_command_handler
    async def handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/help命令"""
        # 开始性能监控
        monitor = get_performance_monitor()
        operation_id = f"help_command_{update.effective_user.id}"
        
        async with monitor.async_timer(operation_id, "处理 /help 命令"):
            help_text = f"""
🤖 **AI图像生成机器人使用指南**

**基础功能：**
👕 快速去衣 - 一键体验，使用最优参数
🎨 自定义去衣 - 自由选择衣服、姿势、偏好
🎁 /checkin - 每日签到获取积分
💰 /points - 查看当前积分余额
📊 /records - 查看积分使用记录
🛒 /buy - 购买积分包
📋 /orders - 查看订单记录
🆔 /myid - 查看您的身份码

**功能介绍：**
👕 快速去衣 - 使用最优参数，直接上传图片
🎨 自定义去衣 - 选择衣服(14种)、姿势(100+种)、偏好设置

**积分消耗：**
- 快速去衣：{COST_QUICK_UNDRESS}积分
- 自定义去衣：{COST_CUSTOM_UNDRESS}积分

**使用流程：**
1. 发送图片或点击功能按钮
2. 选择处理类型和参数
3. 确认生成并等待结果

如有问题请联系客服 👨‍💻
        """

            await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    @safe_command_handler
    async def handle_myid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/myid命令"""
        # 开始性能监控
        monitor = get_performance_monitor()
        operation_id = f"myid_command_{update.effective_user.id}"
        
        async with monitor.async_timer(operation_id, "处理 /myid 命令"):
            user = update.effective_user
            await update.message.reply_text(f"🆔 您的用户ID是: `{user.id}`", parse_mode=ParseMode.MARKDOWN)
    
    @safe_command_handler
    async def handle_points_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/points命令"""
        # 开始性能监控
        monitor = get_performance_monitor()
        operation_id = f"points_command_{update.effective_user.id}"
        
        async with monitor.async_timer(operation_id, "处理 /points 命令"):
            user = update.effective_user
            
            # 检查点：验证用户存在
            monitor.checkpoint(operation_id, "check_user", "检查用户是否存在")
            user_data = await self._check_user_exists(update)
            if not user_data:
                return
            
            # 检查点：获取积分余额
            monitor.checkpoint(operation_id, "get_points", "获取用户积分余额")
            points_balance = await self.user_service.get_user_points_balance(user_data['id'])
            
            # 检查点：构建消息
            monitor.checkpoint(operation_id, "build_message", "构建积分信息消息")
            message = (
                f"💰 **积分余额信息**\n\n"
                f"👤 用户: {escape_markdown(user.first_name or 'Anonymous')}\n"
                f"💎 当前积分: {points_balance}\n\n"
                f"🛒 使用 /buy 购买更多积分\n"
                f"🎁 使用 /checkin 每日签到获取积分"
            )
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [
                    InlineKeyboardButton("🎁 每日签到", callback_data="daily_checkin"),
                    InlineKeyboardButton("🛒 购买积分", callback_data="buy_credits")
                ]
            ]
            
            # 检查点：发送消息
            monitor.checkpoint(operation_id, "send_message", "发送积分信息消息")
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    @safe_command_handler
    async def handle_checkin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/checkin命令"""
        # 开始性能监控
        monitor = get_performance_monitor()
        operation_id = f"checkin_command_{update.effective_user.id}"
        
        async with monitor.async_timer(operation_id, "处理 /checkin 命令"):
            user = update.effective_user
            
            # 检查点：验证用户存在
            monitor.checkpoint(operation_id, "check_user", "检查用户是否存在")
            user_data = await self._check_user_exists(update)
            if not user_data:
                return
            
            # 检查点：执行签到
            monitor.checkpoint(operation_id, "daily_checkin", "执行每日签到")
            result = await self.user_service.daily_checkin(user_data['id'])
            
            # 检查点：构建响应消息
            monitor.checkpoint(operation_id, "build_response", "构建签到响应消息")
            if result['success']:
                message = f"🎉 {result['message']}\n\n💰 获得积分: +{result.get('points', 0)}"
            else:
                message = f"ℹ️ {result['message']}"
            
            # 检查点：发送消息
            monitor.checkpoint(operation_id, "send_message", "发送签到结果消息")
            await update.message.reply_text(message)
        
        # 将会话创建和行为记录移到后台，避免阻塞签到响应
        async def _background_checkin_side_effects(user_id: int):
            try:
                session_inner = await self.session_service.get_or_create_session(user_id)
                if not session_inner:
                    return
                await self.action_record_service.record_action(
                    user_id=user_id,
                    session_id=session_inner['session_id'],
                    action_type='daily_checkin',
                    message_context='用户执行每日签到'
                )
            except Exception as e:
                self.logger.error(f"签到副作用失败(后台): {e}")

        try:
            asyncio.create_task(_background_checkin_side_effects(user_data['id']))
        except Exception as e:
            self.logger.error(f"调度签到副作用后台任务失败: {e}")
    
    @safe_command_handler
    async def handle_recover_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/recover命令"""
        message = "🔁 **账号找回**\n\n"
        message += "请直接输入您的身份码：\n\n"
        message += f"格式示例：`{UID_PREFIX}123456789`\n\n"
        message += "💡 输入错误或不想找回，点击其他按钮即可退出"

        # 设置用户状态为等待UID输入
        self.state_manager.update_user_state(
            update.effective_user.id, 
            States.WAITING_UID_INPUT
        )
        self.state_manager.set_user_expiry(update.effective_user.id, 3)  # 3分钟过期

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN) 