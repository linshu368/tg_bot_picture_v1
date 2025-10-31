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


class UserCommandHandler(BaseCommandHandler):
    """用户基础命令处理器"""
    
    def get_command_handlers(self):
        """返回用户命令处理方法映射"""
        return {
            "start": self.handle_start_command,
            "help": self.handle_help_command,
            "checkin": self.handle_checkin_command
            
        }
  