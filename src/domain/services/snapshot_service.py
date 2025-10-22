import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.domain.services.message_service import message_service
from src.domain.services.session_service_base import session_service
from src.domain.services.role_service import role_service
from src.infrastructure.repositories_v2.single.snapshot_repository_v2 import SnapshotRepositoryV2


class SnapshotService:
    """MVP 快照服务：保存当前会话上下文到本地 JSON 文件。

    约束：
    - 仅保存静态快照，不支持编辑/删除/合并
    - name 为空时，自动生成：{角色名或'对话'}_{YYYYMMDD_HHMMSS}
    - model/system_prompt 优先取自会话绑定的角色
    """

    def __init__(self):
        self.repo = SnapshotRepositoryV2()

    async def save_snapshot(self, user_id: str, session_id: str, name: Optional[str] = None) -> str:
        # 1. 读取会话历史（实际交互内容）
        history = message_service.get_history(session_id) or []
        session_messages: List[Dict[str, str]] = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            for m in history
        ]

        # 2. 获取会话角色 → 角色配置（用于 model/system_prompt 与命名）
        role_id = await session_service.get_session_role_id(session_id)
        role_data: Optional[Dict[str, Any]] = role_service.get_role_by_id(role_id) if role_id else None

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

        # 3. 生成名称
        if not name or not name.strip():
            role_name = role_data.get("name") if role_data else "对话"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{role_name}_{ts}"

        # 4. 生成快照并写入
        snapshot_id = uuid.uuid4().hex
        snapshot: Dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "user_id": user_id,
            "name": name,
            "model": model or "",
            "system_prompt": system_prompt or "",
            # 合并顺序：角色预置历史在前 → 实际会话历史在后
            "messages": [*role_history, *session_messages],
            "created_at": datetime.utcnow().isoformat(),
        }

        self.repo.insert(snapshot)
        return snapshot_id

    async def list_snapshots(self, user_id: str) -> List[Dict[str, Any]]:
        items = self.repo.list_by_user(user_id)
        # 倒序：最新在前
        try:
            return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)
        except Exception:
            return items


# ✅ 全局唯一实例
snapshot_service = SnapshotService()


