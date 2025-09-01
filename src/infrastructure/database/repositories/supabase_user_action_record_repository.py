"""
Supabase用户行为记录Repository
负责用户行为记录数据的CRUD操作 - Supabase版本
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .supabase_base_repository import SupabaseBaseRepository


class SupabaseUserActionRecordRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase用户行为记录数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'user_action_records')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新行为记录"""
        try:
            client = self.get_client()
            
            # 设置默认值
            action_data = {
                'user_id': data['user_id'],
                'session_id': data['session_id'],
                'action_type': data['action_type'],
                'action_time': data.get('action_time', datetime.utcnow().isoformat()),
                'parameters': data.get('parameters', {}),
                'message_context': data.get('message_context'),
                'status': data.get('status', 'success'),
                'points_cost': data.get('points_cost', 0),
                'result_url': data.get('result_url'),
                'error_message': data.get('error_message'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 合并传入的数据
            action_data.update({k: v for k, v in data.items() if k not in ['id']})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(action_data)
            
            # 插入数据
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data and len(result.data) > 0:
                created_record = result.data[0]
                self.logger.info(f"行为记录创建成功: action_type={data['action_type']}")
                return created_record
            else:
                raise Exception("插入行为记录失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建行为记录失败: {e}")
            raise
    
    async def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取行为记录"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', record_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取行为记录失败: {e}")
            return None
    
    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新行为记录"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', record_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"行为记录更新成功: record_id={record_id}")
                return True
            else:
                self.logger.warning(f"行为记录更新失败: record_id={record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新行为记录失败: {e}")
            return False
    
    async def delete(self, record_id: int) -> bool:
        """删除行为记录"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', record_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"行为记录删除成功: record_id={record_id}")
                return True
            else:
                self.logger.warning(f"行为记录删除失败: record_id={record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除行为记录失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个行为记录"""
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
            self.logger.error(f"查找行为记录失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个行为记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order('action_time', desc=True)
            
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
            self.logger.error(f"查找多个行为记录失败: {e}")
            return []
    
    async def record_action(self, user_id: int, session_id: str, action_type: str,
                           parameters: Dict[str, Any] = None, message_context: str = None,
                           points_cost: int = 0) -> Dict[str, Any]:
        """记录用户行为"""
        try:
            action_data = {
                'user_id': user_id,
                'session_id': session_id,
                'action_type': action_type,
                'action_time': datetime.utcnow().isoformat(),
                'parameters': parameters or {},
                'message_context': message_context,
                'status': 'success',
                'points_cost': points_cost
            }
            
            return await self.create(action_data)
            
        except Exception as e:
            self.logger.error(f"记录用户行为失败: {e}")
            raise
    
    async def record_error_action(self, user_id: int, session_id: str, action_type: str,
                                 error_message: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录失败的用户行为"""
        try:
            action_data = {
                'user_id': user_id,
                'session_id': session_id,
                'action_type': action_type,
                'action_time': datetime.utcnow().isoformat(),
                'parameters': parameters or {},
                'status': 'error',
                'error_message': error_message,
                'points_cost': 0
            }
            
            return await self.create(action_data)
            
        except Exception as e:
            self.logger.error(f"记录失败行为失败: {e}")
            raise
    
    async def update_action_result(self, record_id: int, result_url: str = None, 
                                  status: str = 'completed') -> bool:
        """更新行为记录结果"""
        try:
            update_data = {'status': status}
            if result_url:
                update_data['result_url'] = result_url
            
            return await self.update(record_id, update_data)
            
        except Exception as e:
            self.logger.error(f"更新行为结果失败: {e}")
            return False
    
    async def get_user_actions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的行为记录"""
        return await self.find_many(limit=limit, user_id=user_id)
    
    async def get_session_actions(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话的行为记录"""
        return await self.find_many(limit=limit, session_id=session_id)
    
    async def get_actions_by_type(self, action_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """根据行为类型获取记录"""
        return await self.find_many(limit=limit, action_type=action_type)
    
    async def get_user_actions_by_type(self, user_id: int, action_type: str, 
                                      limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户特定类型的行为记录"""
        return await self.find_many(limit=limit, user_id=user_id, action_type=action_type)
    
    async def get_recent_actions(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的行为记录"""
        try:
            client = self.get_client()
            since_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            query = client.table(self.table_name).select('*')
            query = query.gte('action_time', since_time)
            query = query.order('action_time', desc=True).limit(limit)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取最近行为记录失败: {e}")
            return []
    
    async def get_action_statistics(self, user_id: int = None, days: int = 7) -> Dict[str, Any]:
        """获取行为统计"""
        try:
            client = self.get_client()
            since_time = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            query = client.table(self.table_name).select('action_type, status')
            query = query.gte('action_time', since_time)
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            result = query.execute()
            
            # 统计数据
            stats = {'total': 0, 'success': 0, 'error': 0, 'by_type': {}}
            
            for record in result.data or []:
                stats['total'] += 1
                if record['status'] == 'success':
                    stats['success'] += 1
                elif record['status'] == 'error':
                    stats['error'] += 1
                
                action_type = record['action_type']
                if action_type not in stats['by_type']:
                    stats['by_type'][action_type] = 0
                stats['by_type'][action_type] += 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取行为统计失败: {e}")
            return {'total': 0, 'success': 0, 'error': 0, 'by_type': {}}