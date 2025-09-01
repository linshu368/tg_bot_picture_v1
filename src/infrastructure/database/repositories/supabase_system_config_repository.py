"""
Supabase系统配置Repository
负责系统配置数据的CRUD操作 - Supabase版本
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .supabase_base_repository import SupabaseBaseRepository


class SupabaseSystemConfigRepository(SupabaseBaseRepository[Dict[str, Any]]):
    """Supabase系统配置数据访问层"""
    
    def __init__(self, supabase_manager):
        super().__init__(supabase_manager, 'system_config')
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新配置项"""
        try:
            client = self.get_client()
            
            # 设置默认值
            config_data = {
                'config_key': data['config_key'],
                'config_value': data['config_value'],
                'description': data.get('description'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 合并传入的数据
            config_data.update({k: v for k, v in data.items() if k not in ['id']})
            
            # 准备插入数据
            prepared_data = self._prepare_data_for_insert(config_data)
            
            # 插入数据
            result = client.table(self.table_name).insert(prepared_data).execute()
            
            if result.data and len(result.data) > 0:
                created_config = result.data[0]
                self.logger.info(f"配置项创建成功: key={data['config_key']}")
                return created_config
            else:
                raise Exception("插入配置项失败，未返回数据")
                
        except Exception as e:
            self.logger.error(f"创建配置项失败: {e}")
            raise
    
    async def get_by_id(self, config_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取配置项"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('id', config_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取配置项失败: {e}")
            return None
    
    async def get_by_key(self, config_key: str) -> Optional[Dict[str, Any]]:
        """根据配置键获取配置项"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).select('*').eq('config_key', config_key).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"根据配置键获取配置项失败: {e}")
            return None
    
    async def update(self, config_id: int, data: Dict[str, Any]) -> bool:
        """更新配置项"""
        try:
            client = self.get_client()
            
            # 准备更新数据
            update_data = self._prepare_data_for_update(data)
            
            # 执行更新
            result = client.table(self.table_name).update(update_data).eq('id', config_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"配置项更新成功: config_id={config_id}")
                return True
            else:
                self.logger.warning(f"配置项更新失败: config_id={config_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新配置项失败: {e}")
            return False
    
    async def delete(self, config_id: int) -> bool:
        """删除配置项"""
        try:
            client = self.get_client()
            result = client.table(self.table_name).delete().eq('id', config_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"配置项删除成功: config_id={config_id}")
                return True
            else:
                self.logger.warning(f"配置项删除失败: config_id={config_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除配置项失败: {e}")
            return False
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个配置项"""
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
            self.logger.error(f"查找配置项失败: {e}")
            return None
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查找多个配置项"""
        try:
            client = self.get_client()
            query = client.table(self.table_name).select('*')
            query = self._build_supabase_filters(query, conditions)
            query = query.order('config_key', desc=False)
            
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
            self.logger.error(f"查找多个配置项失败: {e}")
            return []
    
    async def set_config(self, config_key: str, config_value: str, description: str = None) -> bool:
        """设置配置项（如果存在则更新，不存在则创建）"""
        try:
            # 检查配置项是否存在
            existing_config = await self.get_by_key(config_key)
            
            if existing_config:
                # 更新现有配置
                update_data = {'config_value': config_value}
                if description:
                    update_data['description'] = description
                
                result = await self.update(existing_config['id'], update_data)
                self.logger.info(f"配置项更新: {config_key} = {config_value}")
                return result
            else:
                # 创建新配置
                config_data = {
                    'config_key': config_key,
                    'config_value': config_value,
                    'description': description
                }
                
                await self.create(config_data)
                self.logger.info(f"配置项创建: {config_key} = {config_value}")
                return True
                
        except Exception as e:
            self.logger.error(f"设置配置项失败: {e}")
            return False
    
    async def get_config_value(self, config_key: str, default_value: str = None) -> Optional[str]:
        """获取配置值"""
        try:
            config = await self.get_by_key(config_key)
            if config:
                return config['config_value']
            return default_value
            
        except Exception as e:
            self.logger.error(f"获取配置值失败: {e}")
            return default_value
    
    async def get_config_value_as_int(self, config_key: str, default_value: int = 0) -> int:
        """获取配置值（整数类型）"""
        try:
            value = await self.get_config_value(config_key)
            if value:
                return int(value)
            return default_value
            
        except (ValueError, TypeError) as e:
            self.logger.warning(f"配置值转换为整数失败: {config_key}, {e}")
            return default_value
    
    async def get_config_value_as_bool(self, config_key: str, default_value: bool = False) -> bool:
        """获取配置值（布尔类型）"""
        try:
            value = await self.get_config_value(config_key)
            if value:
                return value.lower() in ('true', '1', 'yes', 'on')
            return default_value
            
        except Exception as e:
            self.logger.warning(f"配置值转换为布尔失败: {config_key}, {e}")
            return default_value
    
    async def get_all_configs(self) -> Dict[str, str]:
        """获取所有配置项（返回键值对字典）"""
        try:
            configs = await self.find_many()
            return {config['config_key']: config['config_value'] for config in configs}
            
        except Exception as e:
            self.logger.error(f"获取所有配置失败: {e}")
            return {}
    
    async def delete_by_key(self, config_key: str) -> bool:
        """根据配置键删除配置项"""
        try:
            config = await self.get_by_key(config_key)
            if config:
                return await self.delete(config['id'])
            return False
            
        except Exception as e:
            self.logger.error(f"根据键删除配置失败: {e}")
            return False
    
    async def bulk_set_configs(self, configs: Dict[str, str]) -> bool:
        """批量设置配置项"""
        try:
            success_count = 0
            for config_key, config_value in configs.items():
                if await self.set_config(config_key, config_value):
                    success_count += 1
            
            self.logger.info(f"批量设置配置完成: {success_count}/{len(configs)}")
            return success_count == len(configs)
            
        except Exception as e:
            self.logger.error(f"批量设置配置失败: {e}")
            return False