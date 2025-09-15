"""
Supabase用户会话Repository V2
负责user_sessions_v2表的CRUD操作 - 专注于用户会话基础关联管理

v2版本变化：
1. 表结构极简化：只保留 id, user_id, session_id 三个核心字段
2. 移除了 current_action, session_data, expires_at, created_at, updated_at 字段
3. 专注于用户与会话的基础关联关系管理
4. 复杂的会话状态管理移至其他专门表处理
"""

from typing import Dict, Any, List, Optional
import asyncio
from .base_repository_v2 import BaseRepositoryV2


class UserSessionRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase用户会话数据访问层 V2版本
    
    专注于用户会话基础关联管理：
    - 用户与会话ID的关联关系
    - 会话的基础CRUD操作
    - 用户会话查询和检索
    """
    
    def __init__(self, supabase_manager):
        # user_sessions_v2表没有updated_at字段
        super().__init__(supabase_manager, 'user_sessions_v2', has_updated_at=False)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新会话
        
        v2版本适配：只处理核心字段 user_id, session_id
        """
        try:
            client = self.get_client()
            
            # 设置会话核心数据（仅包含v2表的字段）
            session_data = {
                'user_id': data['user_id'],
                'session_id': data['session_id']
            }
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(session_data)
            
            # 插入数据（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).insert(prepared_data).execute()
            )
            
            if result.data and len(result.data) > 0:
                created_session = result.data[0]
                self.logger.info(f"会话创建成功: session_id={data['session_id']}, user_id={data['user_id']}")
                return created_session
            else:
                raise Exception("插入会话失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建会话失败: {e}")
            raise
    
    async def get_by_id(self, session_record_id: int) -> Optional[Dict[str, Any]]:
        """根据记录ID获取会话"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('id', session_record_id).execute()
            )
            
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
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('session_id', session_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据session_id获取会话失败: {e}")
            return None
    
    async def update(self, session_record_id: int, data: Dict[str, Any]) -> bool:
        """更新会话信息
        
        v2版本适配：由于表结构简化，实际上没有可更新的业务字段
        """
        try:
            # v2表结构极简，除了主键和外键，没有其他可更新字段
            # 这个方法保留主要是为了接口一致性
            self.logger.warning(f"会话表v2版本没有可更新的字段: session_record_id={session_record_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新会话失败: {e}")
            return False
    
    async def delete(self, session_record_id: int) -> bool:
        """删除会话（物理删除）"""
        return await self.hard_delete(session_record_id)
    
    async def delete_by_session_id(self, session_id: str) -> bool:
        """根据session_id删除会话"""
        try:
            session = await self.get_by_session_id(session_id)
            if not session:
                self.logger.warning(f"会话不存在: session_id={session_id}")
                return False
            
            return await self.delete(session['id'])
            
        except Exception as e:
            self.logger.error(f"根据session_id删除会话失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个会话"""
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
            self.logger.error(f"查找会话失败: {e}")
            return None
    
    # ==================== 业务方法（保持原有逻辑，适配简化表结构） ====================
    
    async def get_user_sessions(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户的会话列表"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*').eq('user_id', user_id)
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取用户会话列表失败: {e}")
            return []
    
    async def get_sessions_by_user_ids(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        """批量获取多个用户的会话"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').in_('user_id', user_ids).execute()
            )
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"批量获取用户会话失败: {e}")
            return []
    
    async def check_session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return await self.exists(session_id=session_id)
    
    async def get_user_session_count(self, user_id: int) -> int:
        """获取用户的会话数量"""
        try:
            return await self.count(user_id=user_id)
        except Exception as e:
            self.logger.error(f"获取用户会话数量失败: {e}")
            return 0
    
    async def cleanup_user_sessions(self, user_id: int) -> int:
        """清理用户的所有会话"""
        try:
            client = self.get_client()
            
            # 查找用户的所有会话
            sessions = await self.get_user_sessions(user_id)
            if not sessions:
                return 0
            
            session_ids = [session['id'] for session in sessions]
            
            # 批量删除
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).delete().in_('id', session_ids).execute()
            )
            
            deleted_count = len(result.data) if result.data else 0
            self.logger.info(f"清理用户会话成功: user_id={user_id}, count={deleted_count}")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"清理用户会话失败: {e}")
            return 0
    
    async def batch_create_sessions(self, sessions_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量创建会话"""
        try:
            prepared_sessions = []
            
            for data in sessions_data:
                session_data = {
                    'user_id': data['user_id'],
                    'session_id': data['session_id']
                }
                prepared_sessions.append(session_data)
            
            # 批量插入
            return await self.bulk_insert(prepared_sessions)
            
        except Exception as e:
            self.logger.error(f"批量创建会话失败: {e}")
            raise 