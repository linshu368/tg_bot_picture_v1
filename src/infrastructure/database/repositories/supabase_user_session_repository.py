"""
Supabase用户会话Repository
负责用户会话数据的CRUD操作 - Supabase版本
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .supabase_base_repository import SupabaseBaseRepository


class SupabaseUserSessionRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase用户会话数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'user_sessions')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新会话"""
        try:
            client = self.get_client()
            
            # 设置默认值
            session_data = {
                'user_id': data['user_id'],
                'session_id': data['session_id'],
                'current_action': data.get('current_action'),
                'session_data': data.get('session_data', {}),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'expires_at': data.get('expires_at')
            }
            
            # 合并传入的数据
            session_data.update({k: v for k, v in data.items() if k not in ['id']})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(session_data)
            
            # 插入数据
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data and len(result.data) > 0:
                created_session = result.data[0]
                self.logger.info(f"会话创建成功: session_id={data['session_id']}")
                return created_session
            else:
                raise Exception("插入会话失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建会话失败: {e}")
            raise
    
    async def get_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取会话"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', session_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取会话失败: {e}")
            return None
    
    async def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """根据session_id获取会话"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('session_id', session_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据session_id获取会话失败: {e}")
            return None
    
    async def update(self, session_id: int, data: Dict[str, Any]) -> bool:
        """更新会话信息"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', session_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"会话更新成功: session_id={session_id}")
                return True
            else:
                self.logger.warning(f"会话更新失败: session_id={session_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新会话失败: {e}")
            return False
    
    async def delete(self, session_id: int) -> bool:
        """删除会话"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', session_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"会话删除成功: session_id={session_id}")
                return True
            else:
                self.logger.warning(f"会话删除失败: session_id={session_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除会话失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个会话"""
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
            self.logger.error(f"查找会话失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个会话"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            
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
            self.logger.error(f"查找多个会话失败: {e}")
            return []
    
    async def update_session_data(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """更新会话数据"""
        try:
            session = await self.get_by_session_id(session_id)
            if not session:
                return False
            
            return await self.update(session['id'], {
                'session_data': session_data,
                'updated_at': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"更新会话数据失败: {e}")
            return False
    
    async def update_current_action(self, session_id: str, action: str) -> bool:
        """更新当前操作"""
        try:
            session = await self.get_by_session_id(session_id)
            if not session:
                return False
            
            return await self.update(session['id'], {
                'current_action': action,
                'updated_at': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"更新当前操作失败: {e}")
            return False
    
    async def get_user_sessions(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户的会话列表"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*').eq('user_id', user_id)
            query = query.order('updated_at', desc=True).limit(limit)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取用户会话列表失败: {e}")
            return []
    
    async def cleanup_expired_sessions(self) -> int:
        """清理过期的会话"""
        try:
            client = self.get_client()
            current_time = datetime.utcnow().isoformat()
            
            # 查找过期的会话
            result = client.table(self.table_name).select('id').lt('expires_at', current_time).execute()
            
            if result.data:
                expired_ids = [session['id'] for session in result.data]
                
                # 删除过期会话
                delete_result = client.table(self.table_name).delete().in_('id', expired_ids).execute()
                
                deleted_count = len(delete_result.data) if delete_result.data else 0
                self.logger.info(f"清理过期会话成功: {deleted_count} 个")
                return deleted_count
            
            return 0
            
        except Exception as e:
            self.logger.error(f"清理过期会话失败: {e}")
            return 0