"""
Supabase每日签到Repository V2
负责daily_checkins_v2表的CRUD操作 - 专注于用户每日签到管理

v2版本特点：
1. 每日签到记录管理：签到日期、获得积分
2. 唯一约束：用户每天只能签到一次 (user_id, checkin_date)
3. 只有created_at字段，没有updated_at字段
4. 简洁的表结构，专注于签到核心功能
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from .base_repository_v2 import BaseRepositoryV2
import asyncio


class DailyCheckinRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase每日签到数据访问层 V2版本
    
    专注于每日签到的CRUD操作：
    - 用户签到记录管理
    - 签到历史查询
    - 签到统计分析
    """
    
    def __init__(self, supabase_manager):
        # daily_checkins_v2表没有updated_at字段，只有created_at
        super().__init__(supabase_manager, 'daily_checkins_v2', has_updated_at=False)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建签到记录
        
        包含用户ID、签到日期、获得积分
        """
        try:
            client = self.get_client()
            
            # 设置签到数据
            checkin_data = {
                'user_id': data['user_id'],
                'checkin_date': data.get('checkin_date', date.today().isoformat()),
                'points_earned': data.get('points_earned', 0),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 过滤有效字段
            allowed_fields = {'user_id', 'checkin_date', 'points_earned'}
            checkin_data.update({k: v for k, v in data.items() if k in allowed_fields})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(checkin_data)
            
            # 插入数据（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).insert(prepared_data).execute()
            )
            
            if result.data and len(result.data) > 0:
                created_checkin = result.data[0]
                self.logger.info(f"签到记录创建成功: user_id={data['user_id']}, date={checkin_data['checkin_date']}")
                return created_checkin
            else:
                raise Exception("插入签到记录失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建签到记录失败: {e}")
            raise
    
    async def get_by_id(self, checkin_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取签到记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).select('*').eq('id', checkin_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取签到记录失败: {e}")
            return None
    
    async def get_user_checkin_by_date(self, user_id: int, checkin_date: str) -> Optional[Dict[str, Any]]:
        """根据用户ID和日期获取签到记录"""
        try:
            client = self.get_client()
            result = await asyncio.to_thread(
                lambda: (client.table(self.table_name)
                     .select('*')
                     .eq('user_id', user_id)
                     .eq('checkin_date', checkin_date)
                     .execute())
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据用户ID和日期获取签到记录失败: {e}")
            return None
    
    async def update(self, checkin_id: int, data: Dict[str, Any]) -> bool:
        """更新签到记录信息
        
        主要用于更新获得积分（实际使用中很少更新签到记录）
        """
        try:
            client = self.get_client()
            
            # 过滤允许更新的字段
            allowed_fields = {'points_earned'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: checkin_id={checkin_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 执行更新（后台线程执行，避免阻塞事件循环）
            result = await asyncio.to_thread(
                lambda: client.table(self.table_name).update(prepared_data).eq('id', checkin_id).execute()
            )
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"签到记录更新成功: checkin_id={checkin_id}")
                return True
            else:
                self.logger.warning(f"签到记录更新失败: checkin_id={checkin_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新签到记录失败: {e}")
            return False
    
    async def delete(self, checkin_id: int) -> bool:
        """删除签到记录（物理删除）"""
        return await self.hard_delete(checkin_id)
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个签到记录"""
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
            self.logger.error(f"查找签到记录失败: {e}")
            return None
    
    # ==================== 业务方法 ====================
    
    async def get_user_checkin_history(self, user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        """获取用户的签到历史"""
        try:
            client = self.get_client()
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .order('checkin_date', desc=True))
            
            if limit is not None:
                query = query.limit(limit)
                
            result = await asyncio.to_thread(lambda: query.execute())
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"获取用户签到历史失败: {e}")
            return []
    
    async def check_user_checked_in_today(self, user_id: int) -> bool:
        """检查用户今天是否已签到"""
        today = date.today().isoformat()
        checkin = await self.get_user_checkin_by_date(user_id, today)
        return checkin is not None
    
    async def get_user_checkin_streak(self, user_id: int) -> int:
        """获取用户连续签到天数"""
        try:
            # 获取用户最近的签到记录
            checkins = await self.get_user_checkin_history(user_id, limit=365)  # 最多查一年
            
            if not checkins:
                return 0
            
            # 按日期排序（最新的在前）
            checkins.sort(key=lambda x: x['checkin_date'], reverse=True)
            
            # 计算连续签到天数
            streak = 0
            current_date = date.today()
            
            for checkin in checkins:
                checkin_date = date.fromisoformat(checkin['checkin_date'])
                
                # 如果是今天或昨天开始计算
                if checkin_date == current_date:
                    streak += 1
                    current_date = current_date - timedelta(days=1)
                elif checkin_date == current_date:
                    streak += 1
                    current_date = current_date - timedelta(days=1)
                else:
                    # 不连续，中断计算
                    break
            
            return streak
            
        except Exception as e:
            self.logger.error(f"获取用户连续签到天数失败: {e}")
            return 0
    
    async def get_user_checkin_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取用户签到统计信息"""
        try:
            client = self.get_client()
            
            # 计算日期范围
            from_date = (date.today() - timedelta(days=days)).isoformat()
            
            query = (client.table(self.table_name)
                    .select('*')
                    .eq('user_id', user_id)
                    .gte('checkin_date', from_date))
                    
            result = await asyncio.to_thread(lambda: query.execute())
            checkins = result.data or []
            
            # 统计信息
            total_checkins = len(checkins)
            total_points_earned = sum(c.get('points_earned', 0) for c in checkins)
            
            # 计算签到率
            checkin_rate = (total_checkins / days * 100) if days > 0 else 0
            
            # 获取连续签到天数
            streak = await self.get_user_checkin_streak(user_id)
            
            # 检查今天是否已签到
            checked_in_today = await self.check_user_checked_in_today(user_id)
            
            return {
                'total_checkins': total_checkins,
                'total_points_earned': total_points_earned,
                'checkin_rate': round(checkin_rate, 2),
                'current_streak': streak,
                'checked_in_today': checked_in_today,
                'days': days
            }
            
        except Exception as e:
            self.logger.error(f"获取用户签到统计失败: {e}")
            return {}
    
    # ==================== 兼容性方法（与原Repository接口保持一致） ====================
    
    async def checkin_user(self, user_id: int, points_earned: int = 1) -> Dict[str, Any]:
        """用户签到（兼容原接口）
        
        如果今天已签到则返回现有记录，否则创建新记录
        """
        try:
            # 检查今天是否已签到
            today = date.today().isoformat()
            existing_checkin = await self.get_user_checkin_by_date(user_id, today)
            
            if existing_checkin:
                self.logger.info(f"用户今天已签到: user_id={user_id}")
                return existing_checkin
            
            # 创建新的签到记录
            checkin_data = {
                'user_id': user_id,
                'checkin_date': today,
                'points_earned': points_earned
            }
            
            return await self.create(checkin_data)
            
        except Exception as e:
            self.logger.error(f"用户签到失败: {e}")
            raise 

    # ==================== 业务方法（保持原有逻辑不变） ====================
    
    async def get_by_user_id_and_date(self, user_id: int, checkin_date) -> Optional[Dict[str, Any]]:
        """根据用户ID和日期获取签到记录（兼容接口）"""
        try:
            # 支持date对象和字符串两种格式
            if hasattr(checkin_date, 'isoformat'):
                date_str = checkin_date.isoformat()
            else:
                date_str = str(checkin_date)
            
            checkin = await self.get_user_checkin_by_date(user_id, date_str)
            return checkin  # 直接返回，无需字段映射
        except Exception as e:
            self.logger.error(f"根据用户ID和日期获取签到记录失败: {e}")
            return None 