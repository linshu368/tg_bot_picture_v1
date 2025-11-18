"""
Supabase消息仓储
负责消息数据的持久化操作
"""

import logging
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from .supabase_manager import SupabaseManager


class SupabaseMessageRepository:
    """Supabase消息仓储"""
    
    def __init__(self, supabase_manager: SupabaseManager):
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        self.table_name = "messages"
    
    async def save_message(self, user_id: str, role_id: Optional[str], session_id: str, 
                          message: str, sender: str,
                          system_instructions: Optional[str] = None,
                          ongoing_instructions: Optional[str] = None,
                          # 🆕 新字段写入逻辑（过渡期与旧字段并存）
                          instructions: Optional[str] = None,
                          bot_reply: Optional[str] = None,
                          history: Optional[str] = None,
                          model_name: Optional[str] = None,
                          user_input: Optional[str] = None,
                          round: Optional[int] = None) -> Optional[str]:
        """
        保存消息到Supabase
        
        Args:
            user_id: 用户ID (TEXT格式，如Telegram用户ID)
            role_id: 角色ID (TEXT格式，可为None) 
            session_id: 会话ID (TEXT格式，如sess_xxxxxxxx)
            message: 消息内容
            sender: 发送者 ('user' 或 'bot')
            system_instructions: 系统指令（前3轮用户消息使用）
            ongoing_instructions: 持续指令（第4轮及以后用户消息使用）
            
        Returns:
            消息记录的ID，失败返回None
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 数据验证和转换
            if not user_id or not user_id.strip():
                self.logger.error("❌ user_id 不能为空")
                return None
            
            if not message or not message.strip():
                self.logger.error("❌ message 不能为空")
                return None
            
            if sender not in ['user', 'bot']:
                self.logger.error(f"❌ sender 必须是 'user' 或 'bot'，当前值: {sender}")
                return None
            
            # 构造消息数据
            message_data = {
                "user_id": str(user_id).strip(),
                "role_id": str(role_id).strip() if role_id else None, 
                "session_id": str(session_id).strip() if session_id else None,
                "message": str(message).strip(),
                "sender": str(sender).strip(),
                "system_instructions": system_instructions,
                "ongoing_instructions": ongoing_instructions
                # timestamp 和 last_interaction 由数据库触发器自动设置为东八区时间
            }
            # 🆕 新字段写入逻辑：按有值追加至入库载荷（与旧字段并存，后续可移除旧字段）
            # 注意：这些字段主要随“用户行（sender='user'）”一并保存
            if instructions is not None:
                message_data["instructions"] = instructions
            if bot_reply is not None:
                message_data["bot_reply"] = bot_reply
            if history is not None:
                message_data["history"] = history
            if model_name is not None:
                message_data["model_name"] = model_name
            if user_input is not None:
                message_data["user_input"] = user_input
            if round is not None:
                message_data["round"] = round
            
            # 异步插入数据（使用线程池避免阻塞主线程）
            def _sync_insert():
                return client.table(self.table_name).insert(message_data).execute()
            
            result = await asyncio.to_thread(_sync_insert)
            
            if result.data and len(result.data) > 0:
                record_id = result.data[0].get('id')
                self.logger.info(f"✅ 消息已保存到Supabase: id={record_id}, user_id={user_id}, sender={sender}")
                return str(record_id)
            else:
                self.logger.error(f"❌ 保存消息失败: 无返回数据")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 保存消息到Supabase失败: {e}")
            return None
    
    async def get_messages_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        根据会话ID获取消息历史
        
        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            
        Returns:
            消息列表，按时间戳排序
        """
        try:
            client = self.supabase_manager.get_client()
            
            def _sync_select():
                return client.table(self.table_name)\
                    .select("*")\
                    .eq("session_id", session_id)\
                    .order("timestamp", desc=False)\
                    .limit(limit)\
                    .execute()
            
            result = await asyncio.to_thread(_sync_select)
            
            if result.data:
                self.logger.info(f"📚 获取会话消息: session_id={session_id}, count={len(result.data)}")
                return result.data
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"❌ 获取会话消息失败: {e}")
            return []
    
    async def get_user_message_count(self, user_id: str, date_from: Optional[datetime] = None) -> int:
        """
        获取用户消息数量统计
        
        Args:
            user_id: 用户ID
            date_from: 统计起始时间，None表示全部时间
            
        Returns:
            消息数量
        """
        try:
            client = self.supabase_manager.get_client()
            
            def _sync_count():
                query = client.table(self.table_name)\
                    .select("id", count="exact")\
                    .eq("user_id", user_id)\
                    .eq("sender", "user")  # 只统计用户发送的消息
                
                if date_from:
                    query = query.gte("timestamp", date_from.isoformat())
                
                return query.execute()
            
            result = await asyncio.to_thread(_sync_count)
            
            return result.count or 0
            
        except Exception as e:
            self.logger.error(f"❌ 获取用户消息数量失败: {e}")
            return 0
    
    async def get_user_daily_message_count(self, user_id: str) -> int:
        """
        获取用户今日消息数量统计（按东八区时间计算）
        
        Args:
            user_id: 用户ID
            
        Returns:
            今日消息数量
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 获取东八区今日开始时间（UTC+8）
            from datetime import datetime, timezone, timedelta
            beijing_tz = timezone(timedelta(hours=8))
            now_beijing = datetime.now(beijing_tz)
            today_start_beijing = now_beijing.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 转换为UTC时间用于数据库查询
            today_start_utc = today_start_beijing.astimezone(timezone.utc)
            
            def _sync_daily_count():
                return client.table(self.table_name)\
                    .select("id", count="exact")\
                    .eq("user_id", user_id)\
                    .eq("sender", "user")\
                    .gte("timestamp", today_start_utc.isoformat())\
                    .execute()
            
            result = await asyncio.to_thread(_sync_daily_count)
            
            count = result.count or 0
            self.logger.info(f"📊 用户今日消息统计: user_id={user_id}, count={count}")
            return count
            
        except Exception as e:
            self.logger.error(f"❌ 获取用户今日消息数量失败: {e}")
            return 0
    
    async def delete_messages_by_session(self, session_id: str) -> bool:
        """
        删除指定会话的所有消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        try:
            client = self.supabase_manager.get_client()
            
            def _sync_delete():
                return client.table(self.table_name)\
                    .delete()\
                    .eq("session_id", session_id)\
                    .execute()
            
            result = await asyncio.to_thread(_sync_delete)
            
            self.logger.info(f"🗑️ 删除会话消息: session_id={session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 删除会话消息失败: {e}")
            return False
    
    def save_user_message_with_real_instructions_async(self, user_id: str, role_id: Optional[str], 
                                                      session_id: str, message: str,
                                                      system_instructions: Optional[str] = None,
                                                      ongoing_instructions: Optional[str] = None,
                                                      # 🆕 新字段写入逻辑（过渡期与旧字段并存）
                                                      instructions: Optional[str] = None,
                                                      bot_reply: Optional[str] = None,
                                                      history: Optional[str] = None,
                                                      model_name: Optional[str] = None,
                                                      user_input: Optional[str] = None,
                                                      round: Optional[int] = None) -> asyncio.Task:
        """
        异步保存用户消息（使用AI生成时的真实指令内容）
        
        这是推荐的保存方式，确保保存的指令与AI调用时完全一致
        
        Args:
            user_id: 用户ID
            role_id: 角色ID
            session_id: 会话ID
            message: 消息内容
            system_instructions: AI生成时实际使用的系统指令
            ongoing_instructions: AI生成时实际使用的持续指令
            
        Returns:
            asyncio.Task: 可以await的任务对象
        """
        async def _safe_save():
            try:
                result = await self.save_message(
                    user_id=user_id,
                    role_id=role_id,
                    session_id=session_id,
                    message=message,
                    sender="user",
                    system_instructions=system_instructions,
                    ongoing_instructions=ongoing_instructions,
                    # 🆕 新字段写入逻辑：透传到基础保存方法
                    instructions=instructions,
                    bot_reply=bot_reply,
                    history=history,
                    model_name=model_name,
                    user_input=user_input,
                    round=round
                )
                
                if result:
                    instruction_type = "系统指令" if system_instructions else "持续指令" if ongoing_instructions else "无指令"
                    self.logger.debug(f"🔄 异步保存用户消息成功（真实指令）: id={result}, 指令类型={instruction_type}")
                else:
                    self.logger.warning(f"⚠️ 异步保存用户消息失败: session={session_id}")
            except Exception as e:
                self.logger.error(f"❌ 异步保存用户消息异常: {e}")
        
        return asyncio.create_task(_safe_save())
    
    async def _get_last_message_by_sender(self, session_id: str, sender: str) -> Optional[Dict[str, Any]]:
        """获取某会话中指定sender的最新一条消息"""
        try:
            client = self.supabase_manager.get_client()
            def _sync_select_last():
                return client.table(self.table_name)\
                    .select("id")\
                    .eq("session_id", session_id)\
                    .eq("sender", sender)\
                    .order("timestamp", desc=True)\
                    .limit(1)\
                    .execute()
            result = await asyncio.to_thread(_sync_select_last)
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取最新消息失败: session_id={session_id}, sender={sender}, err={e}")
            return None
    
    async def delete_last_bot_message(self, session_id: str) -> bool:
        """删除会话中最新一条机器人消息（用于重新生成时清理旧回复）"""
        try:
            last_bot = await self._get_last_message_by_sender(session_id, "bot")
            if not last_bot:
                return True
            msg_id = last_bot.get("id")
            client = self.supabase_manager.get_client()
            def _sync_delete():
                return client.table(self.table_name)\
                    .delete()\
                    .eq("id", msg_id)\
                    .execute()
            await asyncio.to_thread(_sync_delete)
            self.logger.info(f"🗑️ 已删除最新机器人消息: session_id={session_id}, id={msg_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 删除最新机器人消息失败: session_id={session_id}, err={e}")
            return False
    
    async def update_last_user_message_reply(self, session_id: str, 
                                            bot_reply: Optional[str] = None,
                                            history: Optional[str] = None,
                                            model_name: Optional[str] = None) -> bool:
        """
        更新会话中最新一条用户消息的回复相关字段（用于重新生成时覆盖旧 bot_reply/history/model）
        """
        try:
            last_user = await self._get_last_message_by_sender(session_id, "user")
            if not last_user:
                return False
            msg_id = last_user.get("id")
            payload: Dict[str, Any] = {}
            if bot_reply is not None:
                payload["bot_reply"] = bot_reply
            if history is not None:
                payload["history"] = history
            if model_name is not None:
                payload["model_name"] = model_name
            if not payload:
                return True
            client = self.supabase_manager.get_client()
            def _sync_update():
                return client.table(self.table_name)\
                    .update(payload)\
                    .eq("id", msg_id)\
                    .execute()
            await asyncio.to_thread(_sync_update)
            self.logger.info(f"✏️ 已更新最新用户消息: session_id={session_id}, id={msg_id}, fields={list(payload.keys())}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 更新最新用户消息失败: session_id={session_id}, err={e}")
            return False
    
    def save_bot_message_async(self, user_id: str, role_id: Optional[str], 
                              session_id: str, message: str) -> asyncio.Task:
        """
        异步保存机器人消息（不阻塞主流程）
        
        Args:
            user_id: 用户ID
            role_id: 角色ID
            session_id: 会话ID
            message: 消息内容
            
        Returns:
            asyncio.Task: 可以await的任务对象
        """
        async def _safe_save():
            try:
                result = await self.save_message(
                    user_id, role_id, session_id, message, "bot"
                    # bot消息不需要指令，使用默认的None值
                )
                if result:
                    self.logger.debug(f"🔄 异步保存机器人消息成功: id={result}")
                else:
                    self.logger.warning(f"⚠️ 异步保存机器人消息失败: session={session_id}")
            except Exception as e:
                self.logger.error(f"❌ 异步保存机器人消息异常: {e}")
        
        return asyncio.create_task(_safe_save())
