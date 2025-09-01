"""
基础Repository抽象类
定义通用的数据访问接口模式
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
import logging

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """基础Repository抽象类"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def get_connection(self):
        """获取数据库连接"""
        return await self.db_manager.get_connection()
    
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
        pass
    
    def _build_where_clause(self, conditions: Dict[str, Any]) -> tuple:
        """构建WHERE子句"""
        if not conditions:
            return "", []
        
        where_parts = []
        values = []
        
        for key, value in conditions.items():
            if value is None:
                where_parts.append(f"{key} IS NULL")
            else:
                where_parts.append(f"{key} = ?")
                values.append(value)
        
        where_clause = " WHERE " + " AND ".join(where_parts)
        return where_clause, values
    
    def _dict_factory(self, cursor, row):
        """将查询结果转换为字典"""
        fields = [column[0] for column in cursor.description]
        return dict(zip(fields, row)) 