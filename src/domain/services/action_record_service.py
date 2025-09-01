"""
用户行为记录服务
负责用户操作行为的记录、查询和统计分析

修改：已迁移为仅依赖 ActionCompositeRepository，移除并行验证相关代码
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class ActionRecordService:
    """用户行为记录业务服务（已迁移：仅依赖 ActionCompositeRepository）"""
    
    # 修改：精简构造，仅保留组合仓库
    def __init__(self, action_record_repo=None):
        if not action_record_repo:
            raise ValueError("必须提供action_record_repo")
        self.logger = logging.getLogger(__name__)
        self.action_record_repo = action_record_repo
        self.logger.info("🔧 使用ActionCompositeRepository")
    
    async def record_action(self, user_id: int, session_id: str, action_type: str,
                           parameters: Dict[str, Any] = None, message_context: str = None,
                           points_cost: int = 0) -> Optional[Dict[str, Any]]:
        """记录用户成功行为"""
        try:
            # 主要操作
            record = await self.action_record_repo.record_action(
                user_id, session_id, action_type, parameters, message_context, points_cost
            )
            
            self.logger.info(f"行为记录成功: user_id={user_id}, action={action_type}")
            return record
            
        except Exception as e:
            self.logger.error(f"记录用户行为失败: {e}")
            return None
    
    async def record_error_action(self, user_id: int, session_id: str, action_type: str,
                                 error_message: str, parameters: Dict[str, Any] = None,
                                 message_context: str = None) -> Optional[Dict[str, Any]]:
        """记录用户失败行为"""
        try:
            record = await self.action_record_repo.record_error_action(
                user_id, session_id, action_type, error_message, parameters
            )
            
            if message_context and record:
                await self.action_record_repo.update(record['id'], {
                    'message_context': message_context
                })
            
            self.logger.info(f"错误行为记录成功: user_id={user_id}, action={action_type}")
            return record
            
        except Exception as e:
            self.logger.error(f"记录错误行为失败: {e}")
            return None
    
    async def update_action_result(self, record_id: int, result_url: str = None,
                                  status: str = 'completed') -> bool:
        """更新行为记录结果"""
        try:
            return await self.action_record_repo.update_action_result(record_id, result_url, status)
        except Exception as e:
            self.logger.error(f"更新行为结果失败: {e}")
            return False
    
    async def get_user_actions(self, user_id: int, limit: int = 50, 
                              action_type: str = None) -> List[Dict[str, Any]]:
        """获取用户的行为记录"""
        try:
            if action_type:
                return await self.action_record_repo.get_user_actions_by_type(user_id, action_type, limit)
            else:
                return await self.action_record_repo.get_user_actions(user_id, limit)
        except Exception as e:
            self.logger.error(f"获取用户行为记录失败: {e}")
            return []
    
    async def get_session_actions(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话的行为记录"""
        try:
            return await self.action_record_repo.get_session_actions(session_id, limit)
        except Exception as e:
            self.logger.error(f"获取会话行为记录失败: {e}")
            return []
    
    async def get_actions_by_type(self, action_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """根据行为类型获取记录"""
        try:
            return await self.action_record_repo.get_actions_by_type(action_type, limit)
        except Exception as e:
            self.logger.error(f"根据类型获取行为记录失败: {e}")
            return []
    
    async def get_recent_actions(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的行为记录"""
        try:
            return await self.action_record_repo.get_recent_actions(hours, limit)
        except Exception as e:
            self.logger.error(f"获取最近行为记录失败: {e}")
            return []
    
    async def get_action_statistics(self, user_id: int = None, days: int = 7) -> Dict[str, Any]:
        """获取行为统计"""
        try:
            stats = await self.action_record_repo.get_action_statistics(user_id, days)
            
            # 计算成功率
            if stats['total'] > 0:
                stats['success_rate'] = round(stats['success'] / stats['total'] * 100, 2)
                stats['error_rate'] = round(stats['error'] / stats['total'] * 100, 2)
            else:
                stats['success_rate'] = 0.0
                stats['error_rate'] = 0.0
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取行为统计失败: {e}")
            return {
                'total': 0, 'success': 0, 'error': 0, 'by_type': {},
                'success_rate': 0.0, 'error_rate': 0.0
            }
    
    async def get_user_action_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取用户行为总结"""
        try:
            # 获取用户最近的行为记录
            since_time = datetime.utcnow() - timedelta(days=days)
            conditions = {
                'user_id': user_id,
                'action_time__gte': since_time.isoformat()
            }
            
            actions = await self.action_record_repo.find_many(**conditions)
            
            # 统计分析
            total_actions = len(actions)
            success_actions = len([a for a in actions if a['status'] == 'success'])
            error_actions = len([a for a in actions if a['status'] == 'error'])
            total_points_cost = sum(a.get('points_cost', 0) for a in actions)
            
            # 按类型统计
            action_types = {}
            for action in actions:
                action_type = action['action_type']
                if action_type not in action_types:
                    action_types[action_type] = {'count': 0, 'success': 0, 'error': 0}
                
                action_types[action_type]['count'] += 1
                if action['status'] == 'success':
                    action_types[action_type]['success'] += 1
                elif action['status'] == 'error':
                    action_types[action_type]['error'] += 1
            
            # 最常用的行为类型
            most_used_action = max(action_types.items(), key=lambda x: x[1]['count'])[0] if action_types else None
            
            return {
                'user_id': user_id,
                'period_days': days,
                'total_actions': total_actions,
                'success_actions': success_actions,
                'error_actions': error_actions,
                'success_rate': round(success_actions / total_actions * 100, 2) if total_actions > 0 else 0,
                'total_points_cost': total_points_cost,
                'most_used_action': most_used_action,
                'action_types': action_types,
                'avg_actions_per_day': round(total_actions / days, 2)
            }
            
        except Exception as e:
            self.logger.error(f"获取用户行为总结失败: {e}")
            return {
                'user_id': user_id,
                'period_days': days,
                'total_actions': 0,
                'success_actions': 0,
                'error_actions': 0,
                'success_rate': 0.0,
                'total_points_cost': 0,
                'most_used_action': None,
                'action_types': {},
                'avg_actions_per_day': 0.0
            }
    
    # 常用的行为类型记录方法
    async def record_image_generation(self, user_id: int, session_id: str, prompt: str,
                                     points_cost: int, result_url: str = None) -> Optional[Dict[str, Any]]:
        """记录图像生成行为"""
        parameters = {'prompt': prompt}
        record = await self.record_action(user_id, session_id, 'image_generation', 
                                        parameters, prompt, points_cost)
        
        if record and result_url:
            await self.update_action_result(record['id'], result_url, 'completed')
        
        return record
    
    async def record_payment_action(self, user_id: int, session_id: str, order_id: str,
                                   amount: float) -> Optional[Dict[str, Any]]:
        """记录支付行为"""
        parameters = {'order_id': order_id, 'amount': amount}
        return await self.record_action(user_id, session_id, 'payment', parameters)
    
    async def record_checkin_action(self, user_id: int, session_id: str, 
                                   points_earned: int) -> Optional[Dict[str, Any]]:
        """记录签到行为"""
        parameters = {'points_earned': points_earned}
        return await self.record_action(user_id, session_id, 'daily_checkin', parameters)

    # （并行验证相关代码已移除）