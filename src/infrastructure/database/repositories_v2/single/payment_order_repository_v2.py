"""
Supabase支付订单Repository V2
负责payment_orders_v2表的CRUD操作 - 专注于支付订单管理

v2版本特点：
1. 支付订单完整信息管理：订单ID、金额、状态、支付方式等
2. 支持JSONB类型字段：order_data存储订单详细数据
3. 包含时间字段：created_at、updated_at、paid_at
4. 积分奖励字段：points_awarded
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from .base_repository_v2 import BaseRepositoryV2
import asyncio


class PaymentOrderRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase支付订单数据访问层 V2版本
    
    专注于支付订单的CRUD操作：
    - 支付订单创建和管理
    - 订单状态跟踪
    - 支付历史查询
    """
    
    def __init__(self, supabase_manager):
        # payment_orders_v2表包含updated_at字段
        super().__init__(supabase_manager, 'payment_orders_v2', has_updated_at=True)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建支付订单
        
        包含订单的完整信息
        """
        try:
            client = self.get_client()
            
            # 设置订单数据
            order_data = {
                'user_id': data['user_id'],
                'order_id': data['order_id'],
                'amount': data['amount'],
                'status': data.get('status', 'pending'),
                'payment_method': data.get('payment_method'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'paid_at': data.get('paid_at'),
                'points_awarded': data.get('points_awarded', 0),
                'order_data': data.get('order_data')
            }
            
            # 过滤有效字段
            allowed_fields = {'user_id', 'order_id', 'amount', 'status', 'payment_method',
                            'paid_at', 'points_awarded', 'order_data'}
            order_data.update({k: v for k, v in data.items() if k in allowed_fields})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(order_data)
            
            # 插入数据（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).insert(prepared_data).execute()
            )
            
            if result.data and len(result.data) > 0:
                created_order = result.data[0]
                self.logger.info(f"支付订单创建成功: order_id={data['order_id']}, user_id={data['user_id']}")
                return created_order
            else:
                raise Exception("插入支付订单失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建支付订单失败: {e}")
            raise
    
    async def get_by_id(self, order_record_id: int) -> Optional[Dict[str, Any]]:
        """根据记录ID获取支付订单"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('id', order_record_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取支付订单失败: {e}")
            return None
    
    async def get_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """根据order_id获取支付订单"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('order_id', order_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据order_id获取支付订单失败: {e}")
            return None
    
    async def update(self, order_record_id: int, data: Dict[str, Any]) -> bool:
        """更新支付订单信息
        
        主要用于更新订单状态、支付时间等
        """
        try:
            client = self.get_client()
            
            # 过滤允许更新的字段
            allowed_fields = {'status', 'payment_method', 'paid_at', 'points_awarded', 'order_data'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: order_record_id={order_record_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 执行更新（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).update(prepared_data).eq('id', order_record_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"支付订单更新成功: order_record_id={order_record_id}")
                return True
            else:
                self.logger.warning(f"支付订单更新失败: order_record_id={order_record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新支付订单失败: {e}")
            return False
    
    async def update_by_order_id(self, order_id: str, data: Dict[str, Any]) -> bool:
        """根据order_id更新支付订单"""
        try:
            order = await self.get_by_order_id(order_id)
            if not order:
                self.logger.warning(f"支付订单不存在: order_id={order_id}")
                return False
            
            return await self.update(order['id'], data)
            
        except Exception as e:
            self.logger.error(f"根据order_id更新支付订单失败: {e}")
            return False
    
    async def delete(self, order_record_id: int) -> bool:
        """删除支付订单（物理删除）"""
        return await self.hard_delete(order_record_id)

    # 修改：新增状态更新、取消与过期清理等通用方法
    # 目的：为组合仓库与Service提供统一订单生命周期操作
    async def update_status(self, order_id: str, status: str, extra: Dict[str, Any] = None) -> bool:
        """更新订单状态（便捷方法）"""
        try:
            data = {'status': status}
            if extra:
                data.update(extra)
            return await self.update_by_order_id(order_id, data)
        except Exception as e:
            self.logger.error(f"更新订单状态失败: order_id={order_id}, status={status}, error={e}")
            return False

    async def mark_order_completed(self, order_id: str) -> bool:
        """标记订单为已完成"""
        try:
            return await self.update_by_order_id(order_id, {
                'status': 'completed',
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            self.logger.error(f"标记订单完成失败: {e}")
            return False

    async def cancel_order(self, order_id: str, user_id: int) -> bool:
        """取消订单（仅允许取消待支付订单）"""
        try:
            order = await self.get_by_order_id(order_id)
            if not order:
                return False
            if order.get('user_id') != user_id:
                self.logger.warning(f"无权取消订单: order_id={order_id}, user_id={user_id}")
                return False
            if order.get('status') != 'pending':
                self.logger.warning(f"订单状态不允许取消: order_id={order_id}, status={order.get('status')}")
                return False
            return await self.update_status(order_id, 'cancelled', {
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            self.logger.error(f"取消订单失败: {e}")
            return False

    async def cleanup_expired_orders(self, ttl_minutes: int = 30) -> int:
        """清理过期的待支付订单，返回影响条数"""
        try:
            client = self.get_client()
            cutoff = (datetime.utcnow() - timedelta(minutes=ttl_minutes)).isoformat()
            update_data = self._prepare_data_for_update({
                'status': 'expired',
                'updated_at': datetime.utcnow().isoformat()
            })
            result = (client.table(self.table_name)
                      .update(update_data)
                      .eq('status', 'pending')
                      .lt('created_at', cutoff)
                      .execute())
            return len(result.data) if result and result.data else 0
        except Exception as e:
            self.logger.error(f"清理过期订单失败: {e}")
            return 0
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个支付订单"""
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
            self.logger.error(f"查找支付订单失败: {e}")
            return None
    
    # ==================== 业务方法 ====================
    
    async def get_user_orders(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户的订单列表"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .order('created_at', desc=True))
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取用户订单列表失败: {e}")
            return []
    
    async def get_orders_by_status(self, status: str, user_id: int = None, 
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """根据状态获取订单"""
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
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"根据状态获取订单失败: {e}")
            return []
    
    async def mark_order_paid(self, order_id: str, payment_method: str = None, 
                            points_awarded: int = None) -> bool:
        """标记订单为已支付状态"""
        update_data = {
            'status': 'paid',
            'paid_at': datetime.utcnow().isoformat()
        }
        
        if payment_method:
            update_data['payment_method'] = payment_method
        if points_awarded is not None:
            update_data['points_awarded'] = points_awarded
            
        return await self.update_by_order_id(order_id, update_data)
    
    async def mark_order_failed(self, order_id: str) -> bool:
        """标记订单为失败状态"""
        return await self.update_by_order_id(order_id, {'status': 'failed'})
    
    async def get_user_payment_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取用户支付统计信息"""
        try:
            client = self.get_client()
            
            # 计算日期范围
            from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .gte('created_at', from_date))
                    
            result = query.execute()
            orders = result.data or []
            
            # 统计信息
            total_orders = len(orders)
            paid_orders = [o for o in orders if o.get('status') == 'paid']
            total_amount = sum(float(o.get('amount', 0)) for o in paid_orders)
            total_points_awarded = sum(o.get('points_awarded', 0) for o in paid_orders)
            
            # 按状态统计
            status_stats = {}
            for order in orders:
                status = order.get('status', 'unknown')
                status_stats[status] = status_stats.get(status, 0) + 1
            
            return {
                'total_orders': total_orders,
                'paid_orders': len(paid_orders),
                'total_amount': round(total_amount, 2),
                'total_points_awarded': total_points_awarded,
                'status_stats': status_stats,
                'days': days
            }
            
        except Exception as e:
            self.logger.error(f"获取用户支付统计失败: {e}")
            return {}
    
    # ==================== 兼容性方法（与原Repository接口保持一致） ====================
    
    async def create_order(self, user_id: int, order_id: str, amount: float,
                         payment_method: str = None, order_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建支付订单（兼容原接口）"""
        order_data_dict = {
            'user_id': user_id,
            'order_id': order_id,
            'amount': amount,
            'payment_method': payment_method,
            'order_data': order_data or {},
            'status': 'pending'
        }
        return await self.create(order_data_dict) 

    # ==================== 业务方法（保持原有逻辑不变） ====================
    
    async def get_by_user_id(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """根据用户ID获取支付订单列表（兼容接口）"""
        try:
            orders = await self.find_many(limit=limit, user_id=user_id)
            return orders  # 直接返回，无需字段映射
        except Exception as e:
            self.logger.error(f"根据用户ID获取支付订单失败: {e}")
            return [] 