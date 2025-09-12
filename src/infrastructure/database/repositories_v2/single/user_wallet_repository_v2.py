"""
Supabase用户钱包Repository V2
负责user_wallet_v2表的CRUD操作 - 专注于用户钱包和积分管理

v2版本变化：
1. 从users表分离出钱包相关字段到专门的user_wallet_v2表
2. 保持原有的积分管理业务逻辑不变
3. 表字段已重命名为与旧版一致：points字段
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_repository_v2 import BaseRepositoryV2


class UserWalletRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase用户钱包数据访问层 V2版本
    
    专注于用户钱包和积分管理：
    - 积分余额管理
    - 支付金额统计
    - 等级管理
    - 首次充值标记
    """
    
    def __init__(self, supabase_manager):
        # user_wallet_v2表有updated_at字段
        super().__init__(supabase_manager, 'user_wallet_v2', has_updated_at=True)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户钱包记录
        
        保持原有默认值设置：
        - 默认积分：50
        - 默认等级：1
        - 其他字段使用表默认值
        """
        try:
            client = self.get_client()
            
            # 设置钱包默认数据（保持原有业务逻辑）
            wallet_data = {
                'user_id': data['user_id'],
                'first_add': False,
                'points': 50,  # 默认初始积分（使用新的字段名）
                'total_paid_amount': 0.0,
                'total_points_spent': 0,
                'level': 1,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 合并传入的数据（只保留表中存在的字段）
            allowed_fields = {'user_id', 'first_add', 'points', 'total_paid_amount', 'total_points_spent', 'level'}
            wallet_data.update({k: v for k, v in data.items() if k in allowed_fields})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(wallet_data)
            
            # 🚀 修复：使用异步调用，避免阻塞事件循环
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).insert(prepared_data).execute()
            )
            
            if result.data and len(result.data) > 0:
                created_wallet = result.data[0]
                self.logger.info(f"用户钱包创建成功: user_id={data['user_id']}")
                return created_wallet
            else:
                raise Exception("插入用户钱包失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建用户钱包失败: {e}")
            raise
    
    async def get_by_id(self, wallet_id: int) -> Optional[Dict[str, Any]]:
        """根据钱包ID获取钱包信息"""
        try:
            client = self.get_client()
            # 🚀 修复：使用异步调用，避免阻塞事件循环
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('id', wallet_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取钱包失败: {e}")
            return None
    
    async def get_by_user_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据用户ID获取钱包信息"""
        try:
            client = self.get_client()
            # 🚀 修复：使用异步调用，避免阻塞事件循环
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('user_id', user_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据用户ID获取钱包失败: {e}")
            return None
    
    async def update(self, wallet_id: int, data: Dict[str, Any]) -> bool:
        """更新钱包信息"""
        try:
            client = self.get_client()
            
            # 过滤只允许更新的字段
            allowed_fields = {'first_add', 'points', 'total_paid_amount', 'total_points_spent', 'level'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: wallet_id={wallet_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 🚀 修复：使用异步调用，避免阻塞事件循环
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).update(prepared_data).eq('id', wallet_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"钱包更新成功: wallet_id={wallet_id}")
                return True
            else:
                self.logger.warning(f"钱包更新失败: wallet_id={wallet_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新钱包失败: {e}")
            return False
    
    async def update_by_user_id(self, user_id: int, data: Dict[str, Any]) -> bool:
        """根据用户ID更新钱包信息"""
        try:
            client = self.get_client()
            
            # 过滤只允许更新的字段
            allowed_fields = {'first_add', 'points', 'total_paid_amount', 'total_points_spent', 'level'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: user_id={user_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 🚀 修复：使用异步调用，避免阻塞事件循环
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).update(prepared_data).eq('user_id', user_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"用户钱包更新成功: user_id={user_id}")
                return True
            else:
                self.logger.warning(f"用户钱包更新失败: user_id={user_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"根据用户ID更新钱包失败: {e}")
            return False
    
    async def delete(self, wallet_id: int) -> bool:
        """删除钱包记录（物理删除）"""
        return await self.hard_delete(wallet_id)
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个钱包记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.limit(1)
            
            # 🚀 修复：使用异步调用，避免阻塞事件循环
            result = await asyncio.to_thread(lambda: query.execute())
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"查找钱包失败: {e}")
            return None
    
    # ==================== 业务方法（保持原有逻辑不变） ====================
    
    async def add_points(self, user_id: int, points: int) -> bool:
        """增加用户积分（保持原有业务逻辑）"""
        try:
            # 获取当前钱包信息
            wallet = await self.get_by_user_id(user_id)
            if not wallet:
                self.logger.error(f"用户钱包不存在: user_id={user_id}")
                return False
            
            # 计算新积分
            new_points = wallet['points'] + points
            
            # 更新积分
            return await self.update_by_user_id(user_id, {'points': new_points})
            
        except Exception as e:
            self.logger.error(f"增加用户积分失败: {e}")
            return False
    
    async def subtract_points(self, user_id: int, points: int) -> bool:
        """扣除用户积分（保持原有业务逻辑）"""
        try:
            # 获取当前钱包信息
            wallet = await self.get_by_user_id(user_id)
            if not wallet:
                self.logger.error(f"用户钱包不存在: user_id={user_id}")
                return False
            
            # 检查积分是否足够
            if wallet['points'] < points:
                self.logger.warning(f"用户积分不足: user_id={user_id}, current={wallet['points']}, required={points}")
                return False
            
            # 计算新积分并更新相关统计
            new_points = wallet['points'] - points
            new_total_spent = wallet['total_points_spent'] + points
            
            return await self.update_by_user_id(user_id, {
                'points': new_points,
                'total_points_spent': new_total_spent
            })
            
        except Exception as e:
            self.logger.error(f"扣除用户积分失败: {e}")
            return False
    
    async def add_paid_amount(self, user_id: int, amount: float) -> bool:
        """增加用户支付金额"""
        try:
            wallet = await self.get_by_user_id(user_id)
            if not wallet:
                self.logger.error(f"用户钱包不存在: user_id={user_id}")
                return False
            
            new_total_paid = float(wallet['total_paid_amount']) + amount
            
            # 如果是第一次支付，标记first_add为True
            update_data = {'total_paid_amount': new_total_paid}
            if not wallet['first_add'] and amount > 0:
                update_data['first_add'] = True
            
            return await self.update_by_user_id(user_id, update_data)
            
        except Exception as e:
            self.logger.error(f"增加支付金额失败: {e}")
            return False
    
    async def update_level(self, user_id: int, level: int) -> bool:
        """更新用户等级"""
        try:
            return await self.update_by_user_id(user_id, {'level': level})
        except Exception as e:
            self.logger.error(f"更新用户等级失败: {e}")
            return False
    
    async def get_users_by_level(self, level: int) -> List[Dict[str, Any]]:
        """根据等级获取钱包列表"""
        return await self.find_many(level=level) 