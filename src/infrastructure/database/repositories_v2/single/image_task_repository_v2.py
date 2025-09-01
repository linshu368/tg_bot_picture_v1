"""
Supabase图像任务Repository V2
负责image_tasks_v2表的CRUD操作 - 专注于图像处理任务管理

v2版本特点：
1. 图像任务完整生命周期管理：创建、处理、完成
2. 支持JSONB类型字段：api_response存储API响应数据
3. 包含时间字段：created_at、updated_at、completed_at
4. 任务状态跟踪和错误处理
5. 积分消耗记录：points_cost
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base_repository_v2 import BaseRepositoryV2


class ImageTaskRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase图像任务数据访问层 V2版本
    
    专注于图像任务的CRUD操作：
    - 图像任务创建和管理
    - 任务状态跟踪
    - 任务历史查询
    """
    
    def __init__(self, supabase_manager):
        # image_tasks_v2表包含updated_at字段
        super().__init__(supabase_manager, 'image_tasks_v2', has_updated_at=True)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建图像任务
        
        包含任务的完整信息
        """
        try:
            client = self.get_client()
            
            # 设置任务数据
            task_data = {
                'user_id': data['user_id'],
                'task_id': data.get('task_id'),
                'task_type': data['task_type'],
                'status': data.get('status', 'pending'),
                'input_image_url': data.get('input_image_url'),
                'output_image_url': data.get('output_image_url'),
                'webhook_url': data.get('webhook_url'),
                'api_response': data.get('api_response'),
                'error_message': data.get('error_message'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'completed_at': data.get('completed_at'),
                'points_cost': data.get('points_cost', 0)
            }
            
            # 过滤有效字段
            allowed_fields = {'user_id', 'task_id', 'task_type', 'status', 'input_image_url',
                            'output_image_url', 'webhook_url', 'api_response', 'error_message',
                            'completed_at', 'points_cost'}
            task_data.update({k: v for k, v in data.items() if k in allowed_fields})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(task_data)
            
            # 插入数据
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data and len(result.data) > 0:
                created_task = result.data[0]
                self.logger.info(f"图像任务创建成功: task_id={data.get('task_id')}, user_id={data['user_id']}")
                return created_task
            else:
                raise Exception("插入图像任务失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建图像任务失败: {e}")
            raise
    
    async def get_by_id(self, task_record_id: int) -> Optional[Dict[str, Any]]:
        """根据记录ID获取图像任务"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', task_record_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取图像任务失败: {e}")
            return None
    
    async def get_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据task_id获取图像任务"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('task_id', task_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据task_id获取图像任务失败: {e}")
            return None
    
    async def update(self, task_record_id: int, data: Dict[str, Any]) -> bool:
        """更新图像任务信息
        
        主要用于更新任务状态、结果等
        """
        try:
            client = self.get_client()
            
            # 过滤允许更新的字段
            allowed_fields = {'status', 'output_image_url', 'api_response', 'error_message', 
                            'completed_at', 'points_cost'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: task_record_id={task_record_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 执行更新
            result = client.table(self.table_name).update(prepared_data).eq('id', task_record_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"图像任务更新成功: task_record_id={task_record_id}")
                return True
            else:
                self.logger.warning(f"图像任务更新失败: task_record_id={task_record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新图像任务失败: {e}")
            return False
    
    async def update_by_task_id(self, task_id: str, data: Dict[str, Any]) -> bool:
        """根据task_id更新图像任务"""
        try:
            task = await self.get_by_task_id(task_id)
            if not task:
                self.logger.warning(f"图像任务不存在: task_id={task_id}")
                return False
            
            return await self.update(task['id'], data)
            
        except Exception as e:
            self.logger.error(f"根据task_id更新图像任务失败: {e}")
            return False
    
    async def delete(self, task_record_id: int) -> bool:
        """删除图像任务（物理删除）"""
        return await self.hard_delete(task_record_id)
    
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
    
    # ==================== 业务方法 ====================
    
    async def get_user_tasks(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户的任务列表"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .order('created_at', desc=True))
            
            if limit is not None:
                query = query.limit(limit)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取用户任务列表失败: {e}")
            return []
    
    async def get_tasks_by_status(self, status: str, user_id: int = None, 
                                limit: int = 100) -> List[Dict[str, Any]]:
        """根据状态获取任务"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('status', status)
                    .order('created_at', desc=True))
            
            if user_id is not None:
                query = query.eq('user_id', user_id)
            
            if limit is not None:
                query = query.limit(limit)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"根据状态获取任务失败: {e}")
            return []
    
    async def get_tasks_by_type(self, task_type: str, user_id: int = None,
                              limit: int = 100) -> List[Dict[str, Any]]:
        """根据任务类型获取任务"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('task_type', task_type)
                    .order('created_at', desc=True))
            
            if user_id is not None:
                query = query.eq('user_id', user_id)
            
            if limit is not None:
                query = query.limit(limit)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"根据任务类型获取任务失败: {e}")
            return []
    
    async def mark_task_completed(self, task_id: str, output_image_url: str = None,
                                api_response: Dict[str, Any] = None, points_cost: int = None) -> bool:
        """标记任务为完成状态"""
        update_data = {
            'status': 'completed',
            'completed_at': datetime.utcnow().isoformat()
        }
        
        if output_image_url:
            update_data['output_image_url'] = output_image_url
        if api_response:
            update_data['api_response'] = api_response
        if points_cost is not None:
            update_data['points_cost'] = points_cost
            
        return await self.update_by_task_id(task_id, update_data)
    
    async def mark_task_failed(self, task_id: str, error_message: str) -> bool:
        """标记任务为失败状态"""
        update_data = {
            'status': 'failed',
            'error_message': error_message,
            'completed_at': datetime.utcnow().isoformat()
        }
        return await self.update_by_task_id(task_id, update_data)
    
    async def mark_task_processing(self, task_id: str) -> bool:
        """标记任务为处理中状态"""
        return await self.update_by_task_id(task_id, {'status': 'processing'})
    
    async def get_user_task_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取用户任务统计信息"""
        try:
            client = self.get_client()
            
            # 计算日期范围
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .gte('created_at', from_date))
                    
            result = query.execute()
            tasks = result.data or []
            
            # 统计信息
            total_tasks = len(tasks)
            completed_tasks = [t for t in tasks if t.get('status') == 'completed']
            failed_tasks = [t for t in tasks if t.get('status') == 'failed']
            total_points_cost = sum(t.get('points_cost', 0) for t in completed_tasks)
            
            # 按状态统计
            status_stats = {}
            for task in tasks:
                status = task.get('status', 'unknown')
                status_stats[status] = status_stats.get(status, 0) + 1
            
            # 按任务类型统计
            type_stats = {}
            for task in tasks:
                task_type = task.get('task_type', 'unknown')
                type_stats[task_type] = type_stats.get(task_type, 0) + 1
            
            # 成功率计算
            total_finished = len(completed_tasks) + len(failed_tasks)
            success_rate = (len(completed_tasks) / total_finished * 100) if total_finished > 0 else 0
            
            return {
                'total_tasks': total_tasks,
                'completed_tasks': len(completed_tasks),
                'failed_tasks': len(failed_tasks),
                'total_points_cost': total_points_cost,
                'success_rate': round(success_rate, 2),
                'status_stats': status_stats,
                'type_stats': type_stats,
                'days': days
            }
            
        except Exception as e:
            self.logger.error(f"获取用户任务统计失败: {e}")
            return {}

    # 修改：新增系统级与时间窗口查询方法
    # 目的：为组合仓库与Service提供所需的统计与清理能力
    async def get_recent_tasks(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近hours内的任务"""
        try:
            client = self.get_client()
            from_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            query = (client.table(self.table_name)
                     .select('*')
                     .gte('created_at', from_time)
                     .order('created_at', desc=True))
            if limit is not None:
                query = query.limit(limit)
            result = query.execute()
            return result.data or []
        except Exception as e:
            self.logger.error(f"获取最近任务失败: {e}")
            return []

    async def get_task_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取系统级任务统计信息"""
        try:
            client = self.get_client()
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            result = (client.table(self.table_name)
                      .select('*')
                      .gte('created_at', from_date)
                      .execute())
            tasks = result.data or []
            stats = {
                'total': len(tasks),
                'completed': len([t for t in tasks if t.get('status') == 'completed']),
                'failed': len([t for t in tasks if t.get('status') == 'failed']),
                'pending': len([t for t in tasks if t.get('status') == 'pending']),
                'processing': len([t for t in tasks if t.get('status') == 'processing'])
            }
            # 简化：不计算成功率和平均处理时长，交由上层如需再算
            return stats
        except Exception as e:
            self.logger.error(f"获取系统任务统计失败: {e}")
            return {'total': 0, 'completed': 0, 'failed': 0, 'pending': 0, 'processing': 0}

    async def cleanup_old_tasks(self, days: int = 30) -> int:
        """清理days天前的已完成/失败任务，返回影响数量"""
        try:
            client = self.get_client()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            result = (client.table(self.table_name)
                      .delete()
                      .lte('created_at', cutoff)
                      .in_('status', ['completed', 'failed'])
                      .execute())
            return len(result.data) if result and result.data else 0
        except Exception as e:
            self.logger.error(f"清理旧任务失败: {e}")
            return 0
    
    # ==================== 兼容性方法（与原Repository接口保持一致） ====================
    
    async def create_task(self, user_id: int, task_type: str, input_image_url: str = None,
                         webhook_url: str = None, points_cost: int = 0) -> Dict[str, Any]:
        """创建图像任务（兼容原接口）"""
        task_data = {
            'user_id': user_id,
            'task_type': task_type,
            'input_image_url': input_image_url,
            'webhook_url': webhook_url,
            'points_cost': points_cost,
            'status': 'pending'
        }
        return await self.create(task_data) 

    # ==================== 业务方法（保持原有逻辑不变） ====================
    
    async def get_by_user_id(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """根据用户ID获取图像任务列表（兼容接口）"""
        try:
            tasks = await self.find_many(limit=limit, user_id=user_id)
            return tasks  # 直接返回，无需字段映射
        except Exception as e:
            self.logger.error(f"根据用户ID获取图像任务失败: {e}")
            return [] 