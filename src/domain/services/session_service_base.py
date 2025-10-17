"""
轻量版 SessionService
- MVP 阶段使用：仅用内存字典存储，不依赖数据库或 Repository。
- 保持接口方法名和类名一致，未来可直接替换为成熟版（基于 SessionCompositeRepository）。
"""

import uuid
import logging
from typing import Dict, Any, Optional


class SessionService:
    """轻量版会话服务：MVP 验证阶段"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 内存存储：user_id -> session_dict
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self.logger.info("🟢 SessionService 初始化完成 - 使用内存存储")

    def generate_session_id(self) -> str:
        """生成唯一的会话ID"""
        return f"sess_{uuid.uuid4().hex[:8]}"

    async def create_session(self, user_id: str, role_id: str = None) -> Dict[str, Any]:
        """创建新会话"""
        session_id = self.generate_session_id()
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "role_id": role_id,
            "history": [],
        }
        self._sessions[user_id] = session
        self.logger.info(f"✅ 新建会话: user_id={user_id}, session_id={session_id}, role_id={role_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """根据 session_id 查找会话"""
        for sess in self._sessions.values():
            if sess["session_id"] == session_id:
                return sess
        return None

    async def get_or_create_session(self, user_id: str) -> Dict[str, Any]:
        """获取或创建会话"""
        if user_id not in self._sessions:
            return await self.create_session(user_id)
        return self._sessions[user_id]

    async def new_session(self, user_id: str, role_id: str = None) -> Dict[str, Any]:
        """强制开启新会话（替换旧会话）"""
        return await self.create_session(user_id, role_id)

    async def get_session_role_id(self, session_id: str) -> Optional[str]:
        """根据 session_id 获取绑定的角色ID"""
        session = await self.get_session(session_id)
        return session.get("role_id") if session else None

    async def set_session_role_id(self, session_id: str, role_id: str) -> bool:
        """为指定会话设置角色ID"""
        session = await self.get_session(session_id)
        if session:
            session["role_id"] = role_id
            self.logger.info(f"✅ 更新会话角色: session_id={session_id}, role_id={role_id}")
            return True
        self.logger.warning(f"⚠️ 会话不存在，无法设置角色: session_id={session_id}")
        return False

    async def create_session_with_role(self, user_id: str, role_id: str) -> Dict[str, Any]:
        """创建绑定特定角色的新会话"""
        return await self.create_session(user_id, role_id)



# ✅ 全局唯一实例 
session_service = SessionService()
