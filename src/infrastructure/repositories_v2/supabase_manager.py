"""
Supabase数据库管理器
负责Supabase连接管理和基础操作
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from src.utils.config.settings import DatabaseSettings


class SupabaseManager:
    """Supabase数据库管理器"""
    
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self._client: Optional[Client] = None
        
    async def initialize(self):
        """初始化Supabase客户端"""
        try:
            self.logger.info("初始化Supabase连接")
            
            if not self.settings.supabase_url or not self.settings.supabase_key:
                raise ValueError("Supabase URL和Key不能为空")
            
            # 创建Supabase客户端
            self._client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_key
            )
            
            # 测试连接
            await self._test_connection()
            
            self.logger.info("Supabase连接初始化完成")
            
        except Exception as e:
            self.logger.error(f"Supabase初始化失败: {e}")
            raise
    
    async def close(self):
        """关闭连接（Supabase客户端无需显式关闭）"""
        self.logger.info("Supabase连接已释放")
    
    def get_client(self) -> Client:
        """获取Supabase客户端"""
        self.logger.info(f"[SupabaseManager] 开始 get_client()")
        if not self._client:
            self.logger.error(f"[SupabaseManager] 客户端未初始化")
            raise RuntimeError("Supabase客户端未初始化")
        self.logger.info(f"[SupabaseManager] 返回客户端实例")
        return self._client
    
    def get_beijing_time(self, dt: datetime = None) -> datetime:
        """获取北京时间"""
        if dt is None:
            dt = datetime.utcnow()
        beijing_time = dt.replace(tzinfo=timezone.utc).astimezone(
            timezone(timedelta(hours=8))
        )
        return beijing_time
    
    async def _test_connection(self):
        """测试Supabase连接"""
        try:
            # 尝试查询一个简单的系统表来测试连接
            # 使用 rpc 调用一个简单的函数来测试连接
            result = self._client.rpc('version').execute()
            self.logger.info("Supabase连接测试成功")
        except Exception as e:
            # 如果 rpc 不可用，尝试简单的表查询
            try:
                # 尝试查询一个不存在的表，如果连接正常会返回表不存在的错误
                result = self._client.table('test_connection_table').select('*').limit(1).execute()
            except Exception as e2:
                # 如果错误信息包含表不存在，说明连接是正常的
                if "does not exist" in str(e2).lower() or "not found" in str(e2).lower():
                    self.logger.info("Supabase连接测试成功")
                else:
                    self.logger.error(f"Supabase连接测试失败: {e2}")
                    raise e2
    
  