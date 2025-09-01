"""
Supabase每日签到Repository
负责签到记录数据的CRUD操作 - Supabase版本
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from .supabase_base_repository import SupabaseBaseRepository


class SupabaseDailyCheckinRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase每日签到数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'daily_checkins')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建签到记录"""
        try:
            client = self.get_client()
            
            # 🔧 新增：准备签到数据
            checkin_data = {
                'user_id': data['user_id'],
                'checkin_date': data['checkin_date'],  # 格式: YYYY-MM-DD
                'points_earned': data.get('points_earned', 0),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 使用 upsert 避免重复签到
            result = client.table(self.table_name).upsert(checkin_data).execute()
            
            if result.data and len(result.data) > 0:
                created_checkin = result.data[0]
                self.logger.info(f"签到记录创建成功: user_id={data['user_id']}, date={data['checkin_date']}")
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
            result = client.table(self.table_name).select('*').eq('id', checkin_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取签到记录失败: {e}")
            return None
    
    async def update(self, checkin_id: int, data: Dict[str, Any]) -> bool:
        """更新签到记录"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', checkin_id).execute()
            
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
        """删除签到记录"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', checkin_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"签到记录删除成功: checkin_id={checkin_id}")
                return True
            else:
                self.logger.warning(f"签到记录删除失败: checkin_id={checkin_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除签到记录失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个签到记录"""
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
            self.logger.error(f"查找签到记录失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个签到记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order('checkin_date', desc=True)
            
            # 🔧 使用修复后的分页方法
            if limit is not None and offset is not None:
                end_index = offset + limit - 1
                query = query.range(offset, end_index)
            elif limit is not None:
                query = query.limit(limit)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"查找多个签到记录失败: {e}")
            return []
    
    async def is_checked_in_today(self, user_id: int, date_str: str) -> bool:
        """检查用户今日是否已签到"""
        try:
            checkin = await self.find_one(user_id=user_id, checkin_date=date_str)
            return checkin is not None
        except Exception as e:
            self.logger.error(f"检查签到状态失败: {e}")
            return True  # 出错时认为已签到，避免重复
    
    async def get_user_checkins(self, user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        """获取用户的签到记录"""
        return await self.find_many(limit=limit, user_id=user_id)
    
    async def get_user_checkin_streak(self, user_id: int) -> int:
        """获取用户连续签到天数"""
        try:
            # 获取用户最近30天的签到记录，按日期倒序
            recent_checkins = await self.get_user_checkins(user_id, 30)
            
            if not recent_checkins:
                return 0
            
            # 计算连续签到天数
            streak = 0
            today = date.today()
            
            for checkin in recent_checkins:
                checkin_date = datetime.fromisoformat(checkin['checkin_date']).date()
                expected_date = today - timedelta(days=streak)
                
                if checkin_date == expected_date:
                    streak += 1
                else:
                    break
            
            return streak
            
        except Exception as e:
            self.logger.error(f"获取连续签到天数失败: {e}")
            return 0