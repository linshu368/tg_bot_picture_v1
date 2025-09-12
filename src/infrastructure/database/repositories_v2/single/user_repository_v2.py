"""
Supabase用户Repository V2
负责users_v2表的CRUD操作 - 专注于核心用户信息管理

v2版本变化：
1. 表结构简化：移除积分、统计等业务字段，专注于用户基础信息
2. 移除updated_at字段
3. 业务逻辑分离：积分管理→钱包表，统计信息→统计表
"""

import asyncio
import random
import string
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_repository_v2 import BaseRepositoryV2


class UserRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase用户数据访问层 V2版本
    
    专注于用户核心信息的CRUD操作：
    - 用户基础信息管理
    - UID生成和唯一性保证
    - 用户查询和检索
    """
    
    def __init__(self, supabase_manager):
        # users_v2表没有updated_at字段
        super().__init__(supabase_manager, 'users_v2', has_updated_at=False)
        self.uid_prefix = "u_"
        self.uid_length = 8
    
    def generate_uid(self) -> str:
        """生成唯一的用户ID"""
        return self.uid_prefix + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=self.uid_length)
        )
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新用户
        
        v2版本适配：
        1. 只处理users_v2表的核心字段
        2. 不再设置积分、等级等业务字段（由其他表管理）
        3. 保持UID生成逻辑不变
        """
        try:
            client = self.get_client()
            
            # 生成唯一UID
            uid = self.generate_uid()
            while await self.find_one(uid=uid):
                uid = self.generate_uid()
            
            # 设置用户核心数据（仅包含users_v2表的字段）
            user_data = {
                'telegram_id': data['telegram_id'],
                'uid': uid,
                'username': data.get('username'),
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
                'is_active': True,
                'utm_source': data.get('utm_source', '000'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 合并传入的数据（只保留表中存在的字段）
            allowed_fields = {'telegram_id', 'uid', 'username', 'first_name', 'last_name', 'is_active', 'utm_source'}
            user_data.update({k: v for k, v in data.items() if k in allowed_fields and k != 'uid'})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(user_data)
            
            # 插入数据
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data and len(result.data) > 0:
                created_user = result.data[0]
                self.logger.info(f"用户创建成功: telegram_id={data['telegram_id']}, uid={uid}")
                return created_user
            else:
                raise Exception("插入用户失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建用户失败: {e}")
            raise
    
    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', user_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取用户失败: {e}")
            return None
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """根据Telegram ID获取用户"""
        try:
            self.logger.info(f"🔍 [UserRepositoryV2] 开始执行 get_by_telegram_id: telegram_id={telegram_id}")
            
            # 步骤1: 获取数据库客户端
            self.logger.info(f"🔧 [UserRepositoryV2] 步骤1: 调用 get_client()")
            client = self.get_client()
            self.logger.info(f"✅ [UserRepositoryV2] 步骤1完成: get_client() 成功获取客户端")
            
            # 步骤2: 构建查询参数
            self.logger.info(f"🔧 [UserRepositoryV2] 步骤2: 构建查询参数 - 表名={self.table_name}, 查询字段=*, 条件=telegram_id={telegram_id}")
            
            # 步骤3: 执行数据库查询
            self.logger.info(f"🔧 [UserRepositoryV2] 步骤3: 开始执行数据库查询")
            result = client.table(self.table_name).select('*').eq('telegram_id', telegram_id).execute()
            #用 asyncio.to_thread() 包裹
            # result = await asyncio.to_thread(
            #     lambda: client.table(self.table_name).select('*').eq('telegram_id', telegram_id).execute()
            # )
            self.logger.info(f"✅ [UserRepositoryV2] 步骤3完成: 数据库查询执行完成")
            
            # 步骤4: 处理查询结果
            self.logger.info(f"🔧 [UserRepositoryV2] 步骤4: 处理查询结果")
            self.logger.info(f"📊 [UserRepositoryV2] 查询结果详情: result.data存在={result.data is not None}, 数据条数={len(result.data) if result.data else 0}")
            
            if result.data and len(result.data) > 0:
                user = result.data[0]
                self.logger.info(f"✅ [UserRepositoryV2] 步骤4完成: 成功找到用户")
                self.logger.info(f"👤 [UserRepositoryV2] 用户详情: id={user.get('id')}, uid={user.get('uid')}, username={user.get('username')}")
                self.logger.info(f"🎯 [UserRepositoryV2] get_by_telegram_id 执行成功，返回用户数据")
                return user
            
            self.logger.info(f"❌ [UserRepositoryV2] 步骤4完成: 未找到匹配的用户")
            self.logger.info(f"🎯 [UserRepositoryV2] get_by_telegram_id 执行完成，返回 None (用户不存在): telegram_id={telegram_id}")
            return None
            
        except Exception as e:
            self.logger.error(f"💥 [UserRepositoryV2] get_by_telegram_id 执行失败: {e}")
            self.logger.error(f"💥 [UserRepositoryV2] 异常详情: telegram_id={telegram_id}, 错误类型={type(e).__name__}")
            return None
    
    async def get_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """根据UID获取用户"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('uid', uid).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据UID获取用户失败: {e}")
            return None
    
    async def update(self, user_id: int, data: Dict[str, Any]) -> bool:
        """更新用户信息
        
        v2版本适配：只允许更新users_v2表中存在的字段
        """
        try:
            client = self.get_client()
            
            # 过滤只允许更新的字段
            allowed_fields = {'username', 'first_name', 'last_name', 'is_active', 'utm_source'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: user_id={user_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 执行更新
            result = client.table(self.table_name).update(prepared_data).eq('id', user_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"用户更新成功: user_id={user_id}")
                return True
            else:
                self.logger.warning(f"用户更新失败: user_id={user_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新用户失败: {e}")
            return False
    
    async def delete(self, user_id: int, hard_delete: bool = False) -> bool:
        """删除用户
        
        Args:
            user_id: 用户ID
            hard_delete: 是否物理删除，默认为软删除
        """
        try:
            if hard_delete:
                return await self.hard_delete(user_id)
            else:
                return await self.soft_delete(user_id)
        except Exception as e:
            self.logger.error(f"删除用户失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个用户"""
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
            self.logger.error(f"查找用户失败: {e}")
            return None
    
    async def get_active_users(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取活跃用户列表"""
        return await self.find_many(limit=limit, is_active=True)
    
    async def search_users_by_username(self, username_pattern: str) -> List[Dict[str, Any]]:
        """根据用户名模糊搜索用户"""
        return await self.find_many(username=f'%{username_pattern}%')
    
    async def get_users_by_utm_source(self, utm_source: str) -> List[Dict[str, Any]]:
        """根据UTM来源获取用户"""
        return await self.find_many(utm_source=utm_source)
    
    async def batch_create_users(self, users_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量创建用户
        
        为每个用户生成唯一UID并插入数据库
        """
        try:
            prepared_users = []
            
            for data in users_data:
                # 生成唯一UID
                uid = self.generate_uid()
                while await self.find_one(uid=uid):
                    uid = self.generate_uid()
                
                # 准备用户数据
                user_data = {
                    'telegram_id': data['telegram_id'],
                    'uid': uid,
                    'username': data.get('username'),
                    'first_name': data.get('first_name'),
                    'last_name': data.get('last_name'),
                    'is_active': True,
                    'utm_source': data.get('utm_source', '000'),
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # 过滤字段
                allowed_fields = {'telegram_id', 'uid', 'username', 'first_name', 'last_name', 'is_active', 'utm_source'}
                user_data.update({k: v for k, v in data.items() if k in allowed_fields and k != 'uid'})
                
                prepared_users.append(user_data)
            
            # 批量插入
            return await self.bulk_insert(prepared_users)
            
        except Exception as e:
            self.logger.error(f"批量创建用户失败: {e}")
            raise
    
    async def check_telegram_id_exists(self, telegram_id: int) -> bool:
        """检查Telegram ID是否已存在"""
        return await self.exists(telegram_id=telegram_id)
    
    async def check_uid_exists(self, uid: str) -> bool:
        """检查UID是否已存在"""
        return await self.exists(uid=uid) 