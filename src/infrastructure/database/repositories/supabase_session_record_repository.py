"""
Supabase会话记录Repository
负责会话记录数据的CRUD操作 - Supabase版本
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .supabase_base_repository import SupabaseBaseRepository


class SupabaseSessionRecordRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase会话记录数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'session_records')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新会话记录"""
        try:
            client = self.get_client()
            
            # 设置默认值
            record_data = {
                'user_id': data['user_id'],
                'session_id': data['session_id'],
                'started_at': data.get('started_at', datetime.utcnow().isoformat()),
                'ended_at': data.get('ended_at'),
                'message_count_user': data.get('message_count_user', 0),
                'duration_sec': data.get('duration_sec'),
                'summary': data.get('summary'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 合并传入的数据
            record_data.update({k: v for k, v in data.items() if k not in ['id']})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(record_data)
            
            # 插入数据
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data and len(result.data) > 0:
                created_record = result.data[0]
                self.logger.info(f"会话记录创建成功: session_id={data['session_id']}")
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
            result = client.table(self.table_name).select('*').eq('id', record_id).execute()
            
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
            result = client.table(self.table_name).select('*').eq('session_id', session_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据session_id获取会话记录失败: {e}")
            return None
    
    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新会话记录"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', record_id).execute()
            
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
        """删除会话记录"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', record_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"会话记录删除成功: record_id={record_id}")
                return True
            else:
                self.logger.warning(f"会话记录删除失败: record_id={record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除会话记录失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个会话记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.limit(1)
            
            result = query.execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"查找会话记录失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个会话记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order('started_at', desc=True)
            
            if limit is not None and offset is not None:
                end_index = offset + limit - 1
                query = query.range(offset, end_index)
            elif limit is not None:
                query = query.limit(limit)
            elif offset is not None:
                query = query.range(offset, offset + 999)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"查找多个会话记录失败: {e}")
            return []
    
    async def start_session(self, user_id: int, session_id: str) -> Dict[str, Any]:
        """开始新会话"""
        try:
            session_data = {
                'user_id': user_id,
                'session_id': session_id,
                'started_at': datetime.utcnow().isoformat(),
                'message_count_user': 0
            }
            
            return await self.create(session_data)
            
        except Exception as e:
            self.logger.error(f"开始会话失败: {e}")
            raise
    
    async def end_session(self, session_id: str, summary: str = None) -> bool:
        """结束会话"""
        try:
            # 获取现有会话记录
            record = await self.get_by_session_id(session_id)
            if not record:
                self.logger.warning(f"会话记录不存在: {session_id}")
                return False
            
            ended_at = datetime.utcnow()
            started_at = datetime.fromisoformat(record['started_at'].replace('Z', '+00:00'))
            duration_sec = int((ended_at - started_at).total_seconds())
            
            # 更新结束时间和统计信息
            update_data = {
                'ended_at': ended_at.isoformat(),
                'duration_sec': duration_sec,
                'summary': summary
            }
            
            return await self.update(record['id'], update_data)
            
        except Exception as e:
            self.logger.error(f"结束会话失败: {e}")
            return False
    
    async def increment_message_count(self, session_id: str) -> bool:
        """增加消息计数"""
        try:
            record = await self.get_by_session_id(session_id)
            if not record:
                return False
            
            new_count = record['message_count_user'] + 1
            return await self.update(record['id'], {'message_count_user': new_count})
            
        except Exception as e:
            self.logger.error(f"增加消息计数失败: {e}")
            return False
    
    async def get_user_sessions(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户的会话记录"""
        return await self.find_many(limit=limit, user_id=user_id)
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """获取活跃的会话（未结束的）"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*').is_('ended_at', None)
            query = query.order('started_at', desc=True)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取活跃会话失败: {e}")
            return []