"""
Supabase基础Repository抽象类
定义通用的Supabase数据访问接口模式
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
import logging
from datetime import datetime

T = TypeVar('T')


class SupabaseBaseRepository(ABC, Generic[T]):
    """Supabase基础Repository抽象类"""
    
    def __init__(self, supabase_manager, table_name: str):
        self.supabase_manager = supabase_manager
        self.table_name = table_name
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_client(self):
        """获取Supabase客户端"""
        return self.supabase_manager.get_client()
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> T:
        """创建记录"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        """根据ID获取记录"""
        pass
    
    @abstractmethod
    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """更新记录"""
        pass
    
    @abstractmethod
    async def delete(self, id: int) -> bool:
        """删除记录"""
        pass
    
    async def exists(self, **conditions) -> bool:
        """检查记录是否存在"""
        try:
            record = await self.find_one(**conditions)
            return record is not None
        except Exception as e:
            self.logger.error(f"检查记录存在性失败: {e}")
            return False
    
    @abstractmethod
    async def find_one(self, **conditions) -> Optional[T]:
        """查找单条记录"""
        pass
    
    @abstractmethod
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[T]:
        """查找多条记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            
            # 🔧 修复：supabase==2.3.4 不支持 .offset() 方法
            # 使用 .range() 方法替代 offset + limit 的组合
            if limit is not None and offset is not None:
                # range(start, end) - 包含start，包含end
                end_index = offset + limit - 1
                query = query.range(offset, end_index)
            elif limit is not None:
                # 只有limit，从0开始
                query = query.limit(limit)
            elif offset is not None:
                # 只有offset，使用range从offset开始到一个大数
                query = query.range(offset, offset + 999)  # 假设最多返回1000条
                
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            self.logger.error(f"查找多条记录失败: {e}")
            return []

    
    def _build_supabase_filters(self, query, conditions: Dict[str, Any]):
        """构建Supabase查询过滤器"""
        for key, value in conditions.items():
            if value is not None:
                if isinstance(value, (list, tuple)):
                    query = query.in_(key, value)
                elif isinstance(value, str) and value.startswith('%') and value.endswith('%'):
                    # 模糊匹配
                    query = query.ilike(key, value)
                else:
                    query = query.eq(key, value)
        return query
    
    def _prepare_data_for_insert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """为插入操作准备数据"""
        prepared_data = data.copy()
        
        # 处理时间字段
        for key, value in prepared_data.items():
            if isinstance(value, datetime):
                prepared_data[key] = value.isoformat()
        
        # 移除None值（可选，根据业务需求）
        prepared_data = {k: v for k, v in prepared_data.items() if v is not None}
        
        return prepared_data
    
    def _prepare_data_for_update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """为更新操作准备数据"""
        prepared_data = data.copy()
        
        # 处理时间字段
        for key, value in prepared_data.items():
            if isinstance(value, datetime):
                prepared_data[key] = value.isoformat()
        
        # 添加更新时间
        if 'updated_at' not in prepared_data:
            prepared_data['updated_at'] = datetime.utcnow().isoformat()
        
        # 移除None值（可选，根据业务需求）
        prepared_data = {k: v for k, v in prepared_data.items() if v is not None}
        
        return prepared_data
    
    async def bulk_insert(self, data_list: List[Dict[str, Any]]) -> List[T]:
        """批量插入记录"""
        try:
            client = self.get_client()
            prepared_data = [self._prepare_data_for_insert(data) for data in data_list]
            
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data:
                self.logger.info(f"批量插入成功: {len(result.data)} 条记录")
                return result.data
            else:
                self.logger.warning("批量插入返回空数据")
                return []
                
        except Exception as e:
            self.logger.error(f"批量插入失败: {e}")
            raise
    
    async def count(self, **conditions) -> int:
        """计算符合条件的记录数量"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*', count='exact')
            query = self._build_supabase_filters(query, conditions)
            
            result = query.execute()
            return result.count if result.count is not None else 0
            
        except Exception as e:
            self.logger.error(f"计算记录数量失败: {e}")
            return 0
    
    async def get_latest(self, order_by: str = 'created_at', **conditions) -> Optional[T]:
        """获取最新的一条记录"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order(order_by, desc=True).limit(1)
            
            result = query.execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"获取最新记录失败: {e}")
            return None 