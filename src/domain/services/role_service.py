"""
角色服务
负责角色数据的查询和管理
"""

import logging
from typing import Dict, Any, List, Optional


class RoleService:
    """
    角色服务 - 基于 Supabase Repository
    提供角色查询、列表等功能
    """
    
    def __init__(self, role_repository):
        """
        初始化角色服务
        
        Args:
            role_repository: 角色仓库实例（SupabaseRoleRepository）
        """
        self.logger = logging.getLogger(__name__)
        self.repository = role_repository
        self.logger.info("✅ RoleService 初始化完成")
    
    def get_role_by_id(self, role_id: str) -> Optional[Dict[str, Any]]:
        """
        根据角色ID获取角色信息
        
        Args:
            role_id: 角色ID
            
        Returns:
            角色数据字典，如果不存在则返回None
        """
        return self.repository.get_role_by_id(role_id)
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """
        获取所有角色列表
        
        Returns:
            角色列表
        """
        return self.repository.list_roles()
    
    def list_roles_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """
        根据标签筛选角色
        
        Args:
            tags: 标签列表
            
        Returns:
            匹配的角色列表
        """
        return self.repository.list_roles_by_tags(tags)


# ✅ 全局唯一实例（临时占位，实际使用时应通过容器获取）
# 注意：这个实例在初始化时会报错，因为没有提供 repository
# 在应用启动时，应该通过容器创建并替换这个实例
role_service = None  # 将在容器中初始化