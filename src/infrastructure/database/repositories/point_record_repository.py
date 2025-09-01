"""
积分记录Repository
负责用户积分变动记录的CRUD操作
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base_repository import BaseRepository


class PointRecordRepository(BaseRepository[Dict[str, Any]]):
    """积分记录数据访问层"""
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建积分记录"""
        conn = await self.get_connection()
        
        try:
            cursor = await conn.execute("""
                INSERT INTO point_records (
                    user_id, points_change, action_type, description, points_balance
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                data['user_id'],
                data['points_change'],
                data['action_type'],
                data.get('description', ''),
                data.get('points_balance', 0)
            ))
            
            record_id = cursor.lastrowid
            await conn.commit()
            
            self.logger.info(f"积分记录创建成功: user_id={data['user_id']}, change={data['points_change']}")
            
            return await self.get_by_id(record_id)
            
        except Exception as e:
            self.logger.error(f"创建积分记录失败: {e}")
            await conn.rollback()
            raise
    
    async def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取积分记录"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        cursor = await conn.execute("""
            SELECT id, user_id, points_change, action_type, description,
                   points_balance, created_at
            FROM point_records WHERE id = ?
        """, (record_id,))
        
        row = await cursor.fetchone()
        return row
    
    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新积分记录（一般不允许修改历史记录）"""
        self.logger.warning("尝试修改积分历史记录，这通常不被允许")
        return False
    
    async def delete(self, record_id: int) -> bool:
        """删除积分记录（一般不允许删除历史记录）"""
        self.logger.warning("尝试删除积分历史记录，这通常不被允许")
        return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单条积分记录"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        where_clause, values = self._build_where_clause(conditions)
        
        cursor = await conn.execute(f"""
            SELECT id, user_id, points_change, action_type, description,
                   points_balance, created_at
            FROM point_records{where_clause}
            ORDER BY created_at DESC
        """, values)
        
        row = await cursor.fetchone()
        return row
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多条积分记录"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        where_clause, values = self._build_where_clause(conditions)
        
        sql = f"""
            SELECT id, user_id, points_change, action_type, description,
                   points_balance, created_at
            FROM point_records{where_clause}
            ORDER BY created_at DESC
        """
        
        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"
        
        cursor = await conn.execute(sql, values)
        rows = await cursor.fetchall()
        return rows
    
    async def get_user_records(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的积分记录"""
        return await self.find_many(limit=limit, user_id=user_id)
    
    async def get_user_records_by_type(self, user_id: int, action_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """根据操作类型获取用户积分记录"""
        return await self.find_many(limit=limit, user_id=user_id, action_type=action_type)
    
    async def get_user_total_earned(self, user_id: int) -> int:
        """获取用户总获得积分（不包括消费）"""
        conn = await self.get_connection()
        
        # 临时保存原来的row_factory
        original_row_factory = conn.row_factory
        # 设置为None以获取tuple结果
        conn.row_factory = None
        
        try:
            cursor = await conn.execute("""
                SELECT COALESCE(SUM(points_change), 0) 
                FROM point_records 
                WHERE user_id = ? AND points_change > 0
            """, (user_id,))
            
            row = await cursor.fetchone()
            result = row[0] if row else 0
            self.logger.debug(f"用户 {user_id} 总获得积分: {result}")
            return result
        finally:
            # 恢复原来的row_factory
            conn.row_factory = original_row_factory
    
    async def get_user_total_spent(self, user_id: int) -> int:
        """获取用户总消费积分"""
        conn = await self.get_connection()
        
        # 临时保存原来的row_factory
        original_row_factory = conn.row_factory
        # 设置为None以获取tuple结果
        conn.row_factory = None
        
        try:
            cursor = await conn.execute("""
                SELECT COALESCE(SUM(ABS(points_change)), 0) 
                FROM point_records 
                WHERE user_id = ? AND points_change < 0
            """, (user_id,))
            
            row = await cursor.fetchone()
            result = row[0] if row else 0
            return result
        finally:
            # 恢复原来的row_factory
            conn.row_factory = original_row_factory
    
    async def get_recent_records(self, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近几天的积分记录"""
        conn = await self.get_connection()
        conn.row_factory = self._dict_factory
        
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor = await conn.execute(f"""
            SELECT id, user_id, points_change, action_type, description,
                   points_balance, created_at
            FROM point_records
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT {limit}
        """, (since_date,))
        
        rows = await cursor.fetchall()
        return rows
    
    async def get_records_by_action_type(self, action_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """根据操作类型获取积分记录"""
        return await self.find_many(limit=limit, action_type=action_type)
    
    async def get_daily_summary(self, user_id: int, date: str) -> Dict[str, Any]:
        """获取用户某日的积分变动汇总"""
        conn = await self.get_connection()
        
        # 查询当日的积分变动
        cursor = await conn.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN points_change > 0 THEN points_change ELSE 0 END), 0) as earned,
                COALESCE(SUM(CASE WHEN points_change < 0 THEN ABS(points_change) ELSE 0 END), 0) as spent,
                COUNT(*) as transaction_count
            FROM point_records
            WHERE user_id = ? AND DATE(created_at) = ?
        """, (user_id, date))
        
        row = await cursor.fetchone()
        
        if row:
            return {
                'date': date,
                'earned': row[0],
                'spent': row[1],
                'net_change': row[0] - row[1],
                'transaction_count': row[2]
            }
        
        return {
            'date': date,
            'earned': 0,
            'spent': 0,
            'net_change': 0,
            'transaction_count': 0
        } 