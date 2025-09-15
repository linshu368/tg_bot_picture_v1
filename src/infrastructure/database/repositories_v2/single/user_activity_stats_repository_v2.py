"""
Supabase用户活动统计Repository V2
负责user_activity_stats_v2表的CRUD操作 - 专注于用户活动统计信息管理

v2版本特点：
1. 用户活动统计信息管理：会话数量、消息总数、活动时间等
2. 每个用户只有一条记录（user_id UNIQUE约束）
3. 没有updated_at字段，只有基础统计字段
4. 专注于活动数据的聚合统计
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_repository_v2 import BaseRepositoryV2
import asyncio


class UserActivityStatsRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase用户活动统计数据访问层 V2版本
    
    专注于用户活动统计的CRUD操作：
    - 用户活动统计记录管理
    - 统计数据更新
    - 活动数据查询
    """
    
    def __init__(self, supabase_manager):
        # user_activity_stats_v2表没有updated_at字段
        super().__init__(supabase_manager, 'user_activity_stats_v2', has_updated_at=False)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户活动统计记录
        
        为新用户创建初始统计记录
        """
        try:
            client = self.get_client()
            
            # 设置活动统计数据
            stats_data = {
                'user_id': data['user_id'],
                'session_count': data.get('session_count', 0),
                'total_messages_sent': data.get('total_messages_sent', 0),
                'first_active_time': data.get('first_active_time'),
                'last_active_time': data.get('last_active_time')
            }
            
            # 过滤有效字段
            allowed_fields = {'user_id', 'session_count', 'total_messages_sent', 
                            'first_active_time', 'last_active_time'}
            stats_data.update({k: v for k, v in data.items() if k in allowed_fields})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(stats_data)
            
            # 插入数据（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).insert(prepared_data).execute()
            )
            
            if result.data and len(result.data) > 0:
                created_stats = result.data[0]
                self.logger.info(f"用户活动统计创建成功: user_id={data['user_id']}")
                return created_stats
            else:
                raise Exception("插入用户活动统计失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建用户活动统计失败: {e}")
            raise
    
    async def get_by_id(self, stats_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取活动统计记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('id', stats_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取活动统计失败: {e}")
            return None
    
    async def get_by_user_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据用户ID获取活动统计记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('user_id', user_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据用户ID获取活动统计失败: {e}")
            return None
    
    async def update(self, stats_id: int, data: Dict[str, Any]) -> bool:
        """更新活动统计信息"""
        try:
            client = self.get_client()
            
            # 过滤允许更新的字段
            allowed_fields = {'session_count', 'total_messages_sent', 'first_active_time', 'last_active_time'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: stats_id={stats_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 执行更新（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).update(prepared_data).eq('id', stats_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"活动统计更新成功: stats_id={stats_id}")
                return True
            else:
                self.logger.warning(f"活动统计更新失败: stats_id={stats_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新活动统计失败: {e}")
            return False
    
    async def update_by_user_id(self, user_id: int, data: Dict[str, Any]) -> bool:
        """根据用户ID更新活动统计"""
        try:
            stats = await self.get_by_user_id(user_id)
            if not stats:
                self.logger.warning(f"用户活动统计不存在: user_id={user_id}")
                return False
            
            return await self.update(stats['id'], data)
            
        except Exception as e:
            self.logger.error(f"根据用户ID更新活动统计失败: {e}")
            return False
    
    async def delete(self, stats_id: int) -> bool:
        """删除活动统计记录（物理删除）"""
        return await self.hard_delete(stats_id)
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个活动统计记录"""
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
            self.logger.error(f"查找活动统计失败: {e}")
            return None
    
    # ==================== 业务方法 ====================
    
    async def get_or_create_user_stats(self, user_id: int) -> Dict[str, Any]:
        """获取或创建用户活动统计记录"""
        try:
            # 先尝试获取现有记录
            stats = await self.get_by_user_id(user_id)
            
            if stats:
                return stats
            
            # 如果不存在，创建新记录
            current_time = datetime.utcnow().isoformat()
            stats_data = {
                'user_id': user_id,
                'session_count': 0,
                'total_messages_sent': 0,
                'first_active_time': current_time,
                'last_active_time': current_time
            }
            
            return await self.create(stats_data)
            
        except Exception as e:
            self.logger.error(f"获取或创建用户活动统计失败: {e}")
            raise
    
    async def increment_session_count(self, user_id: int) -> bool:
        """增加用户会话计数"""
        try:
            stats = await self.get_or_create_user_stats(user_id)
            
            update_data = {
                'session_count': stats['session_count'] + 1,
                'last_active_time': datetime.utcnow().isoformat()
            }
            
            return await self.update(stats['id'], update_data)
            
        except Exception as e:
            self.logger.error(f"增加会话计数失败: {e}")
            return False
    
    async def increment_message_count(self, user_id: int, count: int = 1) -> bool:
        """增加用户消息计数"""
        try:
            stats = await self.get_or_create_user_stats(user_id)
            
            update_data = {
                'total_messages_sent': stats['total_messages_sent'] + count,
                'last_active_time': datetime.utcnow().isoformat()
            }
            
            return await self.update(stats['id'], update_data)
            
        except Exception as e:
            self.logger.error(f"增加消息计数失败: {e}")
            return False
    
    async def update_last_active_time(self, user_id: int) -> bool:
        """更新用户最后活跃时间"""
        try:
            stats = await self.get_or_create_user_stats(user_id)
            
            update_data = {
                'last_active_time': datetime.utcnow().isoformat()
            }
            
            return await self.update(stats['id'], update_data)
            
        except Exception as e:
            self.logger.error(f"更新最后活跃时间失败: {e}")
            return False
    
    async def get_active_users_stats(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最活跃用户的统计信息"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .order('total_messages_sent', desc=True))
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取活跃用户统计失败: {e}")
            return []
    
    # ==================== 兼容性方法（与原Repository接口保持一致） ====================
    
    async def create_user_stats(self, user_id: int) -> Dict[str, Any]:
        """创建用户统计记录（兼容原接口）"""
        current_time = datetime.utcnow().isoformat()
        stats_data = {
            'user_id': user_id,
            'session_count': 0,
            'total_messages_sent': 0,
            'first_active_time': current_time,
            'last_active_time': current_time
        }
        return await self.create(stats_data) 