"""
Supabase支付订单Repository
负责支付订单数据的CRUD操作 - Supabase版本
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .supabase_base_repository import SupabaseBaseRepository


class SupabasePaymentOrderRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase支付订单数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'payment_orders')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建支付订单"""
        try:
            client = self.get_client()
            
            # 准备数据
            order_data = {
                'user_id': data['user_id'],
                'order_id': data['order_id'],
                'amount': float(data['amount']),
                'status': data.get('status', 'pending'),
                'payment_method': data.get('payment_method'),
                'points_awarded': data.get('points_awarded', 0),
                'order_data': data.get('order_data', {}),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 处理可选的时间字段
            if data.get('paid_at'):
                order_data['paid_at'] = data['paid_at']
            
            # 插入记录
            result = client.table(self.table_name).insert(order_data).execute()
            
            if result.data and len(result.data) > 0:
                created_order = result.data[0]
                self.logger.info(f"支付订单创建成功: order_id={data['order_id']}")
                return created_order
            else:
                raise Exception("插入支付订单失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建支付订单失败: {e}")
            raise
    
    async def get_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取支付订单"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', order_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取支付订单失败: {e}")
            return None
    
    async def get_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """根据订单ID获取支付订单"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('order_id', order_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据订单ID获取支付订单失败: {e}")
            return None
    
    async def update(self, order_id: int, data: Dict[str, Any]) -> bool:
        """更新支付订单"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', order_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"支付订单更新成功: order_id={order_id}")
                return True
            else:
                self.logger.warning(f"支付订单更新失败: order_id={order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新支付订单失败: {e}")
            return False
    
    async def update_by_order_id(self, order_id: str, data: Dict[str, Any]) -> bool:
        """根据订单ID更新支付订单"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('order_id', order_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"支付订单更新成功: order_id={order_id}")
                return True
            else:
                self.logger.warning(f"支付订单更新失败: order_id={order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"根据订单ID更新支付订单失败: {e}")
            return False
    
    async def update_status(self, order_id: str, status: str) -> bool:
        """更新订单状态"""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 如果状态是已支付，添加支付时间
            if status == 'paid':
                update_data['paid_at'] = datetime.utcnow().isoformat()
            
            return await self.update_by_order_id(order_id, update_data)
            
        except Exception as e:
            self.logger.error(f"更新订单状态失败: order_id={order_id}, status={status}, error={e}")
            return False
    
    async def delete(self, order_id: int) -> bool:
        """删除支付订单"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', order_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"支付订单删除成功: order_id={order_id}")
                return True
            else:
                self.logger.warning(f"支付订单删除失败: order_id={order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除支付订单失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个支付订单"""
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
            self.logger.error(f"查找支付订单失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个支付订单"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order('created_at', desc=True)
            
            # 🔧 修复：使用range()替代offset()
            if limit is not None and offset is not None:
                end_index = offset + limit - 1
                query = query.range(offset, end_index)
            elif limit is not None:
                query = query.limit(limit)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"查找多个支付订单失败: {e}")
            return []
    
    async def get_user_orders(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户的支付订单"""
        return await self.find_many(limit=limit, offset=offset, user_id=user_id)
    
    async def get_orders_by_status(self, status: str, limit: int = None) -> List[Dict[str, Any]]:
        """根据状态获取支付订单"""
        return await self.find_many(limit=limit, status=status)
    
    async def get_pending_orders(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取待支付的订单"""
        return await self.get_orders_by_status('pending', limit)
    
    async def get_paid_orders(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取已支付的订单"""
        return await self.get_orders_by_status('paid', limit)
    
    async def get_orders_in_date_range(self, start_date: datetime, end_date: datetime, 
                                     user_id: int = None) -> List[Dict[str, Any]]:
        """获取指定日期范围内的支付订单"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            
            # 日期范围过滤
            query = query.gte('created_at', start_date.isoformat())
            query = query.lte('created_at', end_date.isoformat())
            
            # 用户过滤（可选）
            if user_id:
                query = query.eq('user_id', user_id)
            
            query = query.order('created_at', desc=True)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取日期范围支付订单失败: {e}")
            return []
    
    async def get_total_amount_by_user(self, user_id: int) -> float:
        """获取用户的总支付金额"""
        try:
            orders = await self.get_user_orders(user_id)
            paid_orders = [order for order in orders if order['status'] == 'paid']
            total_amount = sum(float(order['amount']) for order in paid_orders)
            return total_amount
            
        except Exception as e:
            self.logger.error(f"获取用户总支付金额失败: {e}")
            return 0.0 