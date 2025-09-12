"""
积分组合Repository V2
负责积分相关的跨表操作 - 保持与旧版UserRepository接口完全兼容

主要职责：
1. 积分操作（wallet + points） - add_points/subtract_points，与旧版接口一致
2. 积分支付（payment + wallet + points） - 支付充值流程
3. 任务积分扣除（wallet + tasks + points） - 任务创建和积分扣除
4. 完全兼容Service层的现有调用方式
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from contextlib import asynccontextmanager

from src.infrastructure.database.repositories_v2.single.user_wallet_repository_v2 import UserWalletRepositoryV2
from src.infrastructure.database.repositories_v2.single.point_record_repository_v2 import PointRecordRepositoryV2
from src.infrastructure.database.repositories_v2.single.payment_order_repository_v2 import PaymentOrderRepositoryV2
from src.infrastructure.database.repositories_v2.single.image_task_repository_v2 import ImageTaskRepositoryV2

from src.utils.config.app_config import COST_QUICK_UNDRESS, COST_CUSTOM_UNDRESS


class PointCompositeRepository:
    """积分组合Repository V2版本
    
    封装积分相关的跨表事务操作，对外提供与旧版UserRepository完全兼容的接口
    """
    
    def __init__(self, supabase_manager: Any):
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        
        # 初始化各个单表Repository
        self.wallet_repo = UserWalletRepositoryV2(supabase_manager)
        self.point_repo = PointRecordRepositoryV2(supabase_manager)
        self.payment_repo = PaymentOrderRepositoryV2(supabase_manager)
        self.task_repo = ImageTaskRepositoryV2(supabase_manager)
    
    def get_client(self) -> Any:
        """获取Supabase客户端"""
        return self.supabase_manager.get_client()
    
    @asynccontextmanager
    async def _transaction(self):
        """简单的事务管理上下文（后续可扩展为真正的DB事务）"""
        rollback_actions: List[Any] = []
        self.logger.debug("积分事务开始")
        try:
            yield rollback_actions
            self.logger.debug("积分事务成功完成")
        except Exception as e:
            self.logger.warning(f"积分事务异常，开始回滚: {e}")
            for action in reversed(rollback_actions):
                try:
                    await action()
                    self.logger.debug("积分事务回滚操作成功")
                except Exception as rollback_error:
                    self.logger.error(f"积分事务回滚操作失败: {rollback_error}")
            raise e
    
    # ==================== 与旧版UserRepository完全兼容的积分接口 ====================
    
    async def add_points(self, user_id: int, points: int, action_type: str = 'system', 
                        description: str = None) -> bool:
        """增加用户积分（与旧版UserRepository接口完全一致）
        
        Args:
            user_id: 用户ID
            points: 增加的积分数量
            action_type: 操作类型，默认为'system'
            description: 操作描述，可选
            
        Returns:
            bool: 操作是否成功
        """
        if points <= 0:
            self.logger.warning(f"积分数量必须为正数: points={points}")
            return False
        
        async with self._transaction() as rollback_actions:
            try:
                self.logger.debug(f"开始增加积分: user_id={user_id}, points={points}")
                
                # 1. 增加钱包积分（单表Repository处理字段映射）
                success = await self.wallet_repo.add_points(user_id, points)
                if not success:
                    return False
                
                rollback_actions.append(
                    lambda: self.wallet_repo.subtract_points(user_id, points)
                )
                
                # 2. 获取更新后的钱包信息（已映射为兼容格式）
                wallet = await self.wallet_repo.get_by_user_id(user_id)
                if not wallet:
                    raise Exception("获取更新后的钱包信息失败")
                
                # 3. 创建积分流水记录（使用传入的参数）
                point_record_data = {
                    'user_id': user_id,
                    'points_change': points,  # 使用新的字段名
                    'action_type': action_type,
                    'description': description or f"获得{points}积分",
                    'points_balance': wallet['points'],  # 使用新的字段名
                    'related_event_id': str(uuid.uuid4())
                }
                await self.point_repo.create(point_record_data)
                
                self.logger.info(f"积分增加成功: user_id={user_id}, +{points}积分, 余额={wallet['points']}")
                return True
                
            except Exception as e:
                self.logger.error(f"增加积分失败: user_id={user_id}, error={e}")
                return False
    
    async def subtract_points(self, user_id: int, points: int) -> bool:
        """扣除用户积分（与旧版UserRepository接口完全一致）
        
        Args:
            user_id: 用户ID
            points: 扣除的积分数量
            
        Returns:
            bool: 操作是否成功（包含余额不足的情况）
        """
        if points <= 0:
            self.logger.warning(f"积分数量必须为正数: points={points}")
            return False
        
        async with self._transaction() as rollback_actions:
            try:
                self.logger.debug(f"开始扣除积分: user_id={user_id}, points={points}")
                
                # 1. 扣除钱包积分（单表Repository处理余额检查和字段映射）
                success = await self.wallet_repo.subtract_points(user_id, points)
                if not success:
                    # 获取当前余额用于日志
                    current_wallet = await self.wallet_repo.get_by_user_id(user_id)
                    current_balance = current_wallet['points'] if current_wallet else 0
                    self.logger.warning(f"用户积分不足: user_id={user_id}, current={current_balance}, required={points}")
                    return False
                
                rollback_actions.append(
                    lambda: self.wallet_repo.add_points(user_id, points)
                )
                
                # 2. 获取更新后的钱包信息（已映射为兼容格式）
                wallet = await self.wallet_repo.get_by_user_id(user_id)
                if not wallet:
                    raise Exception("获取更新后的钱包信息失败")
                
                # 3. 创建积分流水记录（使用旧版字段名）
                point_record_data = {
                    'user_id': user_id,
                    'points_change': -points,  # 负数表示扣除
                    'action_type': 'system',
                    'description': f"消费{points}积分",
                    'points_balance': wallet['points'],  # 使用新的字段名
                    'related_event_id': str(uuid.uuid4())
                }
                await self.point_repo.create(point_record_data)
                
                self.logger.info(f"积分扣除成功: user_id={user_id}, -{points}积分, 余额={wallet['points']}")
                return True
                
            except Exception as e:
                self.logger.error(f"扣除积分失败: user_id={user_id}, error={e}")
                return False

    # ==================== Service层专用的业务方法 ====================
    
    async def process_payment_success(self, user_id: int, order_id: str, amount: Decimal, 
                                     points_awarded: int, payment_method: str = None, 
                                     order_data: Dict[str, Any] = None) -> bool:
        """处理支付成功（为PaymentService服务）
        
        Args:
            user_id: 用户ID
            order_id: 订单ID
            amount: 支付金额
            points_awarded: 奖励的积分数量
            payment_method: 支付方式
            order_data: 订单额外数据
            
        Returns:
            bool: 处理是否成功
        """
        async with self._transaction() as rollback_actions:
            try:
                self.logger.info(f"开始处理支付: user_id={user_id}, order_id={order_id}, amount={amount}, points={points_awarded}")
                
                # 1. 创建支付订单记录
                payment_data = {
                    'user_id': user_id,
                    'order_id': order_id,
                    'amount': amount,
                    'status': 'completed',
                    'payment_method': payment_method,
                    'paid_at': datetime.utcnow().isoformat(),
                    'points_awarded': points_awarded,
                    'order_data': order_data or {}
                }
                payment_order = await self.payment_repo.create(payment_data)
                rollback_actions.append(lambda: self.payment_repo.delete(payment_order['id']))
                
                # 2. 增加钱包积分
                success = await self.wallet_repo.add_points(user_id, points_awarded)
                if not success:
                    raise Exception("更新钱包积分失败")
                
                rollback_actions.append(
                    lambda: self.wallet_repo.subtract_points(user_id, points_awarded)
                )
                
                # 🚀 并行执行：更新总充值金额 + 获取钱包信息
                paid_amount_task = self.wallet_repo.add_paid_amount(user_id, float(amount))
                wallet_info_task = self.wallet_repo.get_by_user_id(user_id)
                
                _, wallet = await asyncio.gather(
                    paid_amount_task,
                    wallet_info_task,
                    return_exceptions=True
                )
                
                # 处理异常情况
                if isinstance(wallet, Exception):
                    raise Exception(f"获取更新后的钱包信息失败: {wallet}")
                if not wallet:
                    raise Exception("获取更新后的钱包信息失败")
                
                # 5. 积分流水记录改为后台异步处理，避免阻塞支付响应
                async def _background_payment_record():
                    try:
                        point_record_data = {
                            'user_id': user_id,
                            'points_change': points_awarded,  # 使用新的字段名
                            'action_type': 'payment',
                            'description': f"充值获得积分 - 订单:{order_id}",
                            'points_balance': wallet['points'],  # 使用新的字段名
                            'related_event_id': None  # 设置为None，让数据库处理，避免UUID格式错误
                        }
                        await self.point_repo.create(point_record_data)
                    except Exception as bg_err:
                        self.logger.error(f"支付积分流水记录失败(后台): {bg_err}")
                
                try:
                    asyncio.create_task(_background_payment_record())
                except Exception as schedule_err:
                    self.logger.error(f"调度支付积分流水后台任务失败: {schedule_err}")
                
                self.logger.info(f"支付处理成功: order_id={order_id}, +{points_awarded}积分, 余额={wallet['points']}")
                return True
                
            except Exception as e:
                self.logger.error(f"支付处理失败: order_id={order_id}, error={e}")
                return False
    
    async def create_task_with_payment(self, user_id: int, task_type: str, task_data: Dict[str, Any] = None, points_cost: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """创建任务并扣除积分（为ImageService服务）
        
        Args:
            user_id: 用户ID  
            task_type: 任务类型（quick_undress, custom_undress等）
            task_data: 任务数据
            points_cost: 积分成本（可选，如果不提供则使用默认映射）
            
        Returns:
            Optional[Dict]: 创建的任务信息，失败返回None
        """
        # 🔧 V2迁移：优先使用外部传入的积分成本，保持业务逻辑一致性
        if points_cost is None:
            # 如果没有传入积分成本，才使用默认映射
            cost_mapping = {
                'quick_undress': COST_QUICK_UNDRESS,
                'custom_undress': COST_CUSTOM_UNDRESS,
            }
            points_cost = cost_mapping.get(task_type, COST_QUICK_UNDRESS)
        
        async with self._transaction() as rollback_actions:
            try:
                self.logger.info(f"开始创建任务: user_id={user_id}, task_type={task_type}, cost={points_cost}")
                
                # 1. 扣除钱包积分（已包含余额检查和总消费更新）
                success = await self.wallet_repo.subtract_points(user_id, points_cost)
                if not success:
                    # 获取当前余额用于日志
                    current_wallet = await self.wallet_repo.get_by_user_id(user_id)
                    current_balance = current_wallet['points'] if current_wallet else 0
                    self.logger.warning(f"用户积分不足，无法创建任务: user_id={user_id}, current={current_balance}, required={points_cost}")
                    return None
                
                rollback_actions.append(
                    lambda: self.wallet_repo.add_points(user_id, points_cost)
                )
                
                # 🚀 并行执行：获取钱包信息 + 创建任务记录
                task_create_data = {
                    'user_id': user_id,
                    'task_type': task_type,
                    'status': 'pending',
                    'points_cost': points_cost,
                    **(task_data or {})
                }
                
                wallet, task = await asyncio.gather(
                    self.wallet_repo.get_by_user_id(user_id),
                    self.task_repo.create(task_create_data),
                    return_exceptions=True
                )
                
                # 处理异常情况
                if isinstance(wallet, Exception):
                    raise Exception(f"获取更新后的钱包信息失败: {wallet}")
                if isinstance(task, Exception):
                    raise Exception(f"创建任务记录失败: {task}")
                if not wallet:
                    raise Exception("获取更新后的钱包信息失败")
                
                rollback_actions.append(lambda: self.task_repo.delete(task['id']))
                
                # 4. 积分流水记录改为后台异步处理，避免阻塞响应
                async def _background_point_record():
                    try:
                        point_record_data = {
                            'user_id': user_id,
                            'points_change': -points_cost,  # 负数表示扣除
                            'action_type': 'task_cost',
                            'description': f"{task_type}任务消耗积分",
                            'points_balance': wallet['points'],  # 使用新的字段名
                            'related_event_id': None  # 设置为None，让数据库处理，避免UUID格式错误
                        }
                        await self.point_repo.create(point_record_data)
                    except Exception as bg_err:
                        self.logger.error(f"任务积分流水记录失败(后台): {bg_err}")
                
                try:
                    asyncio.create_task(_background_point_record())
                except Exception as schedule_err:
                    self.logger.error(f"调度任务积分流水后台任务失败: {schedule_err}")
                
                self.logger.info(f"任务创建成功: task_id={task['id']}, -{points_cost}积分, 余额={wallet['points']}")
                return task
                
            except Exception as e:
                self.logger.error(f"创建任务失败: task_type={task_type}, error={e}")
                return None
    
    # ==================== 查询接口（为Service层服务） ====================
    
    async def get_user_points_balance(self, user_id: int) -> Optional[int]:
        """获取用户积分余额"""
        try:
            wallet = await self.wallet_repo.get_by_user_id(user_id)
            return wallet['points'] if wallet else None  # 使用新的字段名
        except Exception as e:
            self.logger.error(f"获取用户积分余额失败: user_id={user_id}, error={e}")
            return None
    
    async def get_user_points_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户积分历史（兼容接口）"""
        try:
            return await self.point_repo.get_user_point_records(user_id, limit)
        except Exception as e:
            self.logger.error(f"获取用户积分历史失败: {e}")
            return []

    # ==================== 兼容性方法别名 ====================
    
    async def get_user_points(self, user_id: int) -> Optional[int]:
        """获取用户积分余额（兼容别名）"""
        return await self.get_user_points_balance(user_id)
    
    async def get_point_records(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取积分记录（兼容别名）"""
        return await self.get_user_points_history(user_id, limit)
    
    async def create_payment_order(self, user_id: int, amount: Decimal, payment_method: str = 'default', **kwargs) -> Dict[str, Any]:
        """创建支付订单（兼容接口）"""
        try:
            order_data = {
                'user_id': user_id,
                'amount': float(amount),
                'payment_method': payment_method,
                'status': 'pending',
                **kwargs
            }
            return await self.payment_repo.create(order_data)
        except Exception as e:
            self.logger.error(f"创建支付订单失败: {e}")
            raise
    
    async def process_payment_failure(self, user_id: int, order_id: str, error_reason: str = None) -> Dict[str, Any]:
        """处理支付失败（兼容接口）"""
        try:
            # 更新订单状态为失败
            success = await self.payment_repo.update_by_order_id(order_id, {
                'status': 'failed',
                'error_message': error_reason or '支付失败',
                'updated_at': datetime.utcnow().isoformat()
            })
            
            return {
                'success': success,
                'message': '支付失败处理完成' if success else '处理支付失败时出错',
                'order_id': order_id,
                'user_id': user_id
            }
        except Exception as e:
            self.logger.error(f"处理支付失败时出错: {e}")
            return {
                'success': False,
                'message': f'处理失败: {str(e)}',
                'order_id': order_id,
                'user_id': user_id
            }
    
    async def create_image_task(self, user_id: int, task_type: str, task_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """创建图片任务（兼容别名）"""
        return await self.create_task_with_payment(user_id, task_type, task_data)
    
    async def get_user_tasks(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户任务列表（兼容接口）"""
        try:
            return await self.task_repo.get_user_tasks(user_id, limit)
        except Exception as e:
            self.logger.error(f"获取用户任务失败: {e}")
            return []
    
    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取任务（兼容接口）"""
        try:
            return await self.task_repo.get_by_task_id(task_id)
        except Exception as e:
            self.logger.error(f"获取任务详情失败: {e}")
            return None
    
    def _calculate_points_from_amount(self, amount: float) -> int:
        """从金额计算积分（辅助方法）"""
        # 默认汇率：1元 = 100积分
        return int(amount * 100) 

    # 修改：新增订单读写转发方法
    # 目的：让Service仅依赖组合仓库，即便是单表操作也通过组合层统一入口
    async def create_pending_order(self, user_id: int, order_id: str, amount: float,
                                  payment_method: str, order_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await self.payment_repo.create({
                'user_id': user_id,
                'order_id': order_id,
                'amount': amount,
                'status': 'pending',
                'payment_method': payment_method,
                'order_data': order_data or {}
            })
        except Exception as e:
            self.logger.error(f"创建待支付订单失败: {e}")
            raise

    async def get_order_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self.payment_repo.get_by_order_id(order_id)
        except Exception as e:
            self.logger.error(f"获取订单失败: {e}")
            return None

    async def update_order_status(self, order_id: str, status: str, extra: Dict[str, Any] = None) -> bool:
        try:
            return await self.payment_repo.update_status(order_id, status, extra or {})
        except Exception as e:
            self.logger.error(f"更新订单状态失败: {e}")
            return False

    async def get_user_orders(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            return await self.payment_repo.get_user_orders(user_id, limit)
        except Exception as e:
            self.logger.error(f"获取用户订单失败: {e}")
            return []

    async def cleanup_expired_pending_orders(self, ttl_minutes: int = 30) -> int:
        try:
            return await self.payment_repo.cleanup_expired_orders(ttl_minutes)
        except Exception as e:
            self.logger.error(f"清理过期订单失败: {e}")
            return 0

    async def cancel_pending_order(self, order_id: str, user_id: int) -> bool:
        try:
            return await self.payment_repo.cancel_order(order_id, user_id)
        except Exception as e:
            self.logger.error(f"取消订单失败: {e}")
            return False

    # ==================== 任务相关转发方法（为ImageService服务） ====================
    async def update_task_status(self, task_id: str, status: str,
                                 result_path: Optional[str] = None,
                                 error_message: Optional[str] = None) -> bool:
        try:
            update_data: Dict[str, Any] = {'status': status}
            if result_path:
                update_data['output_image_url'] = result_path
            if error_message:
                update_data['error_message'] = error_message
            return await self.task_repo.update_by_task_id(task_id, update_data)
        except Exception as e:
            self.logger.error(f"更新任务状态失败: task_id={task_id}, error={e}")
            return False

    async def complete_task(self, task_id: str, result_path: Optional[str] = None,
                             api_response: Optional[Dict[str, Any]] = None,
                             points_cost: Optional[int] = None) -> bool:
        try:
            return await self.task_repo.mark_task_completed(task_id, result_path, api_response, points_cost)
        except Exception as e:
            self.logger.error(f"标记任务完成失败: {e}")
            return False

    async def fail_task(self, task_id: str, error_message: str) -> bool:
        try:
            return await self.task_repo.mark_task_failed(task_id, error_message)
        except Exception as e:
            self.logger.error(f"标记任务失败失败: {e}")
            return False

    async def start_task_processing(self, task_id: str) -> bool:
        try:
            return await self.task_repo.mark_task_processing(task_id)
        except Exception as e:
            self.logger.error(f"标记任务处理中失败: {e}")
            return False

    async def get_tasks_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            return await self.task_repo.get_tasks_by_status(status, limit=limit)
        except Exception as e:
            self.logger.error(f"按状态获取任务失败: {e}")
            return []

    async def get_recent_tasks(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            return await self.task_repo.get_recent_tasks(hours, limit)
        except Exception as e:
            self.logger.error(f"获取最近任务失败: {e}")
            return []

    async def get_task_statistics(self, days: int = 7) -> Dict[str, Any]:
        try:
            return await self.task_repo.get_task_statistics(days)
        except Exception as e:
            self.logger.error(f"获取任务统计失败: {e}")
            return {'total': 0, 'completed': 0, 'failed': 0, 'pending': 0, 'processing': 0}

    async def cleanup_old_tasks(self, days: int = 30) -> int:
        try:
            return await self.task_repo.cleanup_old_tasks(days)
        except Exception as e:
            self.logger.error(f"清理旧任务失败: {e}")
            return 0

    async def update_task_webhook(self, task_id: str, webhook_url: str) -> bool:
        try:
            return await self.task_repo.update_by_task_id(task_id, {'webhook_url': webhook_url})
        except Exception as e:
            self.logger.error(f"更新任务Webhook失败: {e}")
            return False

    async def update_task_input_image(self, task_id: str, input_image_url: str) -> bool:
        try:
            return await self.task_repo.update_by_task_id(task_id, {'input_image_url': input_image_url})
        except Exception as e:
            self.logger.error(f"更新任务输入图像失败: {e}")
            return False