"""
Supabase消息仓储
负责消息数据的持久化操作
"""

import logging
import uuid
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
                          message: str, sender: str) -> Optional[str]:
        """
        保存消息到Supabase
        
        Args:
            user_id: 用户ID (TEXT格式，如Telegram用户ID)
            role_id: 角色ID (TEXT格式，可为None) 
            session_id: 会话ID (TEXT格式，如sess_xxxxxxxx)
            message: 消息内容
            sender: 发送者 ('user' 或 'bot')
            
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
                "sender": str(sender).strip()
                # timestamp 和 last_interaction 由数据库触发器自动设置为东八区时间
            }
            
            # 插入数据
            result = client.table(self.table_name).insert(message_data).execute()
            
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
            
            result = client.table(self.table_name)\
                .select("*")\
                .eq("session_id", session_id)\
                .order("timestamp", desc=False)\
                .limit(limit)\
                .execute()
            
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
            
            query = client.table(self.table_name)\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .eq("sender", "user")  # 只统计用户发送的消息
            
            if date_from:
                query = query.gte("timestamp", date_from.isoformat())
            
            result = query.execute()
            
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
            
            query = client.table(self.table_name)\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .eq("sender", "user")\
                .gte("timestamp", today_start_utc.isoformat())
            
            result = query.execute()
            
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
            
            result = client.table(self.table_name)\
                .delete()\
                .eq("session_id", session_id)\
                .execute()
            
            self.logger.info(f"🗑️ 删除会话消息: session_id={session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 删除会话消息失败: {e}")
            return False
