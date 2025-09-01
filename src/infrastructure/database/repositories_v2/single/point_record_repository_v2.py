"""
Supabase积分记录Repository V2
负责point_records_v2表的CRUD操作 - 专注于用户积分变动记录管理

v2版本变化：
1. 表字段已重命名为与旧版一致：points_change, points_balance
2. 新增related_event_id字段用于关联其他事件
3. 移除updated_at字段
4. 保持所有原有业务方法不变
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base_repository_v2 import BaseRepositoryV2


class PointRecordRepositoryV2(BaseRepositoryV2[Dict[str, Any]]):
    """Supabase积分记录数据访问层 V2版本
    
    专注于积分变动记录管理：
    - 积分变动记录的CRUD操作
    - 用户积分历史查询
    - 积分统计和汇总
    - 按操作类型和时间范围查询
    """
    
    def __init__(self, supabase_manager):
        # point_records_v2表没有updated_at字段
        super().__init__(supabase_manager, 'point_records_v2', has_updated_at=False)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建积分记录"""
        try:
            client = self.get_client()
            
            # 直接使用新的字段名（与旧版一致）
            record_data = {
                'user_id': data['user_id'],
                'points_change': data['points_change'],
                'action_type': data['action_type'],
                'description': data.get('description', ''),
                'points_balance': data.get('points_balance', 0),
                'related_event_id': data.get('related_event_id'),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(record_data)
            
            # 插入记录
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data and len(result.data) > 0:
                created_record = result.data[0]
                self.logger.info(f"积分记录创建成功: user_id={data['user_id']}, points_change={record_data['points_change']}")
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
            
            # 过滤允许更新的字段（积分记录一般不允许修改核心字段）
            allowed_fields = {'description', 'related_event_id'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                self.logger.warning(f"没有有效的更新字段: record_id={record_id}")
                return False
            
            # 准备更新数据
            prepared_data = self._prepare_data_for_update(update_data)
            
            # 执行更新
            result = client.table(self.table_name).update(prepared_data).eq('id', record_id).execute()
            
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
        return await self.hard_delete(record_id)
    
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
            
            # 处理分页参数
            if limit is not None and offset is not None:
                end_index = offset + limit - 1
                query = query.range(offset, end_index)
            elif limit is not None:
                query = query.limit(limit)
            elif offset is not None:
                query = query.range(offset, offset + 999)
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"查找多条积分记录失败: {e}")
            return []
    
    # ==================== 业务方法（保持原有逻辑不变） ====================
    
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
            
            # 计算汇总（使用新的字段名）
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
            
            # 计算统计（使用新的字段名）
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
    
    async def get_records_by_event_id(self, related_event_id: str) -> List[Dict[str, Any]]:
        """根据关联事件ID获取积分记录（新增方法，利用v2表的新字段）"""
        return await self.find_many(related_event_id=related_event_id) 