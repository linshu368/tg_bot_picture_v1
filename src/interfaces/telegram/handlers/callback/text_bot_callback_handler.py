import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import uuid
from telegram.ext import ContextTypes
from .base_callback_handler import BaseCallbackHandler, robust_callback_handler
from ...ui_handler import UIHandler
from src.domain.services.session_service_base import session_service
from src.domain.services.message_service import message_service
from src.domain.services.ai_completion_port import ai_completion_port
from src.domain.services.role_service import role_service
from src.domain.services.snapshot_service import snapshot_service
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

class TextBotCallbackHandler(BaseCallbackHandler):
    """文字 Bot 的回调处理器"""

    def __init__(self, bot_instance):
        super().__init__(bot_instance)
        self.logger = logging.getLogger(__name__)

    def get_callback_handlers(self):
        """定义本 Bot 支持的回调动作"""
        handlers = {
            "regenerate": self._on_regenerate,
            "new_session": self._on_new_session,
            "save_snapshot": self._on_save_snapshot,
            "save_snapshot_direct": self._on_save_snapshot_direct,
            "delete_snapshot": self._on_delete_snapshot,
        }
        self.logger.info(f"✅ 注册回调 handlers: {list(handlers.keys())}")
        return handlers

    # -------------------------
    # 工具方法
    # -------------------------
    async def _update_message(self, query, reply_text: str, session_id: str = "", user_message_id: str = ""):
        await query.edit_message_text(
            text=reply_text,
            reply_markup=UIHandler.build_reply_keyboard(session_id, user_message_id),
        )

    # -------------------------
    # 回调方法
    # -------------------------
    @robust_callback_handler
    async def _on_regenerate(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 重新生成 按钮"""
        self.logger.info(f"📥 收到回调 action=regenerate data={query.data} user_id={query.from_user.id}")
        user_id = str(query.from_user.id)
        raw_data = query.data

        # 从 callback_data 中解析
        parts = raw_data.split(":")
        action = parts[0]
        session_id = parts[1] if len(parts) > 1 else None
        user_message_id = parts[2] if len(parts) > 2 else None

        self.logger.info(
            f"📥 回调 regenerate: user_id={user_id}, session_id={session_id}, user_message_id={user_message_id}"
        )

        try:
            # 1. 从会话获取绑定的角色ID
            role_id = await session_service.get_session_role_id(session_id)
            self.logger.info(f"📥 获取会话角色: session_id={session_id}, role_id={role_id}")
            
            # 2. 获取角色数据，如果角色不存在则使用默认角色
            if role_id:
                role_data = role_service.get_role_by_id(role_id)
            else:
                role_data = None
                
            if not role_data:
                # 降级到默认角色 (从bot实例获取默认角色ID)
                default_role_id = getattr(self.bot, 'default_role_id', '001')
                role_data = role_service.get_role_by_id(default_role_id)
                self.logger.warning(f"⚠️ 角色不存在，使用默认角色: role_id={role_id} -> default={default_role_id}")
            
            if not role_data:
                await self._update_message(query, "❌ 角色配置错误，请联系管理员", session_id=session_id, user_message_id=user_message_id)
                return
                
            self.logger.info(f"✅ 使用角色: {role_data.get('name', 'Unknown')} (ID: {role_data.get('role_id', 'Unknown')})")
            
            # 3. 重新生成回复
            result = await message_service.regenerate_reply(
                session_id=session_id,
                last_message_id=user_message_id,   # ✅ 用 user_message_id 精确定位
                ai_port=ai_completion_port,
                role_data=role_data,  # ✅ 使用动态获取的角色数据
            )
            reply = result["reply"]
            await self._update_message(query, reply, session_id=session_id, user_message_id=user_message_id)
        except TimeoutError:
            await self._update_message(query, "⏱️ 生成超时，请重试", session_id=session_id, user_message_id=user_message_id)
        except Exception as e:
            self.logger.error(f"❌ 重新生成失败: {e}")
            await self._update_message(query, "⚠️ AI生成失败，请重试", session_id=session_id, user_message_id=user_message_id)

    @robust_callback_handler
    async def _on_new_session(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 新的对话 按钮"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        
        # 从 callback_data 中解析当前session_id
        parts = raw_data.split(":")
        current_session_id = parts[1] if len(parts) > 1 else None
        
        self.logger.info(f"📥 新对话请求: user_id={user_id}, current_session_id={current_session_id}")
        
        try:
            # 1. 获取当前会话的角色ID，保持角色不变
            current_role_id = await session_service.get_session_role_id(current_session_id)
            if not current_role_id:
                # 如果当前会话没有角色，使用默认角色
                current_role_id = getattr(self.bot, 'default_role_id', '001')
                self.logger.info(f"📥 当前会话无角色，使用默认角色: {current_role_id}")
            
            # 2. 创建新会话，保持相同角色
            new_session = await session_service.new_session(user_id, current_role_id)
            new_session_id = new_session["session_id"]
            
            self.logger.info(f"✅ 创建新对话: session_id={new_session_id}, role_id={current_role_id}")
            
            # 3. 获取角色信息，发送角色欢迎语
            role_data = role_service.get_role_by_id(current_role_id)
            if role_data:
                welcome_msg = f"🆕 已开启新对话\n\n💫 当前角色：{role_data.get('name', '未知角色')}\n\n{role_data.get('predefined_messages', '你好！')}"
            else:
                welcome_msg = "🆕 已开启新对话"
            
            await self._update_message(query, welcome_msg, session_id=new_session_id, user_message_id="")
            
        except Exception as e:
            self.logger.error(f"❌ 创建新对话失败: {e}")
            await self._update_message(query, "❌ 创建新对话失败，请重试", session_id="", user_message_id="")

    @robust_callback_handler
    async def _on_save_snapshot(self, query, context: ContextTypes.DEFAULT_TYPE):
        """点击 保存对话 按钮"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        parts = raw_data.split(":")
        session_id = parts[1] if len(parts) > 1 else None
        self.logger.info(f"📥 保存对话请求: user_id={user_id}, session_id={session_id}")

        if not session_id:
            await query.answer("❌ 无效的会话")
            return

        try:
            # 标记命名待输入（进程内状态）
            setattr(self.bot, "pending_snapshot", getattr(self.bot, "pending_snapshot", {}))
            self.bot.pending_snapshot[user_id] = {"session_id": session_id}

            # 提示用户输入名称，附带“直接保存（未命名）”按钮
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("直接保存", callback_data=f"save_snapshot_direct:{session_id}")]])
            await query.message.reply_text(
                "请发送本次历史聊天的名称，或点击下方按钮直接保存",
                reply_markup=keyboard
            )
            await query.answer()
        except Exception as e:
            self.logger.error(f"❌ 保存对话失败: {e}")
            await query.answer("❌ 保存失败，请重试")

    @robust_callback_handler
    async def _on_save_snapshot_direct(self, query, context: ContextTypes.DEFAULT_TYPE):
        """直接保存"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        parts = raw_data.split(":")
        session_id = parts[1] if len(parts) > 1 else None
        if not session_id:
            await query.answer("❌ 无效的会话")
            return
        try:
            snapshot_id = await snapshot_service.save_snapshot(user_id=user_id, session_id=session_id, user_title="未命名")
            self.logger.info(f"✅ 快照已保存(直接): snapshot_id={snapshot_id}")
            # 清理可能存在的命名态
            if getattr(self.bot, "pending_snapshot", None):
                self.bot.pending_snapshot.pop(user_id, None)
            await query.answer()
            await query.message.reply_text("✅ 保存成功，可在主菜单点击「🗂 历史聊天」查看保存结果")
        except Exception as e:
            self.logger.error(f"❌ 直接保存失败: {e}")
            await query.answer("❌ 保存失败，请重试")

    @robust_callback_handler
    async def _on_delete_snapshot(self, query, context: ContextTypes.DEFAULT_TYPE):
        """删除记忆（硬删除）"""
        user_id = str(query.from_user.id)
        raw_data = query.data
        parts = raw_data.split(":")
        snapshot_id = parts[1] if len(parts) > 1 else None
        if not snapshot_id:
            await query.answer("❌ 无效的快照")
            return
        try:
            ok = await snapshot_service.delete_snapshot(user_id=user_id, snapshot_id=snapshot_id)
            if ok:
                await query.edit_message_text("🗑️ 已删除该记忆\n可在主菜单点击「🗂 历史聊天」查看当前记录")
                await query.answer()
            else:
                await query.answer("❌ 快照不存在或无权访问")
        except Exception as e:
            self.logger.error(f"❌ 删除记忆失败: {e}")
            await query.answer("❌ 删除失败，请重试")