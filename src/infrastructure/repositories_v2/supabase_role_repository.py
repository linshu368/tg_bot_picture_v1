"""
Supabase角色仓库
负责从Supabase数据库读取角色数据
"""

import logging
from typing import List, Dict, Any, Optional


class SupabaseRoleRepository:
    """
    基于Supabase的角色仓库
    
    数据表：role_library
    字段：role_id, name, avatar, tags, summary, system_prompt, 
          history, model, deeplink, created_at, post_link
    
    注意：history 字段包含预置对话，格式为：[{"role": "assistant", "content": "预置对话内容"}]
    """
    
    def __init__(self, supabase_manager):
        """
        初始化角色仓库
        
        Args:
            supabase_manager: Supabase管理器实例
        """
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        self.table_name = "role_library"
    
    def get_role_by_id(self, role_id: str) -> Optional[Dict[str, Any]]:
        """
        根据角色ID获取角色信息
        
        Args:
            role_id: 角色ID
            
        Returns:
            角色数据字典，如果不存在则返回None
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 从Supabase查询角色
            response = client.table(self.table_name).select("*").eq("role_id", role_id).execute()
            
            if response.data and len(response.data) > 0:
                role = response.data[0]
                self.logger.debug(f"✅ 获取角色成功: role_id={role_id}, name={role.get('name')}")
                return role
            else:
                self.logger.warning(f"⚠️ 角色不存在: role_id={role_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 获取角色失败: role_id={role_id}, error={str(e)}")
            return None
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """
        获取所有角色列表
        
        Returns:
            角色列表
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 从Supabase查询所有角色
            response = client.table(self.table_name).select("*").execute()
            
            if response.data:
                self.logger.info(f"✅ 获取角色列表成功: 共 {len(response.data)} 个角色")
                return response.data
            else:
                self.logger.warning("⚠️ 角色列表为空")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ 获取角色列表失败: error={str(e)}")
            return []
    
    def list_roles_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """
        根据标签筛选角色（可选功能）
        
        Args:
            tags: 标签列表
            
        Returns:
            匹配的角色列表
        """
        try:
            # 获取所有角色
            all_roles = self.list_roles()
            
            # 筛选包含指定标签的角色
            filtered_roles = []
            for role in all_roles:
                role_tags = role.get("tags", [])
                if isinstance(role_tags, list) and any(tag in role_tags for tag in tags):
                    filtered_roles.append(role)
            
            self.logger.info(f"✅ 标签筛选完成: tags={tags}, 匹配 {len(filtered_roles)} 个角色")
            return filtered_roles
            
        except Exception as e:
            self.logger.error(f"❌ 标签筛选失败: tags={tags}, error={str(e)}")
            return []

