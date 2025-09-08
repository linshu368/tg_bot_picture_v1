"""
行为组合Repository V2
负责用户行为相关的跨表操作 - 保持与旧版UserActionRecordRepository接口兼容

主要职责：
1. 行为记录 + 统计（actions + stats）
2. 行为记录时自动更新统计信息
3. 保持与service层的接口兼容性
4. 低频场景的独立管理
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from src.infrastructure.database.repositories_v2.single.user_action_record_repository_v2 import UserActionRecordRepositoryV2
from src.infrastructure.database.repositories_v2.single.user_activity_stats_repository_v2 import UserActivityStatsRepositoryV2


class ActionCompositeRepository:
    """行为组合Repository V2版本
    
    封装行为记录相关的跨表事务操作，对外提供与旧版UserActionRecordRepository兼容的接口
    """
    
    def __init__(self, supabase_manager: Any):
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        
        # 初始化各个单表Repository
        self.action_repo = UserActionRecordRepositoryV2(supabase_manager)
        self.stats_repo = UserActivityStatsRepositoryV2(supabase_manager)
    
    def get_client(self) -> Any:
        """获取Supabase客户端"""
        return self.supabase_manager.get_client()
    
    @asynccontextmanager
    async def _transaction(self):
        """简单的事务管理上下文"""
        rollback_actions: List[Any] = []
        self.logger.debug("行为事务开始")
        try:
            yield rollback_actions
            self.logger.debug("行为事务成功完成")
        except Exception as e:
            self.logger.warning(f"行为事务异常，开始回滚: {e}")
            for action in reversed(rollback_actions):
                try:
                    await action()
                    self.logger.debug("行为回滚操作成功")
                except Exception as rollback_error:
                    self.logger.error(f"行为回滚操作失败: {rollback_error}")
            raise e
    
    def _standardize_error_response(self, success: bool = False, message: str = "", data: Any = None) -> Dict[str, Any]:
        """标准化错误响应格式"""
        return {
            'success': success,
            'message': message,
            'data': data
        }
    
    # ==================== 保持兼容的核心接口 ====================
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建行为记录（与旧版兼容）"""
        async with self._transaction() as rollback_actions:
            try:
                # 1. 创建行为记录
                action_record = await self.action_repo.create(data)
                rollback_actions.append(lambda: self.action_repo.delete(action_record['id']))
                
                # 2. 如果是新的会话，更新统计信息（后台，避免阻塞首响）
                user_id = data['user_id']
                action_type = data.get('action_type', '')
                
                async def _background_stats_update():
                    try:
                        if action_type in ['start_session', 'new_session']:
                            await self.stats_repo.increment_session_count(user_id)
                        elif action_type in ['send_message', 'text_message', 'image_message']:
                            await self.stats_repo.increment_message_count(user_id)
                        else:
                            await self.stats_repo.update_last_active_time(user_id)
                    except Exception as bg_err:
                        self.logger.error(f"更新行为统计失败(后台): {bg_err}")

                try:
                    asyncio.create_task(_background_stats_update())
                except Exception as schedule_err:
                    self.logger.error(f"调度行为统计后台任务失败: {schedule_err}")
                
                self.logger.info(f"行为记录创建成功: action_type={action_type}, user_id={user_id}")
                return action_record
                
            except Exception as e:
                self.logger.error(f"创建行为记录失败: {e}")
                raise
    
    async def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取行为记录"""
        return await self.action_repo.get_by_id(record_id)
    
    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新行为记录"""
        return await self.action_repo.update(record_id, data)
    
    async def delete(self, record_id: int) -> bool:
        """删除行为记录"""
        return await self.action_repo.delete(record_id)
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个行为记录"""
        return await self.action_repo.find_one(**conditions)
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个行为记录"""
        try:
            # 直接调用单表repo的查询方法
            records = await self.action_repo.find_many(limit=limit, **conditions)
            return records
        except Exception as e:
            self.logger.error(f"查找行为记录失败: {e}")
            return []
    
    # ==================== 兼容旧版的业务方法 ====================
    
    async def record_action(self, user_id: int, session_id: str, action_type: str,
                           parameters: Dict[str, Any] = None, message_context: str = None,
                           points_cost: int = 0) -> Dict[str, Any]:
        """记录用户行为（与旧版接口完全兼容）"""
        async with self._transaction() as rollback_actions:
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
                
                # 1. 创建行为记录（核心同步写）
                action_record = await self.action_repo.create(action_data)
                rollback_actions.append(lambda: self.action_repo.delete(action_record['id']))
                
                # 2. 自动更新统计信息（后台）
                async def _background_stats_update_record():
                    try:
                        if action_type in ['start_session', 'new_session']:
                            await self.stats_repo.increment_session_count(user_id)
                        elif action_type in ['send_message', 'text_message', 'image_message']:
                            await self.stats_repo.increment_message_count(user_id)
                        else:
                            await self.stats_repo.update_last_active_time(user_id)
                    except Exception as bg_err:
                        self.logger.error(f"记录行为后更新统计失败(后台): {bg_err}")

                try:
                    asyncio.create_task(_background_stats_update_record())
                except Exception as schedule_err:
                    self.logger.error(f"调度记录行为统计后台任务失败: {schedule_err}")
                
                self.logger.info(f"用户行为记录成功: action_type={action_type}, user_id={user_id}")
                return action_record
                
            except Exception as e:
                self.logger.error(f"记录用户行为失败: {e}")
                raise
    
    async def record_error_action(self, user_id: int, session_id: str, action_type: str,
                                 error_message: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录失败的用户行为（与旧版接口兼容）"""
        async with self._transaction() as rollback_actions:
            try:
                action_data = {
                    'user_id': user_id,
                    'session_id': session_id,
                    'action_type': action_type,
                    'parameters': parameters or {},
                    'status': 'failed',  # V2使用failed而非error
                    'error_message': error_message
                }
                
                # 1. 创建错误行为记录
                action_record = await self.action_repo.create(action_data)
                rollback_actions.append(lambda: self.action_repo.delete(action_record['id']))
                
                # 2. 仍然更新最后活跃时间（即使失败也是活跃行为）
                await self.stats_repo.update_last_active_time(user_id)
                
                self.logger.warning(f"用户错误行为记录: action_type={action_type}, user_id={user_id}, error={error_message}")
                return action_record
                
            except Exception as e:
                self.logger.error(f"记录失败行为失败: {e}")
                raise
    
    async def update_action_result(self, record_id: int, result_url: str = None, 
                                  status: str = 'completed') -> bool:
        """更新行为记录结果（与旧版接口兼容）"""
        try:
            update_data = {'status': status}
            if result_url:
                update_data['result_url'] = result_url
            
            return await self.action_repo.update(record_id, update_data)
            
        except Exception as e:
            self.logger.error(f"更新行为结果失败: {e}")
            return False
    
    async def get_user_actions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的行为记录（与旧版接口兼容）"""
        return await self.action_repo.get_user_action_records(user_id, limit)
    
    async def get_session_actions(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话的行为记录（与旧版接口兼容）"""
        return await self.action_repo.get_session_action_records(session_id)
    
    async def get_actions_by_type(self, action_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """根据行为类型获取记录（与旧版接口兼容）"""
        return await self.action_repo.get_records_by_action_type(action_type, limit=limit)
    
    async def get_user_actions_by_type(self, user_id: int, action_type: str, 
                                      limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户特定类型的行为记录（与旧版接口兼容）"""
        return await self.action_repo.get_records_by_action_type(action_type, user_id, limit)
    
    async def get_recent_actions(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的行为记录（与旧版接口兼容）"""
        try:
            client = self.get_client()
            since_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            query = client.table('user_action_records_v2').select('*')
            query = query.gte('action_time', since_time)
            query = query.order('action_time', desc=True).limit(limit)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取最近行为记录失败: {e}")
            return []
    
    async def get_action_statistics(self, user_id: int = None, days: int = 7) -> Dict[str, Any]:
        """获取行为统计（与旧版接口兼容，但数据来源于V2表）"""
        try:
            # 使用V2的统计方法
            if user_id:
                stats = await self.action_repo.get_action_stats(user_id, days)
                
                # 转换为旧版兼容格式
                legacy_stats = {
                    'total': stats.get('total_actions', 0),
                    'success': stats.get('status_stats', {}).get('completed', 0),
                    'error': stats.get('status_stats', {}).get('failed', 0),
                    'by_type': stats.get('action_type_stats', {})
                }
                return legacy_stats
            else:
                # 全局统计需要直接查询
                client = self.get_client()
                since_time = (datetime.utcnow() - timedelta(days=days)).isoformat()
                
                query = client.table('user_action_records_v2').select('action_type, status')
                query = query.gte('action_time', since_time)
                
                result = query.execute()
                
                # 统计数据
                stats = {'total': 0, 'success': 0, 'error': 0, 'by_type': {}}
                
                for record in result.data or []:
                    stats['total'] += 1
                    if record.get('status') in ['success', 'completed']:
                        stats['success'] += 1
                    elif record.get('status') in ['error', 'failed']:
                        stats['error'] += 1
                    
                    action_type = record.get('action_type', '')
                    if action_type:
                        if action_type not in stats['by_type']:
                            stats['by_type'][action_type] = 0
                        stats['by_type'][action_type] += 1
                
                return stats
            
        except Exception as e:
            self.logger.error(f"获取行为统计失败: {e}")
            return {'total': 0, 'success': 0, 'error': 0, 'by_type': {}}
    
    # ==================== 新增功能：与统计信息聚合 ====================
    
    async def get_user_action_summary(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """获取用户行为摘要（行为记录 + 活动统计）"""
        try:
            # 并行获取行为统计和活动统计
            action_stats = await self.get_action_statistics(user_id, days)
            activity_stats = await self.stats_repo.get_by_user_id(user_id)
            
            # 聚合数据
            summary = {
                'user_id': user_id,
                'period_days': days,
                'action_stats': action_stats,
                'activity_stats': activity_stats or {},
                'summary': {
                    'total_actions_period': action_stats.get('total', 0),
                    'success_rate': round(
                        (action_stats.get('success', 0) / action_stats.get('total', 1)) * 100, 2
                    ) if action_stats.get('total', 0) > 0 else 0,
                    'total_sessions': activity_stats.get('session_count', 0) if activity_stats else 0,
                    'total_messages': activity_stats.get('total_messages_sent', 0) if activity_stats else 0
                }
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"获取用户行为摘要失败: {e}")
            return {}
    
    async def batch_record_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量记录行为（优化性能）"""
        results = []
        async with self._transaction() as rollback_actions:
            try:
                for action_data in actions:
                    # 记录每个行为
                    result = await self.record_action(**action_data)
                    results.append(result)
                    rollback_actions.append(lambda r=result: self.action_repo.delete(r['id']))
                
                self.logger.info(f"批量记录行为成功: 共{len(actions)}条")
                return results
                
            except Exception as e:
                self.logger.error(f"批量记录行为失败: {e}")
                raise
    
    # ==================== 兼容性方法（确保与旧版接口一致） ====================
    
    async def exists(self, **conditions) -> bool:
        """检查行为记录是否存在"""
        try:
            record = await self.action_repo.find_one(**conditions)
            return record is not None
        except Exception as e:
            self.logger.error(f"检查行为记录存在失败: {e}")
            return False
    
    async def get_by_action_id(self, action_id: str) -> Optional[Dict[str, Any]]:
        """根据action_id获取行为记录（V2新增功能）"""
        return await self.action_repo.get_by_action_id(action_id)
    
    async def update_action_status(self, action_id: str, status: str, 
                                 result_url: str = None, error_message: str = None) -> bool:
        """更新行为状态（V2新增功能）"""
        return await self.action_repo.update_action_status(action_id, status, result_url, error_message) 