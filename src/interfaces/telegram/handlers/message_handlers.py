"""
消息处理器
处理图片消息、文本消息和各种用户输入
"""

import logging
import asyncio
from typing import Dict, Any, Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..ui_handler import UIHandler, escape_markdown, format_generation_summary
from ..user_state_manager import UserStateManager, UserStateHelper, States, DataKeys
from src.utils.config.app_config import (
    COST_QUICK_UNDRESS, COST_CUSTOM_UNDRESS, QUICK_UNDRESS_DEFAULTS, 
    UID_PREFIX, UID_LENGTH
)




class MessageHandler:
    """消息处理器"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.logger = logging.getLogger(__name__)
        self.ui_handler: UIHandler = bot_instance.ui_handler
        self.state_manager: UserStateManager = bot_instance.state_manager
        self.state_helper: UserStateHelper = bot_instance.state_helper
        
        # 服务依赖
        self.user_service = bot_instance.user_service
        self.image_service = bot_instance.image_service
        self.payment_service = bot_instance.payment_service
        # 新增会话和行为记录服务
        self.session_service = bot_instance.session_service
        self.action_record_service = bot_instance.action_record_service
    
    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理图片消息"""
        user = update.effective_user
        
        try:
            # 获取或创建用户会话
            user_data = await self._safe_get_user(user.id)
            if user_data:
                session = await self.session_service.get_or_create_session(user_data['id'])
                if session:
                    # 记录用户行为：发送图片
                    await self.action_record_service.record_action(
                        user_id=user_data['id'],
                        session_id=session['session_id'],
                        action_type='send_photo',
                        message_context='用户发送图片消息'
                    )
            
            # 获取用户信息
            user_data = await self._safe_get_user(user.id)
            if not user_data:
                await update.message.reply_text("❌ 用户不存在，请先使用 /start")
                return
            
            # 获取图片
            photo = update.message.photo[-1]  # 获取最高质量的图片
            current_state = self.state_manager.get_current_state(user.id)
            
            # 根据当前状态处理图片
            if current_state == States.QUICK_UNDRESS_WAITING_PHOTO:
                await self._handle_quick_undress_photo(update, context, photo)
            elif current_state == States.CUSTOM_UNDRESS_WAITING_PHOTO:
                await self._handle_custom_undress_photo(update, context, photo)
            else:
                # 默认显示功能选择
                await self._show_function_selection(update, context, photo)
            
        except Exception as e:
            self.logger.error(f"处理图片消息失败: {e}")
            await update.message.reply_text("❌ 处理图片时出错，请稍后重试")

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文本消息"""
        text = update.message.text
        user = update.effective_user
        self.logger.info("### 当前运行的是已注释版 handle_text_message ###")


        try:
            # 先获取用户信息，避免重复调用
            self.logger.info(f"调用 _safe_get_user(user_id={user.id})")
            user_data = await self._safe_get_user(user.id)
            self.logger.info(f"_safe_get_user 返回: {'OK' if user_data else 'None'}")
            
            # 会话创建与行为记录放后台，避免阻塞首响
            # async def _background_text_side_effects(user_data_inner: dict, preview_text: str):
            #     try:
            #         if not user_data_inner:
            #             self.logger.info("[TEXT_BG] 用户数据为空，跳过后台任务")
            #             return
            #         self.logger.info(f"[TEXT_BG] 使用已获取的用户数据: user_id={user_data_inner['id']}")
            #         self.logger.info(f"[TEXT_BG] 调用 get_or_create_session(user_id={user_data_inner['id']})")
            #         session_inner = await self.session_service.get_or_create_session(user_data_inner['id'])
            #         self.logger.info(f"[TEXT_BG] get_or_create_session 返回: {session_inner.get('session_id') if session_inner else 'None'}")
            #         if not session_inner:
            #             return
            #         short = preview_text[:50] + '...' if len(preview_text) > 50 else preview_text
            #         self.logger.info(f"[TEXT_BG] 调用 record_action(user_id={user_data_inner['id']}, action_type='send_text')")
            #         await self.action_record_service.record_action(
            #             user_id=user_data_inner['id'],
            #             session_id=session_inner['session_id'],
            #             action_type='send_text',
            #             message_context=f'用户发送文本: {short}'
            #         )
            #         self.logger.info("[TEXT_BG] record_action 完成")
            #     except Exception as e:
            #         self.logger.error(f"文本消息副作用失败(后台): {e}")

            # try:
            #     # 传递已获取的用户数据，避免重复查询
            #     asyncio.create_task(_background_text_side_effects(user_data, text))
            # except Exception as e:
            #     self.logger.error(f"调度文本副作用后台任务失败: {e}")
            
            # 检查用户状态 - 如果正在等待UID输入
            self.logger.info(f"获取用户状态: get_current_state(user_id={user.id})")
            current_state = self.state_manager.get_current_state(user.id)
            self.logger.info(f"当前用户状态: {current_state}")
            if current_state == States.WAITING_UID_INPUT:
                self.logger.info(f"重置用户状态: reset_user_state(user_id={user.id})")
                self.state_manager.reset_user_state(user.id)  # 先清除状态
                self.logger.info("用户状态已重置")
                
                # 检查输入是否为有效的UID格式
                uid = text.strip()
                expected_length = len(UID_PREFIX) + UID_LENGTH
                if uid.startswith(UID_PREFIX) and len(uid) == expected_length:
                    # 处理UID找回
                    await self._process_uid_recovery(update, context, uid)
                    return
                else:
                    # 输入格式错误
                    await update.message.reply_text("❌ 身份码格式错误，已退出找回流程")
                    # 继续正常处理用户输入
            
            # 检查用户是否存在
            if not user_data:
                await update.message.reply_text("❌ 用户不存在，请先使用 /start")
                return

            # 模拟用户数据
            # user_data = {"id": 3, "telegram_id": user.id, "mock": True}
            # self.logger.info("_safe_get_user 被跳过，用 mock 数据代替")

            
            # 正常处理文本输入
            await self._handle_button_dispatch(update, context, text)
                
        except Exception as e:
            self.logger.error(f"处理文本消息失败: {e}")
            await self._handle_text_message_error(update, user.id, e)

    async def _safe_get_user(self, user_id: int):
        """安全获取用户信息"""
        self.logger.info(f"开始获取用户信息: telegram_id={user_id}")
        try:
            user = await self.user_service.get_user_by_telegram_id(user_id)
            if user:
                self.logger.info(f"获取用户信息成功: telegram_id={user_id}, user_id={user.get('id')}, uid={user.get('uid')}")
            else:
                self.logger.warning(f"未找到用户: telegram_id={user_id}")
            return user
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {user_id}, 错误: {e}")
            return None

    async def _handle_button_dispatch(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """分发按钮处理，每个功能独立错误处理"""
        self.logger.info(f"🔍 [BUTTON_DISPATCH] 开始处理文本按钮: '{text}'")
        
        # 检查用户是否处于等待UID输入状态，如果点击的不是找回账号按钮，则清除该状态
        # 这样用户可以正常使用其他功能，不会被卡在UID验证状态
        user_id = update.effective_user.id
        try:
            current_state = self.state_manager.get_current_state(user_id)
            if current_state == "waiting_uid" and text != "🔁 找回账号":  # States.WAITING_UID_INPUT
                self.logger.info(f"用户 {user_id} 正在等待UID输入，但点击了其他功能按钮 '{text}'，自动清除等待状态")
                self.state_manager.reset_user_state(user_id)
        except Exception as state_error:
            self.logger.error(f"检查/清除用户状态失败: {state_error}")
        
        function_map = {
            "👕 快速去衣": self._handle_quick_undress_button,
            "🎨 自定义去衣": self._handle_custom_undress_button,
            "💳 充值积分": self._handle_buy_button,
            "👤 个人中心": self._handle_profile_button,
            "🎁 每日签到": self._handle_checkin_button,
            "🔁 找回账号": self._handle_recover_button,
            "❓ 帮助": self._handle_help_button,
        }
        
        if text in function_map:
            self.logger.info(f"🔍 [BUTTON_DISPATCH] 匹配到功能按钮: '{text}' -> {function_map[text].__name__}")
            await self._safe_handle_function(function_map[text], update, context)
        else:
            self.logger.info(f"🔍 [BUTTON_DISPATCH] 未匹配到功能按钮: '{text}'，发送默认提示")
            # 默认提示
            await update.message.reply_text(
                "💡 发送图片开始AI处理，或使用底部菜单功能：\n\n"
                "🎨 /start - 显示主菜单\n"
                "❓ /help - 查看帮助\n"
                "💎 /points - 查看积分\n"
                "🛒 /buy - 购买积分"
            )

    async def _safe_handle_function(self, func, update, context, *args):
        """安全执行功能函数，提供独立的错误处理"""
        function_name = getattr(func, '__name__', '未知功能')
        self.logger.info(f"🔍 [SAFE_HANDLE] 开始执行功能: {function_name}")
        try:
            await func(update, context, *args)
            self.logger.info(f"🔍 [SAFE_HANDLE] 功能执行完成: {function_name}")

        except Exception as e:
            self.logger.error(f"🔍 [SAFE_HANDLE] 功能 {function_name} 执行失败: {e}")
            
            # 根据功能类型提供不同的错误处理
            error_message = self._get_function_error_message(function_name)
            
            try:
                await update.message.reply_text(error_message)
            except Exception as e2:
                self.logger.error(f"发送错误消息失败: {e2}")

    def _get_function_error_message(self, function_name: str) -> str:
        """获取特定功能的错误消息"""
        error_messages = {
            "_handle_quick_undress_button": "❌ 快速去衣功能暂时不可用\n\n💡 您可以尝试：\n• 使用🎨自定义去衣\n• 稍后重试\n• 联系客服",
            "_handle_custom_undress_button": "❌ 自定义去衣功能暂时不可用\n\n💡 您可以尝试：\n• 使用👕快速去衣\n• 稍后重试\n• 联系客服",
            "_handle_profile_button": "❌ 个人中心暂时不可用\n\n💡 您可以尝试：\n• 使用 /points 查看积分\n• 稍后重试\n• 联系客服",
            "_handle_buy_button": "❌ 充值功能暂时不可用\n\n💡 您可以尝试：\n• 稍后重试\n• 联系客服\n• 使用其他功能",
            "_handle_checkin_button": "❌ 签到功能暂时不可用\n\n💡 您可以尝试：\n• 稍后重试\n• 使用其他功能获取积分",
            "_handle_recover_button": "❌ 找回账号功能暂时不可用\n\n💡 请联系客服处理",
            "_handle_help_button": "❌ 帮助功能暂时不可用\n\n💡 您可以直接使用底部菜单功能",
        }
        
        return error_messages.get(function_name, "❌ 功能暂时不可用，请稍后重试或联系客服")

    async def _handle_text_message_error(self, update: Update, user_id: int, error: Exception):
        """处理文本消息的全局错误"""
        try:
            # 清除可能的错误状态
            self.state_manager.reset_user_state(user_id)
            
            error_message = (
                "❌ **系统遇到问题**\n\n"
                "已自动重置您的状态\n\n"
                "💡 建议操作：\n"
                "• 使用底部菜单重新选择功能\n"
                "• 发送 /start 重新开始\n"
                "• 如问题持续，请联系客服"
            )
            
            keyboard = self.ui_handler.create_main_menu_keyboard()
            await update.message.reply_text(
                error_message, 
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            self.logger.error(f"文本消息错误恢复失败: {e}")
            # 最后的保险措施
            try:
                await update.message.reply_text("❌ 系统问题，请使用 /start 重新开始")
            except:
                pass

    # 具体的按钮处理方法
    async def _handle_quick_undress_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理快速脱衣按钮"""
        user = update.effective_user
        
        user_data = await self.user_service.get_user_by_telegram_id(user.id)
        if not user_data:
            await update.message.reply_text("❌ 用户不存在，请先使用 /start")
            return
        
        # 检查积分
        points_balance = await self.user_service.get_user_points_balance(user_data['id'])
        if points_balance < COST_QUICK_UNDRESS:
            message = f"❌ 积分不足！\n\n快速脱衣需要：{COST_QUICK_UNDRESS}积分\n您当前积分：{points_balance}\n\n请先获取积分："
            keyboard = self.ui_handler.create_insufficient_points_keyboard()
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            return
        
        # 设置用户状态为等待上传图片
        self.state_helper.start_quick_undress_flow(user.id)
        
        # 使用原始版本的消息格式
        message = "👕 **快速脱衣**\n\n"
        message += "最优秀最经典的呈现！\n\n"
        message += "直接**上传图片**————建议上传站立，单人，无遮挡，主体人物清晰的照片 无奇怪动作姿势\n\n"
        message += f"图片去衣：{COST_QUICK_UNDRESS}积分/图片\n\n"
        message += "===================\n"
        message += "注意事项：\n"
        message += "1.使用我们的服务即表示您同意 用户协议且不得用于非法用途。\n"
        message += "2.严禁输入未成年相关的任何图片。\n\n"
        message += "24小时开放"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )

    async def _handle_custom_undress_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理自定义脱衣按钮"""
        user = update.effective_user
        
        user_data = await self.user_service.get_user_by_telegram_id(user.id)
        if not user_data:
            await update.message.reply_text("❌ 用户不存在，请先使用 /start")
            return
        
        # 检查积分
        points_balance = await self.user_service.get_user_points_balance(user_data['id'])
        if points_balance < COST_CUSTOM_UNDRESS:
            message = f"❌ 积分不足！\n\n自定义脱衣需要：{COST_CUSTOM_UNDRESS}积分\n您当前积分：{points_balance}\n\n请先获取积分："
            keyboard = self.ui_handler.create_insufficient_points_keyboard()
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            return
        
        # 设置用户状态
        self.state_helper.start_custom_undress_flow(user.id)
        
        message = (
            f"🎨 **自定义脱衣**\n\n"
            f"💰 消耗积分：{COST_CUSTOM_UNDRESS}\n\n"
            f"🔧 可自定义参数：\n"
            f"👔 衣服选项（14种）\n"
            f"🤸 姿势选项（100+种）\n"
            f"⚙️ 偏好设置（体型、年龄等）\n\n"
            f"请先配置参数，然后上传图片"
        )
        
        keyboard = self.ui_handler.create_custom_undress_menu_keyboard()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    async def _handle_buy_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理充值按钮"""
        # 调用支付命令处理器的逻辑
        from .command.payment_commands import PaymentCommandHandler
        payment_handler = PaymentCommandHandler(self.bot)
        await payment_handler.handle_buy_command(update, context)

    async def _handle_profile_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理个人中心按钮"""
        user = update.effective_user
        
        user_data = await self.user_service.get_user_by_telegram_id(user.id)
        if not user_data:
            await update.message.reply_text("❌ 用户不存在，请先使用 /start")
            return
        
        points_balance = await self.user_service.get_user_points_balance(user_data['id'])
        
        # 获取用户统计信息
        username_display = escape_markdown(
            user.username if user.username else "未设置"
        )
        
        message = "👤 **个人中心**\n\n"
        message += f"🆔 身份码：`{user_data.get('uid', 'N/A')}`\n"
        message += f"👤 用户名：{username_display}\n"
        message += f"🎖️ 等级：{user_data.get('level', 1)}\n"
        message += f"💎 当前积分：{points_balance}\n\n"
        
        # 统计信息
        message += "📊 **统计信息**\n"
        message += f"💰 累计消费：¥{user_data.get('total_paid', 0):.2f}\n"
        message += f"🔥 累计使用：{user_data.get('total_points_spent', 0)}积分\n"
        message += f"📅 注册时间：{user_data.get('created_at', 'N/A')[:10]}\n\n"
        message += "请选择功能："
        
        keyboard = self.ui_handler.create_profile_menu_keyboard()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    async def _handle_checkin_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理签到按钮"""
        # 调用用户命令处理器的逻辑
        from .command.user_commands import UserCommandHandler
        user_handler = UserCommandHandler(self.bot)
        await user_handler.handle_checkin_command(update, context)

    async def _handle_recover_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理找回账号按钮"""
        from .command.user_commands import UserCommandHandler
        user_handler = UserCommandHandler(self.bot)
        await user_handler.handle_recover_command(update, context)

    async def _handle_help_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理帮助按钮"""
        self.logger.info("🔍 [HELP_BUTTON] _handle_help_button 被调用")

        from .command.user_commands import UserCommandHandler
        self.logger.info("🔍 [HELP_BUTTON] 创建 UserCommandHandler 实例")
        user_handler = UserCommandHandler(self.bot)
        self.logger.info("🔍 [HELP_BUTTON] 准备调用 handle_help_command")
        await user_handler.handle_help_command(update, context)
        self.logger.info("🔍 [HELP_BUTTON] handle_help_command 调用完成")


    async def _process_uid_recovery(self, update: Update, context: ContextTypes.DEFAULT_TYPE, uid: str):
        """处理UID找回逻辑"""
        user_id = update.effective_user.id
        
        try:
            # 查找UID对应的用户
            existing_user = await self.user_service.get_user_by_uid(uid)
            if not existing_user:
                await update.message.reply_text(
                    "❌ 身份码不存在\n\n请检查输入是否正确，或联系客服"
                )
                return
            
            # 绑定新的telegram_id到该UID
            success = await self.user_service.bind_user_to_uid(user_id, uid)
            
            if success:
                # 获取更新后的用户信息
                user_data = await self.user_service.get_user_by_telegram_id(user_id)
                points_balance = await self.user_service.get_user_points_balance(user_data['id'])
                
                message = "✅ 找回成功！您的积分与记录已恢复\n\n"
                message += f"🎁 当前积分：{points_balance}\n"
                message += f"📜 等级：{user_data.get('level', 1)}\n\n"
                message += "欢迎回来！您现在可以继续使用所有功能～"

                keyboard = self.ui_handler.create_main_menu_keyboard()
                await update.message.reply_text(message, reply_markup=keyboard)
            else:
                await update.message.reply_text(
                    "❌ 绑定失败\n\n该Telegram账号可能已被其他用户使用，请联系客服"
                )
                
        except Exception as e:
            self.logger.error(f"处理UID找回失败: {e}")
            await update.message.reply_text("❌ 处理失败，请稍后重试")

    # 图片处理相关方法
    async def _show_function_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, photo):
        """显示功能选择界面"""
        # 保存图片信息到状态
        user_id = update.effective_user.id
        self.state_helper.set_photo_uploaded(user_id, photo.file_id)
        
        message = "📸 **图片已接收！**\n\n请选择处理类型："
        keyboard = self.ui_handler.create_function_selection_keyboard()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    async def _handle_quick_undress_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE, photo):
        """处理快速脱衣的图片上传"""
        user_id = update.effective_user.id
        
        try:
            # 保存图片文件ID
            self.state_helper.set_photo_uploaded(user_id, photo.file_id)
            
            # 显示确认界面
            params = QUICK_UNDRESS_DEFAULTS.copy()
            summary = format_generation_summary(params, COST_QUICK_UNDRESS)
            
            keyboard = self.ui_handler.create_generation_confirmation_keyboard("quick_undress")
            
            await update.message.reply_text(
                summary,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            self.logger.error(f"处理快速脱衣图片失败: {e}")
            await update.message.reply_text("❌ 处理图片失败，请稍后重试")

    async def _handle_custom_undress_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE, photo):
        """处理自定义脱衣的图片上传"""
        user_id = update.effective_user.id
        
        try:
            # 保存图片文件ID
            self.state_helper.set_photo_uploaded(user_id, photo.file_id)
            
            # 获取用户自定义参数
            user_params = self.state_helper.get_generation_params(user_id)
            
            # 使用默认参数填充缺失的项
            params = QUICK_UNDRESS_DEFAULTS.copy()
            params.update(user_params)
            
            summary = format_generation_summary(params, COST_CUSTOM_UNDRESS)
            
            keyboard = self.ui_handler.create_generation_confirmation_keyboard("custom_undress")
            
            await update.message.reply_text(
                summary,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            self.logger.error(f"处理自定义脱衣图片失败: {e}")
            await update.message.reply_text("❌ 处理图片失败，请稍后重试") 