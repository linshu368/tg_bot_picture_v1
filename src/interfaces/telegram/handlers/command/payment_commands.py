"""
支付相关命令处理器
处理购买、订单、记录等相关命令
"""

from telegram import Update, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

from .base_command_handler import BaseCommandHandler, safe_command_handler


class PaymentCommandHandler(BaseCommandHandler):
    """支付相关命令处理器"""
    
    def get_command_handlers(self):
        """返回支付命令处理方法映射"""
        return {
            "buy": self.handle_buy_command,
            "orders": self.handle_orders_command,
            "records": self.handle_records_command,
        }
    
    @safe_command_handler
    async def handle_buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/buy命令 - 复用回调处理器的逻辑"""
        # 创建一个模拟的回调查询对象来重用回调逻辑
        class MockQuery:
            def __init__(self, user, message):
                self.from_user = user
                self.message = message
                
            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        mock_query = MockQuery(update.effective_user, update.message)
        # 调用新的回调处理逻辑
        from ..callback.payment_callbacks import PaymentCallbackHandler
        payment_handler = PaymentCallbackHandler(self.bot)
        await payment_handler.handle_buy_credits_callback(mock_query, context)
    
    @safe_command_handler
    async def handle_orders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/orders命令 - 显示用户订单记录"""
        user_data = await self._check_user_exists(update)
        if not user_data:
            return
        
        try:
            # 获取用户订单历史（最近5条）
            orders = await self.payment_service.get_user_payment_history(user_data['id'], limit=5)
            
            message = "📋 **订单记录**\n\n"
            
            if orders:
                for order in orders:
                    order_id = order.get('order_id', 'N/A')
                    amount = order.get('amount', 0)
                    status = order.get('status', 'unknown')
                    points_awarded = order.get('points_awarded', 0)
                    created_at = order.get('created_at', '')
                    
                    # 格式化日期
                    if created_at:
                        try:
                            if isinstance(created_at, str):
                                date_str = created_at[:10]  # 取前10位作为日期
                            else:
                                date_str = created_at.strftime('%Y-%m-%d')
                        except:
                            date_str = 'N/A'
                    else:
                        date_str = 'N/A'
                    
                    # 状态emoji映射
                    status_emoji = {
                        'pending': '⏳',
                        'paid': '✅', 
                        'completed': '✅',
                        'expired': '⏰',
                        'cancelled': '❌',
                        'failed': '❌'
                    }.get(status, '❓')
                    
                    # 状态中文映射
                    status_text = {
                        'pending': '待支付',
                        'paid': '已支付',
                        'completed': '已完成',
                        'expired': '已过期',
                        'cancelled': '已取消',
                        'failed': '支付失败'
                    }.get(status, '未知状态')
                    
                    message += f"{status_emoji} **订单 #{order_id}**\n"
                    message += f"💰 金额: ¥{amount}\n"
                    message += f"💎 获得积分: {points_awarded}\n"
                    message += f"📅 日期: {date_str}\n"
                    message += f"📊 状态: {status_text}\n\n"
                
                # 获取订单统计（只显示总消费金额和总获得积分）
                stats = await self.payment_service.get_payment_statistics(user_data['id'])
                message += "📊 **订单统计**\n"
                message += f"总消费: ¥{stats.get('total_amount', 0):.2f}\n"
                message += f"总获得积分: {stats.get('total_credits', 0)}"
                
            else:
                message += "暂无订单记录\n\n"
                message += "💡 您可以使用 /buy 命令购买积分"
            
            # 添加返回按钮
            keyboard = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message, 
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            self.logger.error(f"获取订单记录失败: {e}")
            await update.message.reply_text(
                "❌ 获取订单记录失败，请稍后重试",
                reply_markup=self.ui_handler.create_main_menu_keyboard()
            )
    
    @safe_command_handler
    async def handle_records_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/records命令 - 显示用户积分记录"""
        user_data = await self._check_user_exists(update)
        if not user_data:
            return
            
        try:
            # 获取用户积分记录（最近5条）
            records = await self.user_service.get_user_points_history(user_data['id'], limit=5)
            
            message = f"📊 **积分记录**\n\n"
            message += f"💎 当前积分: **{user_data.get('points', 0)}**\n\n"
            
            if records:
                for record in records:
                    points_change = record.get('points_change', 0)
                    action_type = record.get('action_type', '未知操作')
                    points_balance = record.get('points_balance', 0)
                    
                    # 操作类型中文映射
                    action_text = {
                        'registration': '注册奖励',
                        'daily_checkin': '每日签到',
                        'image_generation': '图像生成',
                        'payment': '充值获得',
                        'purchase': '购买消费',
                        'quick_undress': '快速去衣',
                        'custom_undress': '自定义去衣',
                        'faceswap': '人脸交换',
                        'refund': '退款',
                        'admin_adjust': '管理员调整'
                    }.get(action_type, action_type)
                    
                    if points_change > 0:
                        message += f"✅ **+{points_change}** 积分 - {action_text} | 余额: {points_balance}\n"
                    else:
                        message += f"❌ **{points_change}** 积分 - {action_text} | 余额: {points_balance}\n"
                    
            else:
                message += "暂无积分记录\n\n"
                message += "💡 您可以通过以下方式获得积分：\n"
                message += "• 每日签到 /checkin\n"
                message += "• 购买积分 /buy"
            
            # 添加返回按钮
            keyboard = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message, 
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            self.logger.error(f"获取积分记录失败: {e}")
            await update.message.reply_text(
                "❌ 获取积分记录失败，请稍后重试",
                reply_markup=self.ui_handler.create_main_menu_keyboard()
            ) 