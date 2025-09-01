"""
Supabase图像任务Repository
负责图像处理任务数据的CRUD操作 - Supabase版本
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .supabase_base_repository import SupabaseBaseRepository


class SupabaseImageTaskRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase图像任务数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'image_tasks')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建图像任务"""
        try:
            client = self.get_client()
            
            # 🔧 修正：使用与数据库表一致的字段名
            task_data = {
                'user_id': data['user_id'],
                'task_id': data['task_id'],  # 外部API返回的任务ID
                'task_type': data.get('task_type', 'undress'),  # 任务类型
                'status': data.get('status', 'pending'),  # pending/processing/completed/failed
                'points_cost': data.get('points_cost', 0),  # ✅ 与表字段一致
                'input_image_url': data.get('input_image_url'),   # 🔧 修正：使用正确字段名
                'output_image_url': data.get('output_image_url'), # 🔧 修正：使用正确字段名
                'webhook_url': data.get('webhook_url'),
                'api_response': data.get('api_response', {}),  # 存储原始API响应
                'error_message': data.get('error_message'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 插入记录
            result = client.table(self.table_name).insert(task_data).execute()
            
            if result.data and len(result.data) > 0:
                created_task = result.data[0]
                self.logger.info(f"图像任务创建成功: task_id={data['task_id']}")
                return created_task
            else:
                raise Exception("插入图像任务失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建图像任务失败: {e}")
            raise
    
    async def get_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取图像任务"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', task_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取图像任务失败: {e}")
            return None
    
    async def get_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据外部任务ID获取图像任务"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('task_id', task_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据任务ID获取图像任务失败: {e}")
            return None
    
    async def update(self, task_id: int, data: Dict[str, Any]) -> bool:
        """更新图像任务"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', task_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"图像任务更新成功: task_id={task_id}")
                return True
            else:
                self.logger.warning(f"图像任务更新失败: task_id={task_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新图像任务失败: {e}")
            return False
    
    async def update_by_task_id(self, task_id: str, data: Dict[str, Any]) -> bool:
        """根据外部任务ID更新图像任务"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('task_id', task_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"图像任务更新成功: task_id={task_id}")
                return True
            else:
                self.logger.warning(f"图像任务更新失败: task_id={task_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"根据任务ID更新图像任务失败: {e}")
            return False
    
    async def delete(self, task_id: int) -> bool:
        """删除图像任务"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', task_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"图像任务删除成功: task_id={task_id}")
                return True
            else:
                self.logger.warning(f"图像任务删除失败: task_id={task_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除图像任务失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个图像任务"""
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
            self.logger.error(f"查找图像任务失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个图像任务"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order('created_at', desc=True)  # 默认按创建时间倒序
            
            # 🔧 使用修复后的分页方法
            if limit is not None and offset is not None:
                end_index = offset + limit - 1
                query = query.range(offset, end_index)
            elif limit is not None:
                query = query.limit(limit)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"查找多个图像任务失败: {e}")
            return []
    
    async def get_user_tasks(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户的图像任务"""
        return await self.find_many(limit=limit, offset=offset, user_id=user_id)
    
    async def get_tasks_by_status(self, status: str, limit: int = None) -> List[Dict[str, Any]]:
        """根据状态获取图像任务"""
        return await self.find_many(limit=limit, status=status)
    
    async def get_processing_tasks(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取处理中的任务"""
        return await self.get_tasks_by_status('processing', limit)
    
    async def update_task_id(self, local_task_identifier: str, external_task_id: str) -> bool:
        """更新任务的外部API任务ID
        
        Args:
            local_task_identifier: 本地任务标识符（可能是数据库ID或本地task_id）
            external_task_id: 外部API返回的任务ID
            
        Returns:
            bool: 更新是否成功
        """
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = {
                'task_id': external_task_id,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 尝试根据不同字段查找和更新任务
            # 首先尝试按数据库ID更新（如果是数字）
            if local_task_identifier.isdigit():
                try:
                    db_id = int(local_task_identifier)
                    result = client.table(self.table_name).update(update_data).eq('id', db_id).execute()
                    
                    if result.data and len(result.data) > 0:
                        self.logger.info(f"通过数据库ID更新任务ID成功: db_id={db_id} -> task_id={external_task_id}")
                        return True
                except ValueError:
                    pass
            
            # 如果按数据库ID更新失败，尝试按task_id更新
            result = client.table(self.table_name).update(update_data).eq('task_id', local_task_identifier).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"通过task_id更新任务ID成功: {local_task_identifier} -> {external_task_id}")
                return True
            
            # 如果都失败了，记录警告
            self.logger.warning(f"更新任务ID失败，未找到匹配的任务: {local_task_identifier}")
            return False
                
        except Exception as e:
            self.logger.error(f"更新任务ID失败: local_id={local_task_identifier}, external_id={external_task_id}, error={e}")
            return False