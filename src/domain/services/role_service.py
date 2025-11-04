import json
from pathlib import Path

class RoleService:
    def __init__(self, role_file: str = "scripts/publisher/role_library.json"):
        self.role_file = Path(role_file)
        if not self.role_file.exists():
            raise FileNotFoundError(f"角色库文件未找到: {self.role_file}")
        self.roles = json.loads(self.role_file.read_text(encoding="utf-8"))

    def get_role_by_id(self, role_id: str):
        """根据 role_id 获取角色信息"""
        return next((r for r in self.roles if r["role_id"] == role_id), None)

    def list_roles(self):
        """返回所有角色"""
        return self.roles

# ✅ 全局唯一实例
role_service = RoleService()