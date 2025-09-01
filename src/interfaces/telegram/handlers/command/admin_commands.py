"""
管理员命令处理器
处理管理员专用命令
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .base_command_handler import BaseCommandHandler, safe_command_handler


class AdminCommandHandler(BaseCommandHandler):
    """管理员命令处理器"""
    
    def __init__(self, bot_instance, admin_user_id: int = None):
        super().__init__(bot_instance)
        self.admin_user_id = admin_user_id
    
    def get_command_handlers(self):
        """返回管理员命令处理方法映射"""
        return {
            "admin": self.handle_admin_command,
        }
    
    def _check_admin_permission(self, user_id: int) -> bool:
        """检查是否有管理员权限"""
        return user_id == self.admin_user_id
    
    @safe_command_handler
    async def handle_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/admin命令"""
        user = update.effective_user
        
        if not self._check_admin_permission(user.id):
            await update.message.reply_text("❌ 权限不足")
            return
        
        message = (
            f"🔧 **管理员面板**\n\n"
            f"👥 活跃用户: {self.state_manager.get_active_users_count()}\n"
            f"📊 状态统计: {len(self.state_manager.states)} 个用户状态\n\n"
            f"管理功能开发中..."
        )
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        ) 