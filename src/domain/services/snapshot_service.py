"""
快照服务
负责会话快照的保存、查询和管理
"""

import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


class SnapshotService:
    """
    快照服务 - 基于 Supabase Repository
    
    功能：
    - 保存当前会话上下文为快照
    - 查询用户的快照列表
    - 删除快照
    - 获取特定快照
    """

    def __init__(self, snapshot_repository, message_service=None, session_service=None, role_service=None):
        """
        初始化快照服务
        
        Args:
            snapshot_repository: 快照仓库实例（SupabaseSnapshotRepository）
            message_service: 消息服务实例（通过容器注入）
            session_service: 会话服务实例（通过容器注入）
            role_service: 角色服务实例（通过容器注入）
        """
        self.logger = logging.getLogger(__name__)
        self.repository = snapshot_repository
        self.message_service = message_service
        self.session_service = session_service
        self.role_service = role_service
        self.logger.info("✅ SnapshotService 初始化完成")

    async def save_snapshot(self, user_id: str, session_id: str, user_title: Optional[str] = None) -> str:
        # 1. 读取会话历史（实际交互内容）
        history = await self.message_service.get_history(session_id) or []
        session_messages: List[Dict[str, str]] = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            for m in history
        ]

        # 2. 获取会话角色 → 角色配置（用于 model/system_prompt 与命名）
        role_id = await self.session_service.get_session_role_id(session_id)
        role_data: Optional[Dict[str, Any]] = self.role_service.get_role_by_id(role_id) if role_id else None

        model = role_data.get("model") if role_data else ""
        system_prompt = role_data.get("system_prompt") if role_data else ""
        role_history = []
        if role_data:
            # 角色预置 few-shot 样例，合并到 messages 里
            try:
                rh = role_data.get("history") or []
                # 仅保留必要字段
                role_history = [
                    {"role": h.get("role", ""), "content": h.get("content", "")}
                    for h in rh if isinstance(h, dict)
                ]
            except Exception:
                role_history = []

        # 3. 生成展示名称：{YYYYMMDD_HHMMSS}_{用户命名或未命名}_{角色名}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = (user_title or "").strip() or "未命名"
        role_name = (role_data.get("name") if role_data else "未知角色") or "未知角色"
        display_name = f"{ts}_{safe_title}_{role_name}"

        # 4. 生成快照并写入
        snapshot_id = uuid.uuid4().hex
        snapshot: Dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "user_id": user_id,
            "role_id": role_id or "",
            "name": display_name,
            "model": model or "",
            "system_prompt": system_prompt or "",
            # 合并顺序：角色预置历史在前 → 实际会话历史在后
            "messages": [*role_history, *session_messages],
            "created_at": datetime.utcnow().isoformat(),
        }

        self.repository.insert(snapshot)
        return snapshot_id

    async def list_snapshots(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有快照列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            快照列表，按创建时间倒序
        """
        items = self.repository.list_by_user(user_id)
        # 倒序：最新在前
        try:
            return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)
        except Exception:
            return items

    async def delete_snapshot(self, user_id: str, snapshot_id: str) -> bool:
        """
        删除快照
        
        Args:
            user_id: 用户ID
            snapshot_id: 快照ID
            
        Returns:
            是否删除成功
        """
        return self.repository.delete(user_id=user_id, snapshot_id=snapshot_id)

    async def get_snapshot(self, user_id: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        获取特定快照
        
        Args:
            user_id: 用户ID
            snapshot_id: 快照ID
            
        Returns:
            快照数据，如果不存在或无权访问则返回None
        """
        return self.repository.get(user_id=user_id, snapshot_id=snapshot_id)


# ✅ 全局唯一实例（临时占位，实际使用时应通过容器获取）
# 注意：这个实例在初始化时会报错，因为没有提供 repository
# 在应用启动时，应该通过容器创建并替换这个实例
snapshot_service = None  # 将在容器中初始化


