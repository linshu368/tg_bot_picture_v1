"""
系统配置服务
负责系统全局配置的管理和缓存
"""

import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

# 支持两种Repository实现
try:
    # 优先使用Supabase Repository
    from src.infrastructure.database.repositories.supabase_system_config_repository import SupabaseSystemConfigRepository as SystemConfigRepository
    USING_SUPABASE = True
except ImportError:
    # 如果Supabase不可用，可以扩展支持其他实现
    USING_SUPABASE = False


class SystemConfigService:
    """系统配置业务服务"""
    
    def __init__(self, config_repo=None, db_manager=None):
        """
        初始化系统配置服务
        
        Args:
            config_repo: 系统配置Repository实例（Supabase方式）
            db_manager: 数据库管理器（旧方式，向后兼容）
        """
        self.logger = logging.getLogger(__name__)
        self._config_cache = {}  # 简单的内存缓存
        self._cache_timestamp = None
        self.cache_ttl_seconds = 300  # 缓存5分钟
        
        # 支持新的依赖注入方式（Supabase）
        if config_repo:
            self.config_repo = config_repo
            self.db_manager = None
            self.logger.info("使用注入的Supabase Repository")
        elif db_manager:
            # 支持旧的初始化方式（向后兼容）
            self.db_manager = db_manager
            self.config_repo = None
            self.logger.info("使用传统的数据库管理器")
        else:
            raise ValueError("必须提供Repository实例或db_manager")
    
    async def set_config(self, config_key: str, config_value: Union[str, int, float, bool, dict, list],
                        description: str = None) -> bool:
        """设置配置项"""
        try:
            # 将非字符串值转换为JSON字符串存储
            if isinstance(config_value, (dict, list)):
                value_str = json.dumps(config_value, ensure_ascii=False)
            elif isinstance(config_value, bool):
                value_str = 'true' if config_value else 'false'
            else:
                value_str = str(config_value)
            
            result = await self.config_repo.set_config(config_key, value_str, description)
            
            if result:
                # 更新缓存
                self._config_cache[config_key] = value_str
                self.logger.info(f"配置设置成功: {config_key} = {config_value}")
                return True
            else:
                self.logger.error(f"配置设置失败: {config_key}")
                return False
                
        except Exception as e:
            self.logger.error(f"设置配置失败: {e}")
            return False
    
    async def get_config(self, config_key: str, default_value: Any = None) -> Any:
        """获取配置值（自动类型转换）"""
        try:
            # 检查缓存
            if await self._is_cache_valid() and config_key in self._config_cache:
                value_str = self._config_cache[config_key]
            else:
                # 从数据库获取
                value_str = await self.config_repo.get_config_value(config_key)
                if value_str is not None:
                    self._config_cache[config_key] = value_str
            
            if value_str is None:
                return default_value
            
            # 尝试类型转换
            return self._convert_config_value(value_str, default_value)
            
        except Exception as e:
            self.logger.error(f"获取配置失败: {e}")
            return default_value
    
    async def get_config_str(self, config_key: str, default_value: str = None) -> Optional[str]:
        """获取字符串配置值"""
        try:
            return await self.config_repo.get_config_value(config_key, default_value)
        except Exception as e:
            self.logger.error(f"获取字符串配置失败: {e}")
            return default_value
    
    async def get_config_int(self, config_key: str, default_value: int = 0) -> int:
        """获取整数配置值"""
        try:
            return await self.config_repo.get_config_value_as_int(config_key, default_value)
        except Exception as e:
            self.logger.error(f"获取整数配置失败: {e}")
            return default_value
    
    async def get_config_bool(self, config_key: str, default_value: bool = False) -> bool:
        """获取布尔配置值"""
        try:
            return await self.config_repo.get_config_value_as_bool(config_key, default_value)
        except Exception as e:
            self.logger.error(f"获取布尔配置失败: {e}")
            return default_value
    
    async def get_config_json(self, config_key: str, default_value: dict = None) -> dict:
        """获取JSON配置值"""
        try:
            value_str = await self.config_repo.get_config_value(config_key)
            if value_str:
                return json.loads(value_str)
            return default_value or {}
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error(f"获取JSON配置失败: {e}")
            return default_value or {}
    
    async def get_all_configs(self, use_cache: bool = True) -> Dict[str, str]:
        """获取所有配置项"""
        try:
            if use_cache and await self._is_cache_valid():
                return self._config_cache.copy()
            
            configs = await self.config_repo.get_all_configs()
            
            # 更新缓存
            self._config_cache = configs
            self._cache_timestamp = datetime.utcnow()
            
            return configs
            
        except Exception as e:
            self.logger.error(f"获取所有配置失败: {e}")
            return {}
    
    async def delete_config(self, config_key: str) -> bool:
        """删除配置项"""
        try:
            result = await self.config_repo.delete_by_key(config_key)
            
            if result:
                # 从缓存中移除
                self._config_cache.pop(config_key, None)
                self.logger.info(f"配置删除成功: {config_key}")
                return True
            else:
                self.logger.warning(f"配置删除失败: {config_key}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除配置失败: {e}")
            return False
    
    async def bulk_set_configs(self, configs: Dict[str, Any], descriptions: Dict[str, str] = None) -> bool:
        """批量设置配置项"""
        try:
            success_count = 0
            descriptions = descriptions or {}
            
            for config_key, config_value in configs.items():
                description = descriptions.get(config_key)
                if await self.set_config(config_key, config_value, description):
                    success_count += 1
            
            self.logger.info(f"批量设置配置完成: {success_count}/{len(configs)}")
            return success_count == len(configs)
            
        except Exception as e:
            self.logger.error(f"批量设置配置失败: {e}")
            return False
    
    async def refresh_cache(self) -> bool:
        """刷新配置缓存"""
        try:
            self._config_cache.clear()
            self._cache_timestamp = None
            await self.get_all_configs(use_cache=False)
            self.logger.info("配置缓存刷新成功")
            return True
        except Exception as e:
            self.logger.error(f"刷新配置缓存失败: {e}")
            return False
    
    async def export_configs(self) -> Dict[str, Any]:
        """导出所有配置（包含元数据）"""
        try:
            configs = await self.config_repo.find_many()
            
            exported = {
                'export_time': datetime.utcnow().isoformat(),
                'total_count': len(configs),
                'configs': []
            }
            
            for config in configs:
                exported['configs'].append({
                    'key': config['config_key'],
                    'value': config['config_value'],
                    'description': config.get('description'),
                    'created_at': config.get('created_at'),
                    'updated_at': config.get('updated_at')
                })
            
            return exported
            
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            return {'export_time': datetime.utcnow().isoformat(), 'total_count': 0, 'configs': []}
    
    def _convert_config_value(self, value_str: str, default_value: Any) -> Any:
        """根据默认值类型转换配置值"""
        if default_value is None:
            return value_str
        
        try:
            if isinstance(default_value, bool):
                return value_str.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(default_value, int):
                return int(value_str)
            elif isinstance(default_value, float):
                return float(value_str)
            elif isinstance(default_value, (dict, list)):
                return json.loads(value_str)
            else:
                return value_str
        except (ValueError, json.JSONDecodeError):
            self.logger.warning(f"配置值类型转换失败，使用默认值: {value_str} -> {default_value}")
            return default_value
    
    async def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self._cache_timestamp:
            return False
        
        elapsed = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return elapsed < self.cache_ttl_seconds
    
    # 常用配置的便捷方法
    async def get_app_version(self) -> str:
        """获取应用版本"""
        return await self.get_config_str('app_version', '1.0.0')
    
    async def get_maintenance_mode(self) -> bool:
        """获取维护模式状态"""
        return await self.get_config_bool('maintenance_mode', False)
    
    async def set_maintenance_mode(self, enabled: bool, message: str = None) -> bool:
        """设置维护模式"""
        result = await self.set_config('maintenance_mode', enabled, '系统维护模式开关')
        if result and message:
            await self.set_config('maintenance_message', message, '维护模式提示信息')
        return result
    
    async def get_feature_flags(self) -> Dict[str, bool]:
        """获取功能开关配置"""
        try:
            all_configs = await self.get_all_configs()
            feature_flags = {}
            
            for key, value in all_configs.items():
                if key.startswith('feature_'):
                    feature_name = key[8:]  # 移除 'feature_' 前缀
                    feature_flags[feature_name] = value.lower() in ('true', '1', 'yes', 'on')
            
            return feature_flags
            
        except Exception as e:
            self.logger.error(f"获取功能开关失败: {e}")
            return {}
    
    async def set_feature_flag(self, feature_name: str, enabled: bool) -> bool:
        """设置功能开关"""
        config_key = f'feature_{feature_name}'
        return await self.set_config(config_key, enabled, f'功能开关: {feature_name}')