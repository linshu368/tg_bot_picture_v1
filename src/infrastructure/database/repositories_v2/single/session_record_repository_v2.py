"""
Supabase会话记录Repository V2
负责session_records_v2表的CRUD操作 - 专注于会话详细统计信息管理

v2版本特点：
1. 记录会话的完整生命周期信息：开始时间、结束时间、持续时间
2. 统计会话中的用户消息数量
3. 支持会话总结信息存储
4. 只有created_at字段，没有updated_at字段
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base_repository_v2 import BaseRepositoryV2
import asyncio


class SessionRecordRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase会话记录数据访问层 V2版本
    
    专注于会话统计信息的CRUD操作：
    - 会话生命周期记录
    - 会话统计数据管理
    - 会话历史查询和分析
    """
    
    def __init__(self, supabase_manager):
        # session_records_v2表没有updated_at字段，只有created_at
        super().__init__(supabase_manager, 'session_records_v2', has_updated_at=False)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建会话记录
        
        包含会话的详细统计信息
        """
        try:
            client = self.get_client()
            
            # 设置会话记录数据
            session_record_data = {
                'user_id': data['user_id'],
                'session_id': data['session_id'],
                'started_at': data.get('started_at'),
                'ended_at': data.get('ended_at'),
                'message_count_user': data.get('message_count_user', 0),
                'duration_sec': data.get('duration_sec'),
                'summary': data.get('summary'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 过滤有效字段
            allowed_fields = {'user_id', 'session_id', 'started_at', 'ended_at', 
                            'message_count_user', 'duration_sec', 'summary'}
            session_record_data.update({k: v for k, v in data.items() if k in allowed_fields})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(session_record_data)
            
            # 插入数据（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).insert(prepared_data).execute()
            )
            
            if result.data and len(result.data) > 0:
                created_record = result.data[0]
                self.logger.info(f"会话记录创建成功: session_id={data['session_id']}, user_id={data['user_id']}")
                return created_record
            else:
                raise Exception("插入会话记录失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建会话记录失败: {e}")
            raise
    
    async def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取会话记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('id', record_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取会话记录失败: {e}")
            return None
    
    async def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """根据session_id获取会话记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('session_id', session_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据session_id获取会话记录失败: {e}")
            return None
    
    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新会话记录信息
        
        主要用于更新会话结束信息和统计数据
        """
        try:
            client = self.get_client()
            
            # 过滤允许更新的字段
            allowed_fields = {'ended_at', 'message_count_user', 'duration_sec', 'summary'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: record_id={record_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 执行更新（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).update(prepared_data).eq('id', record_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"会话记录更新成功: record_id={record_id}")
                return True
            else:
                self.logger.warning(f"会话记录更新失败: record_id={record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新会话记录失败: {e}")
            return False
    
    async def delete(self, record_id: int) -> bool:
        """删除会话记录（物理删除）"""
        return await self.hard_delete(record_id)
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个会话记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.limit(1)
            
            result = await asyncio.to_thread(lambda: query.execute())
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"查找会话记录失败: {e}")
            return None
    
    # ==================== 业务方法 ====================
    
    async def get_user_session_records(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户的会话记录列表"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .order('created_at', desc=True))
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取用户会话记录失败: {e}")
            return []
    
    async def get_active_sessions(self, user_id: int = None) -> List[Dict[str, Any]]:
        """获取活跃会话（尚未结束的会话）"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*').is_('ended_at', 'null')
            
            if user_id is not None:
                query = query.eq('user_id', user_id)
                
            query = query.order('started_at', desc=True)
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取活跃会话失败: {e}")
            return []
    
    async def close_session(self, session_id: str, message_count_user: int = None, 
                          summary: str = None) -> bool:
        """关闭会话
        
        设置结束时间并计算持续时间，更新统计信息
        """
        try:
            # 获取会话记录
            record = await self.get_by_session_id(session_id)
            if not record:
                self.logger.warning(f"会话记录不存在: session_id={session_id}")
                return False
            
            if record.get('ended_at'):
                self.logger.info(f"会话已经结束: session_id={session_id}")
                return True
            
            # 计算持续时间
            ended_at = datetime.utcnow()
            duration_sec = None
            
            if record.get('started_at'):
                try:
                    if isinstance(record['started_at'], str):
                        started_at = datetime.fromisoformat(record['started_at'].replace('Z', '+00:00'))
                    else:
                        started_at = record['started_at']
                    
                    duration_sec = int((ended_at - started_at).total_seconds())
                except Exception as e:
                    self.logger.warning(f"计算会话持续时间失败: {e}")
            
            # 更新会话结束信息
            update_data = {
                'ended_at': ended_at.isoformat(),
                'duration_sec': duration_sec
            }
            
            if message_count_user is not None:
                update_data['message_count_user'] = message_count_user
            
            if summary is not None:
                update_data['summary'] = summary
            
            return await self.update(record['id'], update_data)
            
        except Exception as e:
            self.logger.error(f"关闭会话失败: {e}")
            return False
    
    async def get_session_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取用户会话统计信息"""
        try:
            client = self.get_client()
            
            # 计算日期范围
            
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .gte('created_at', from_date))
                    
            result = await asyncio.to_thread(lambda: query.execute())
            records = result.data or []
            
            # 统计信息
            total_sessions = len(records)
            completed_sessions = [r for r in records if r.get('ended_at')]
            active_sessions = total_sessions - len(completed_sessions)
            
            total_messages = sum(r.get('message_count_user', 0) for r in records)
            total_duration = sum(r.get('duration_sec', 0) for r in completed_sessions if r.get('duration_sec'))
            avg_duration = total_duration / len(completed_sessions) if completed_sessions else 0
            avg_messages = total_messages / total_sessions if total_sessions else 0
            
            return {
                'total_sessions': total_sessions,
                'completed_sessions': len(completed_sessions),
                'active_sessions': active_sessions,
                'total_messages': total_messages,
                'total_duration_sec': total_duration,
                'avg_duration_sec': round(avg_duration, 2),
                'avg_messages_per_session': round(avg_messages, 2),
                'days': days
            }
            
        except Exception as e:
            self.logger.error(f"获取会话统计失败: {e}")
            return {}
    
    async def cleanup_old_sessions(self, days: int = 90) -> int:
        """清理旧的会话记录"""
        try:
            
            client = self.get_client()
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # 查找旧记录（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('id').lt('created_at', cutoff_date).execute()
            )
            old_records = result.data or []
            
            if not old_records:
                return 0
            
            old_ids = [r['id'] for r in old_records]
            
            # 批量删除（后台线程执行，避免阻塞事件循环）
            delete_result = await asyncio.to_thread(
                lambda: client.table(self.table_name).delete().in_('id', old_ids).execute()
            )
            deleted_count = len(delete_result.data) if delete_result.data else 0
            
            self.logger.info(f"清理旧会话记录成功: count={deleted_count}, days={days}")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"清理旧会话记录失败: {e}")
            return 0
    
    async def update_message_count(self, session_id: str, message_count: int) -> bool:
        """更新会话的消息数量"""
        try:
            record = await self.get_by_session_id(session_id)
            if not record:
                self.logger.warning(f"会话记录不存在: session_id={session_id}")
                return False
            
            return await self.update(record['id'], {'message_count_user': message_count})
            
        except Exception as e:
            self.logger.error(f"更新会话消息数量失败: {e}")
            return False 