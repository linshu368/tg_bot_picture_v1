"""
Supabase用户Repository
负责用户数据的CRUD操作 - Supabase版本
"""

import random
import string
from typing import Dict, Any, List, Optional
from datetime import datetime
from .supabase_base_repository import SupabaseBaseRepository


class SupabaseUserRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase用户数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'users')
        self.uid_prefix = "u_"
        self.uid_length = 8
    
    def generate_uid(self) -> str:
        """生成唯一的用户ID"""
        return self.uid_prefix + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=self.uid_length)
        )
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新用户"""
        try:
            client = self.get_client()
            
            # 生成唯一UID
            uid = self.generate_uid()
            while await self.find_one(uid=uid):
                uid = self.generate_uid()
            
            # 设置默认值
            user_data = {
                'telegram_id': data['telegram_id'],
                'uid': uid,
                'username': data.get('username'),
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
                'points': 50,  # 默认初始积分
                'level': 1,
                'is_active': True,
                'session_count': 0,
                'total_points_spent': 0,
                'total_paid_amount': 0.0,
                'first_add': False,
                'utm_source': '000',
                'total_messages_sent': 0,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 合并传入的数据
            user_data.update({k: v for k, v in data.items() if k not in ['uid']})
            
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
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('telegram_id', telegram_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据Telegram ID获取用户失败: {e}")
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
        """更新用户信息"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', user_id).execute()
            
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
        """删除用户"""
        try:
            if hard_delete:
                # 物理删除
                client = self.get_client()
                result = client.table(self.table_name).delete().eq('id', user_id).execute()
                
                if result.data and len(result.data) > 0:
                    self.logger.info(f"用户物理删除成功: user_id={user_id}")
                    return True
                else:
                    self.logger.warning(f"用户物理删除失败: user_id={user_id}")
                    return False
            else:
                # 软删除，设置is_active为False
                return await self.update(user_id, {'is_active': False})
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
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个用户"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            
            if limit is not None:
                query = query.limit(limit)
            if offset is not None:
                query = query.offset(offset)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"查找多个用户失败: {e}")
            return []
    
    async def add_points(self, user_id: int, points: int) -> bool:
        """增加用户积分"""
        try:
            # 获取当前用户信息
            user = await self.get_by_id(user_id)
            if not user:
                return False
            
            # 计算新积分
            new_points = user['points'] + points
            
            # 更新积分
            return await self.update(user_id, {'points': new_points})
            
        except Exception as e:
            self.logger.error(f"增加用户积分失败: {e}")
            return False
    
    async def subtract_points(self, user_id: int, points: int) -> bool:
        """扣除用户积分"""
        try:
            # 获取当前用户信息
            user = await self.get_by_id(user_id)
            if not user:
                return False
            
            # 检查积分是否足够
            if user['points'] < points:
                self.logger.warning(f"用户积分不足: user_id={user_id}, current={user['points']}, required={points}")
                return False
            
            # 计算新积分并更新相关统计
            new_points = user['points'] - points
            new_total_spent = user['total_points_spent'] + points
            
            return await self.update(user_id, {
                'points': new_points,
                'total_points_spent': new_total_spent
            })
            
        except Exception as e:
            self.logger.error(f"扣除用户积分失败: {e}")
            return False
    
    async def increment_session_count(self, user_id: int) -> bool:
        """增加用户会话计数"""
        try:
            user = await self.get_by_id(user_id)
            if not user:
                return False
            
            new_count = user['session_count'] + 1
            return await self.update(user_id, {'session_count': new_count})
            
        except Exception as e:
            self.logger.error(f"增加会话计数失败: {e}")
            return False
    
    async def update_last_active_time(self, user_id: int) -> bool:
        """更新用户最后活跃时间"""
        try:
            current_time = datetime.utcnow()
            update_data = {'last_active_time': current_time}
            
            # 如果是第一次活跃，也设置first_active_time
            user = await self.get_by_id(user_id)
            if user and not user.get('first_active_time'):
                update_data['first_active_time'] = current_time
            
            return await self.update(user_id, update_data)
            
        except Exception as e:
            self.logger.error(f"更新最后活跃时间失败: {e}")
            return False
    
    async def get_active_users(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取活跃用户列表"""
        return await self.find_many(limit=limit, is_active=True)
    
    async def get_users_by_level(self, level: int) -> List[Dict[str, Any]]:
        """根据等级获取用户"""
        return await self.find_many(level=level)
    
    async def search_users_by_username(self, username_pattern: str) -> List[Dict[str, Any]]:
        """根据用户名模糊搜索用户"""
        return await self.find_many(username=f'%{username_pattern}%') 