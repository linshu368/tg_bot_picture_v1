"""
Supabase积分记录Repository
负责用户积分变动记录的CRUD操作 - Supabase版本
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .supabase_base_repository import SupabaseBaseRepository


class SupabasePointRecordRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase积分记录数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'point_records')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建积分记录"""
        try:
            client = self.get_client()
            
            # 准备数据
            record_data = {
                'user_id': data['user_id'],
                'points_change': data['points_change'],
                'action_type': data['action_type'],
                'description': data.get('description', ''),
                'points_balance': data.get('points_balance', 0),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 插入记录
            result = client.table(self.table_name).insert(record_data).execute()
            
            if result.data and len(result.data) > 0:
                created_record = result.data[0]
                self.logger.info(f"积分记录创建成功: user_id={data['user_id']}, change={data['points_change']}")
                return created_record
            else:
                raise Exception("插入积分记录失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建积分记录失败: {e}")
            raise
    
    async def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取积分记录"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', record_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取积分记录失败: {e}")
            return None
    
    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新积分记录（一般不允许修改历史记录）"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', record_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"积分记录更新成功: record_id={record_id}")
                return True
            else:
                self.logger.warning(f"积分记录更新失败: record_id={record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新积分记录失败: {e}")
            return False
    
    async def delete(self, record_id: int) -> bool:
        """删除积分记录（物理删除，谨慎使用）"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', record_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"积分记录删除成功: record_id={record_id}")
                return True
            else:
                self.logger.warning(f"积分记录删除失败: record_id={record_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除积分记录失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单条积分记录"""
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
            self.logger.error(f"查找积分记录失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多条积分记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order('created_at', desc=True)  # 默认按时间倒序
            
            if limit is not None:
                query = query.limit(limit)
            # 注意：Supabase客户端不支持offset，如果需要分页，需要手动处理
            # if offset is not None:
            #     query = query.offset(offset)
                
            result = query.execute()
            data = result.data or []
            
            # 手动处理offset（如果提供了offset）
            if offset is not None and offset > 0:
                data = data[offset:]
            
            return data
            
        except Exception as e:
            self.logger.error(f"查找多条积分记录失败: {e}")
            return []
    
    async def get_user_records(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户的积分记录"""
        return await self.find_many(limit=limit, offset=offset, user_id=user_id)
    
    async def get_records_by_action_type(self, action_type: str, limit: int = None) -> List[Dict[str, Any]]:
        """根据操作类型获取积分记录"""
        return await self.find_many(limit=limit, action_type=action_type)
    
    async def get_records_in_date_range(self, start_date: datetime, end_date: datetime, 
                                       user_id: int = None) -> List[Dict[str, Any]]:
        """获取指定日期范围内的积分记录"""
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
            self.logger.error(f"获取日期范围积分记录失败: {e}")
            return []
    
    async def get_daily_summary(self, user_id: int, date: datetime) -> Dict[str, Any]:
        """获取用户某天的积分变动汇总"""
        try:
            # 计算当天的开始和结束时间
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            records = await self.get_records_in_date_range(start_of_day, end_of_day, user_id)
            
            # 计算汇总
            total_gained = sum(r['points_change'] for r in records if r['points_change'] > 0)
            total_spent = sum(abs(r['points_change']) for r in records if r['points_change'] < 0)
            net_change = sum(r['points_change'] for r in records)
            
            # 按操作类型分组
            by_action_type = {}
            for record in records:
                action_type = record['action_type']
                if action_type not in by_action_type:
                    by_action_type[action_type] = {
                        'count': 0,
                        'total_change': 0,
                        'records': []
                    }
                by_action_type[action_type]['count'] += 1
                by_action_type[action_type]['total_change'] += record['points_change']
                by_action_type[action_type]['records'].append(record)
            
            return {
                'date': date.date(),
                'user_id': user_id,
                'total_records': len(records),
                'total_gained': total_gained,
                'total_spent': total_spent,
                'net_change': net_change,
                'by_action_type': by_action_type,
                'records': records
            }
            
        except Exception as e:
            self.logger.error(f"获取每日积分汇总失败: {e}")
            return {
                'date': date.date(),
                'user_id': user_id,
                'total_records': 0,
                'total_gained': 0,
                'total_spent': 0,
                'net_change': 0,
                'by_action_type': {},
                'records': []
            }
    
    async def get_user_total_stats(self, user_id: int) -> Dict[str, Any]:
        """获取用户积分统计"""
        try:
            records = await self.get_user_records(user_id, limit=1000)
            
            if not records:
                return {
                    'user_id': user_id,
                    'total_records': 0,
                    'total_gained': 0,
                    'total_spent': 0,
                    'net_change': 0,
                    'by_action_type': {}
                }
            
            # 计算统计
            total_gained = sum(r['points_change'] for r in records if r['points_change'] > 0)
            total_spent = sum(abs(r['points_change']) for r in records if r['points_change'] < 0)
            net_change = sum(r['points_change'] for r in records)
            
            # 按操作类型分组
            by_action_type = {}
            for record in records:
                action_type = record['action_type']
                if action_type not in by_action_type:
                    by_action_type[action_type] = {
                        'count': 0,
                        'total_change': 0
                    }
                by_action_type[action_type]['count'] += 1
                by_action_type[action_type]['total_change'] += record['points_change']
            
            return {
                'user_id': user_id,
                'total_records': len(records),
                'total_gained': total_gained,
                'total_spent': total_spent,
                'net_change': net_change,
                'by_action_type': by_action_type
            }
            
        except Exception as e:
            self.logger.error(f"获取用户积分统计失败: {e}")
            return {
                'user_id': user_id,
                'total_records': 0,
                'total_gained': 0,
                'total_spent': 0,
                'net_change': 0,
                'by_action_type': {}
            } 