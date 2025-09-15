"""
Supabase用户行为记录Repository V2
负责user_action_records_v2表的CRUD操作 - 专注于用户行为详细记录管理

v2版本特点：
1. 记录用户的详细行为信息：行为类型、时间、参数等
2. 支持JSONB类型字段：parameters和message_context
3. 新增action_id UUID字段用于行为唯一标识
4. 包含行为状态、结果URL、错误信息等完整信息
5. 只有created_at字段，没有updated_at字段
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid
from .base_repository_v2 import BaseRepositoryV2
import asyncio


class UserActionRecordRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase用户行为记录数据访问层 V2版本
    
    专注于用户行为记录的CRUD操作：
    - 用户行为详细记录
    - 行为参数和上下文管理
    - 行为状态跟踪
    - 行为历史查询和分析
    """
    
    def __init__(self, supabase_manager):
        # user_action_records_v2表没有updated_at字段，只有created_at
        super().__init__(supabase_manager, 'user_action_records_v2', has_updated_at=False)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户行为记录
        
        包含行为的详细信息和上下文
        """
        try:
            client = self.get_client()
            
            # 设置行为记录数据
            action_record_data = {
                'user_id': data['user_id'],
                'session_id': data.get('session_id'),
                'action_type': data['action_type'],
                'action_time': data.get('action_time', datetime.utcnow().isoformat()),
                'parameters': data.get('parameters'),
                'message_context': data.get('message_context'),
                'status': data.get('status', 'pending'),
                'result_url': data.get('result_url'),
                'error_message': data.get('error_message'),
                'action_id': data.get('action_id', str(uuid.uuid4())),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 过滤有效字段
            allowed_fields = {'user_id', 'session_id', 'action_type', 'action_time', 
                            'parameters', 'message_context', 'status', 'result_url', 
                            'error_message', 'action_id'}
            action_record_data.update({k: v for k, v in data.items() if k in allowed_fields})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(action_record_data)
            
            # 插入数据（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).insert(prepared_data).execute()
            )
            
            if result.data and len(result.data) > 0:
                created_record = result.data[0]
                self.logger.info(f"用户行为记录创建成功: action_type={data['action_type']}, user_id={data['user_id']}")
                return created_record
            else:
                raise Exception("插入用户行为记录失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建用户行为记录失败: {e}")
            raise
    
    async def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取行为记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('id', record_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取行为记录失败: {e}")
            return None
    
    async def get_by_action_id(self, action_id: str) -> Optional[Dict[str, Any]]:
        """根据action_id获取行为记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('action_id', action_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据action_id获取行为记录失败: {e}")
            return None
    
    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新行为记录信息
        
        主要用于更新行为状态、结果URL、错误信息等
        """
        try:
            client = self.get_client()
            
            # 过滤允许更新的字段
            allowed_fields = {'status', 'result_url', 'error_message', 'parameters', 'message_context'}
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
                self.logger.info(f"行为记录更新成功: record_id={record_id}")
                return True
            else:
                self.logger.warning(f"行为记录更新失败: record_id={record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新行为记录失败: {e}")
            return False
    
    async def update_by_action_id(self, action_id: str, data: Dict[str, Any]) -> bool:
        """根据action_id更新行为记录"""
        try:
            record = await self.get_by_action_id(action_id)
            if not record:
                self.logger.warning(f"行为记录不存在: action_id={action_id}")
                return False
            
            return await self.update(record['id'], data)
            
        except Exception as e:
            self.logger.error(f"根据action_id更新行为记录失败: {e}")
            return False
    
    async def delete(self, record_id: int) -> bool:
        """删除行为记录（物理删除）"""
        return await self.hard_delete(record_id)
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个行为记录"""
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
            self.logger.error(f"查找行为记录失败: {e}")
            return None
    
    # ==================== 业务方法 ====================
    
    async def get_user_action_records(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的行为记录列表"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .order('action_time', desc=True))
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取用户行为记录失败: {e}")
            return []
    
    async def get_session_action_records(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的行为记录"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('session_id', session_id)
                    .order('action_time', desc=False))  # 按时间正序，展示行为流程
                    
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取会话行为记录失败: {e}")
            return []
    
    async def get_records_by_action_type(self, action_type: str, user_id: int = None, 
                                       limit: int = 100) -> List[Dict[str, Any]]:
        """根据行为类型获取记录"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('action_type', action_type)
                    .order('action_time', desc=True))
            
            if user_id is not None:
                query = query.eq('user_id', user_id)
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"根据行为类型获取记录失败: {e}")
            return []
    
    async def get_records_by_status(self, status: str, user_id: int = None, 
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """根据状态获取记录"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('status', status)
                    .order('action_time', desc=True))
            
            if user_id is not None:
                query = query.eq('user_id', user_id)
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"根据状态获取记录失败: {e}")
            return []
    
    async def update_action_status(self, action_id: str, status: str, 
                                 result_url: str = None, error_message: str = None) -> bool:
        """更新行为状态（合并原来的多个状态更新方法）
        
        Args:
            action_id: 行为ID
            status: 新状态 ('pending', 'processing', 'completed', 'failed')
            result_url: 结果URL（完成时使用）
            error_message: 错误信息（失败时使用）
        """
        update_data = {'status': status}
        
        if result_url:
            update_data['result_url'] = result_url
        if error_message:
            update_data['error_message'] = error_message
            
        return await self.update_by_action_id(action_id, update_data)
    
    async def get_action_stats(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """获取用户行为统计信息"""
        try:
            client = self.get_client()
            
            # 计算日期范围
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .gte('action_time', from_date))
                    
            result = await asyncio.to_thread(lambda: query.execute())
            records = result.data or []
            
            # 统计信息
            total_actions = len(records)
            
            # 按状态统计
            status_stats = {}
            for record in records:
                status = record.get('status', 'unknown')
                status_stats[status] = status_stats.get(status, 0) + 1
            
            # 按行为类型统计
            action_type_stats = {}
            for record in records:
                action_type = record.get('action_type', 'unknown')
                action_type_stats[action_type] = action_type_stats.get(action_type, 0) + 1
            
            # 成功率计算
            completed_count = status_stats.get('completed', 0)
            failed_count = status_stats.get('failed', 0)
            total_finished = completed_count + failed_count
            success_rate = (completed_count / total_finished * 100) if total_finished > 0 else 0
            
            return {
                'total_actions': total_actions,
                'status_stats': status_stats,
                'action_type_stats': action_type_stats,
                'success_rate': round(success_rate, 2),
                'days': days
            }
            
        except Exception as e:
            self.logger.error(f"获取行为统计失败: {e}")
            return {}
    
    # ==================== 兼容性方法（与原Repository接口保持一致） ====================
    
    async def record_action(self, user_id: int, session_id: str, action_type: str,
                          parameters: Dict[str, Any] = None, message_context: str = None) -> Dict[str, Any]:
        """记录用户行为（兼容原接口）"""
        action_data = {
            'user_id': user_id,
            'session_id': session_id,
            'action_type': action_type,
            'parameters': parameters or {},
            'message_context': message_context,
            'status': 'completed'  # v2默认为completed，而不是success
        }
        return await self.create(action_data)
    
    async def record_error_action(self, user_id: int, session_id: str, action_type: str,
                                error_message: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录失败的用户行为（兼容原接口）"""
        action_data = {
            'user_id': user_id,
            'session_id': session_id,
            'action_type': action_type,
            'parameters': parameters or {},
            'status': 'failed',
            'error_message': error_message
        }
        return await self.create(action_data) 

    # ==================== 业务方法（保持原有逻辑不变） ====================
    
    async def get_by_user_id(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """根据用户ID获取行为记录列表（兼容接口）"""
        try:
            records = await self.find_many(limit=limit, user_id=user_id)
            return records  # 直接返回，无需字段映射
        except Exception as e:
            self.logger.error(f"根据用户ID获取行为记录失败: {e}")
            return []
    
    async def record_action(self, user_id: int, session_id: str, action_type: str, 
                           parameters: Dict[str, Any] = None, message_context: str = None, 
                           points_cost: int = 0) -> Optional[Dict[str, Any]]:
        """记录用户行为（兼容接口）"""
        try:
            # 整合参数，将points_cost放入parameters中
            if parameters is None:
                parameters = {}
            parameters['points_cost'] = points_cost
            
            action_data = {
                'user_id': user_id,
                'session_id': session_id,
                'action_type': action_type,
                'parameters': parameters,
                'message_context': message_context,
                'status': 'success'
            }
            
            record = await self.create(action_data)
            return record  # 直接返回，无需字段映射
        except Exception as e:
            self.logger.error(f"记录用户行为失败: {e}")
            return None 