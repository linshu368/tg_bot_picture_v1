"""
用户Repository
负责用户数据的CRUD操作
"""

import random
import string
from typing import Dict, Any, List, Optional
from .base_repository import BaseRepository


class UserRepository(BaseRepository[Dict[str, Any]]):
    """用户数据访问层"""
    
    def __init__(self, db_manager):
        super().__init__(db_manager)
        self.uid_prefix = "u_"
        self.uid_length = 8
    
    def generate_uid(self) -> str:
        """生成唯一的用户ID"""
        return self.uid_prefix + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=self.uid_length)
        )
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新用户"""
        conn = await self.get_connection()
        
        # 生成唯一UID
        uid = self.generate_uid()
        while await self.find_one(uid=uid):
            uid = self.generate_uid()
        
        try:
            # 设置默认值
            user_data = {
                'telegram_id': data['telegram_id'],
                'uid': uid,
                'username': data.get('username'),
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
                'points': 50,  # 默认初始积分
                'level': 1,
                'is_active': 1,
                'session_count': 0,
                'total_points_spent': 0,
                'total_paid_amount': 0.0,
                'first_add': 0,
                'utm_source': '000',
                'first_active_time': self.db_manager.get_beijing_time().isoformat(),
                'last_active_time': self.db_manager.get_beijing_time().isoformat(),
                'total_messages_sent': 0
            }
            
            # 插入用户记录
            cursor = await conn.execute("""
                INSERT INTO users (
                    telegram_id, uid, username, first_name, last_name,
                    points, level, is_active, session_count, total_points_spent,
                    total_paid_amount, first_add, utm_source, first_active_time,
                    last_active_time, total_messages_sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_data['telegram_id'], user_data['uid'], user_data['username'],
                user_data['first_name'], user_data['last_name'], user_data['points'],
                user_data['level'], user_data['is_active'], user_data['session_count'],
                user_data['total_points_spent'], user_data['total_paid_amount'],
                user_data['first_add'], user_data['utm_source'], user_data['first_active_time'],
                user_data['last_active_time'], user_data['total_messages_sent']
            ))
            
            user_id = cursor.lastrowid
            await conn.commit()
            
            self.logger.info(f"新用户创建成功: telegram_id={user_data['telegram_id']}, uid={uid}")
            
            # 返回创建的用户
            return await self.get_by_id(user_id)
            
        except Exception as e:
            self.logger.error(f"创建用户失败: {e}")
            await conn.rollback()
            raise
    
    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        cursor = await conn.execute("""
            SELECT id, telegram_id, uid, username, first_name, last_name,
                   points, level, is_active, created_at, updated_at,
                   session_count, total_points_spent, total_paid_amount,
                   first_add, utm_source, first_active_time, last_active_time,
                   total_messages_sent
            FROM users WHERE id = ?
        """, (user_id,))
        
        row = await cursor.fetchone()
        return row
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """根据Telegram ID获取用户"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        cursor = await conn.execute("""
            SELECT id, telegram_id, uid, username, first_name, last_name,
                   points, level, is_active, created_at, updated_at,
                   session_count, total_points_spent, total_paid_amount,
                   first_add, utm_source, first_active_time, last_active_time,
                   total_messages_sent
            FROM users WHERE telegram_id = ?
        """, (telegram_id,))
        
        row = await cursor.fetchone()
        return row
    
    async def get_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """根据UID获取用户"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        cursor = await conn.execute("""
            SELECT id, telegram_id, uid, username, first_name, last_name,
                   points, level, is_active, created_at, updated_at,
                   session_count, total_points_spent, total_paid_amount,
                   first_add, utm_source, first_active_time, last_active_time,
                   total_messages_sent
            FROM users WHERE uid = ?
        """, (uid,))
        
        row = await cursor.fetchone()
        return row
    
    async def update(self, user_id: int, data: Dict[str, Any]) -> bool:
        """更新用户信息"""
        if not data:
            return False
        
        conn = await self.get_connection()
        
        # 构建更新字段
        set_fields = []
        values = []
        
        for key, value in data.items():
            if key != 'id':  # 不允许更新ID
                set_fields.append(f"{key} = ?")
                values.append(value)
        
        if not set_fields:
            return False
        
        # 添加更新时间
        set_fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)
        
        try:
            cursor = await conn.execute(
                f"UPDATE users SET {', '.join(set_fields)} WHERE id = ?",
                values
            )
            await conn.commit()
            
            affected_rows = cursor.rowcount
            return affected_rows > 0
            
        except Exception as e:
            self.logger.error(f"更新用户失败: {e}")
            await conn.rollback()
            return False
    
    async def update_telegram_id(self, uid: str, telegram_id: int) -> bool:
        """更新用户的telegram_id（用于账号恢复绑定）"""
        conn = await self.get_connection()
        
        try:
            cursor = await conn.execute("""
                UPDATE users 
                SET telegram_id = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE uid = ?
            """, (telegram_id, uid))
            
            await conn.commit()
            
            affected_rows = cursor.rowcount
            if affected_rows > 0:
                self.logger.info(f"成功更新用户telegram_id: uid={uid}, telegram_id={telegram_id}")
                return True
            else:
                self.logger.warning(f"未找到UID为 {uid} 的用户")
                return False
                
        except Exception as e:
            self.logger.error(f"更新用户telegram_id失败: {e}")
            await conn.rollback()
            return False
    
    async def delete(self, user_id: int) -> bool:
        """删除用户（软删除）"""
        return await self.update(user_id, {'is_active': 0})
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个用户"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        where_clause, values = self._build_where_clause(conditions)
        
        cursor = await conn.execute(f"""
            SELECT id, telegram_id, uid, username, first_name, last_name,
                   points, level, is_active, created_at, updated_at,
                   session_count, total_points_spent, total_paid_amount,
                   first_add, utm_source, first_active_time, last_active_time,
                   total_messages_sent
            FROM users{where_clause}
        """, values)
        
        row = await cursor.fetchone()
        return row
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个用户"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        where_clause, values = self._build_where_clause(conditions)
        
        sql = f"""
            SELECT id, telegram_id, uid, username, first_name, last_name,
                   points, level, is_active, created_at, updated_at,
                   session_count, total_points_spent, total_paid_amount,
                   first_add, utm_source, first_active_time, last_active_time,
                   total_messages_sent
            FROM users{where_clause}
            ORDER BY created_at DESC
        """
        
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        
        cursor = await conn.execute(sql, values)
        rows = await cursor.fetchall()
        return rows
    
    async def bind_user_to_uid(self, telegram_id: int, uid: str) -> bool:
        """将新的telegram_id绑定到已存在的UID（用于账号恢复）"""
        conn = await self.get_connection()
        
        try:
            cursor = await conn.execute("""
                UPDATE users SET telegram_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE uid = ?
            """, (telegram_id, uid))
            
            await conn.commit()
            affected_rows = cursor.rowcount
            
            if affected_rows > 0:
                self.logger.info(f"用户绑定成功: telegram_id={telegram_id}, uid={uid}")
                return True
            else:
                self.logger.warning(f"UID不存在: {uid}")
                return False
                
        except Exception as e:
            self.logger.error(f"用户绑定失败: {e}")
            await conn.rollback()
            return False
    
    async def update_last_active(self, user_id: int) -> bool:
        """更新用户最后活跃时间"""
        return await self.update(user_id, {
            'last_active_time': self.db_manager.get_beijing_time().isoformat()
        })
    
    async def increment_session_count(self, user_id: int) -> bool:
        """增加用户会话计数"""
        conn = await self.get_connection()
        
        try:
            cursor = await conn.execute("""
                UPDATE users SET 
                    session_count = session_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id,))
            
            await conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"更新会话计数失败: {e}")
            await conn.rollback()
            return False
    
    async def increment_message_count(self, user_id: int) -> bool:
        """增加用户消息计数"""
        conn = await self.get_connection()
        
        try:
            cursor = await conn.execute("""
                UPDATE users SET 
                    total_messages_sent = total_messages_sent + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id,))
            
            await conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"更新消息计数失败: {e}")
            await conn.rollback()
            return False
    
    async def get_active_users_count(self) -> int:
        """获取活跃用户数"""
        conn = await self.get_connection()
        
        # 临时保存原来的row_factory
        original_row_factory = conn.row_factory
        # 设置为None以获取tuple结果
        conn.row_factory = None
        
        try:
            cursor = await conn.execute("""
                SELECT COUNT(*) FROM users WHERE is_active = 1
            """)
            
            row = await cursor.fetchone()
            result = row[0] if row else 0
            return result
        finally:
            # 恢复原来的row_factory
            conn.row_factory = original_row_factory
    
    async def get_users_by_level(self, level: int) -> List[Dict[str, Any]]:
        """根据等级获取用户"""
        return await self.find_many(level=level, is_active=1) 