import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class SnapshotRepositoryV2:
    """基于本地 JSON 的快照仓储（双文件：users.json + snapshots.json）。

    - users.json: [{ user_id, snapshot_ids: [...], created_at }]
    - snapshots.json: [{ snapshot_id, user_id, name, model, system_prompt, messages, created_at }]
    """

    def __init__(self, base_dir: str = "data/snapshots"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.users_file = self.base_dir / "users.json"
        self.snaps_file = self.base_dir / "snapshots.json"
        # 确保文件存在
        if not self.users_file.exists():
            self._atomic_write(self.users_file, [])
        if not self.snaps_file.exists():
            self._atomic_write(self.snaps_file, [])

    # -------------------------
    # 低级IO
    # -------------------------
    def _read_list(self, file_path: Path) -> List[Dict[str, Any]]:
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _atomic_write(self, file_path: Path, data: List[Dict[str, Any]]):
        tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, file_path)

    # -------------------------
    # 高级API
    # -------------------------
    def insert(self, snapshot: Dict[str, Any]) -> bool:
        """保存快照：写 snapshots.json，并在 users.json 关联 snapshot_id。"""
        user_id = snapshot.get("user_id")
        snapshot_id = snapshot.get("snapshot_id")
        if not user_id or not snapshot_id:
            return False

        # 1) 写入 snapshots.json（追加）
        snaps = self._read_list(self.snaps_file)
        snaps.append(snapshot)
        self._atomic_write(self.snaps_file, snaps)

        # 2) 更新 users.json 的 snapshot_ids
        users = self._read_list(self.users_file)
        user = next((u for u in users if u.get("user_id") == user_id), None)
        if not user:
            user = {"user_id": user_id, "snapshot_ids": [], "created_at": snapshot.get("created_at")}
            users.append(user)
        if snapshot_id not in user["snapshot_ids"]:
            user["snapshot_ids"].append(snapshot_id)
        self._atomic_write(self.users_file, users)
        return True

    def list_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """根据 users.json 中的 snapshot_ids 拉取对应 snapshots。"""
        users = self._read_list(self.users_file)
        user = next((u for u in users if u.get("user_id") == user_id), None)
        if not user:
            return []
        snapshot_ids = set(user.get("snapshot_ids", []))
        if not snapshot_ids:
            return []
        snaps = self._read_list(self.snaps_file)
        return [s for s in snaps if s.get("snapshot_id") in snapshot_ids]

    def get(self, user_id: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """兼容旧签名：校验 snapshot 属于该 user，并返回对象。"""
        users = self._read_list(self.users_file)
        user = next((u for u in users if u.get("user_id") == user_id), None)
        if not user:
            return None
        if snapshot_id not in set(user.get("snapshot_ids", [])):
            return None
        snaps = self._read_list(self.snaps_file)
        return next((s for s in snaps if s.get("snapshot_id") == snapshot_id), None)

    def get_by_id(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        snaps = self._read_list(self.snaps_file)
        return next((s for s in snaps if s.get("snapshot_id") == snapshot_id), None)


