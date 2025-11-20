"""
轻量版 SessionService
- MVP 阶段使用：仅用内存字典存储，不依赖数据库或 Repository。
- 保持接口方法名和类名一致，未来可直接替换为成熟版（基于 SessionCompositeRepository）。
"""

import uuid
import logging
from typing import Dict, Any, Optional


class SessionService:
    """轻量版会话服务：MVP 验证阶段
    
    - 默认使用内存存储（重启丢失）
    - 若注入 redis_store（UpstashSessionStore），则：
      - 使用 sess:current:{user_id} 作为“书签”保存当前 session_id
      - 使用 sess:data:{session_id} 保存会话元信息（user_id/role_id/created_at）
      - 重启后可完整恢复 session_id 与 role_id
    """
 
    def __init__(self, redis_store=None):
        self.logger = logging.getLogger(__name__)
        # 内存存储：user_id -> session_dict
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self.redis_store = redis_store
        mode = "Redis+内存回退" if self.redis_store else "仅内存"
        self.logger.info(f"🟢 SessionService 初始化完成 - 模式: {mode}")

    def generate_session_id(self) -> str:
        """生成唯一的会话ID"""
        return f"sess_{uuid.uuid4().hex[:8]}"

    async def create_session(self, user_id: str, role_id: str = None) -> Dict[str, Any]:
        """创建新会话并持久化书签/元信息（若启用 Redis）"""
        session_id = self.generate_session_id()
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "role_id": role_id,
            "history": [],
        }
        # 内存写入
        self._sessions[user_id] = session
        # Redis 写入
        if self.redis_store:
            try:
                await self.redis_store.set_current_session_id(str(user_id), session_id)
                # 同步写入 last 指针，作为冗余索引
                try:
                    await self.redis_store.set_last_session_id(str(user_id), session_id)
                except Exception as _e:
                    self.logger.debug(f"写入 last 会话指针失败: user_id={user_id}, err={_e}")
                await self.redis_store.set_session_data(session_id, {
                    "session_id": session_id,
                    "user_id": str(user_id),
                    "role_id": role_id,
                    "created_at": uuid.uuid4().hex  # 简单占位，可替换为时间戳
                })
            except Exception as e:
                self.logger.debug(f"持久化会话失败: user_id={user_id}, err={e}")
        self.logger.info(f"✅ 新建会话: user_id={user_id}, session_id={session_id}, role_id={role_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """根据 session_id 查找会话"""
        # Redis 优先
        if self.redis_store:
            try:
                data = await self.redis_store.get_session_data(session_id)
                self.logger.info(f"get_session: 从 Redis 获取元信息 session_id={session_id}, data={data}")
                if data and isinstance(data, dict):
                    # 兼容嵌套 {'value': {...}} 的旧数据
                    if "session_id" not in data and "value" in data and isinstance(data.get("value"), dict):
                        data = data.get("value")
                    # 同步到内存（便于现有调用）
                    user_id = str(data.get("user_id")) if data.get("user_id") is not None else None
                    role_id = data.get("role_id")
                    if user_id:
                        sess = {
                            "session_id": session_id,
                            "user_id": user_id,
                            "role_id": role_id,
                            "history": [],
                        }
                        self._sessions[user_id] = sess
                        return sess
            except Exception as e:
                self.logger.debug(f"Redis 获取会话失败: session_id={session_id}, err={e}")
        # 内存查找
        for sess in self._sessions.values():
            if sess["session_id"] == session_id:
                return sess
        return None

    async def get_or_create_session(self, user_id: str) -> Dict[str, Any]:
        """获取或创建会话：若有 Redis 书签则复用原 session_id"""
        user_id_str = str(user_id)
        # 先尝试 Redis 书签
        if self.redis_store:
            self.logger.debug(f"get_or_create_session: 开始读取书签 user_id={user_id_str}")
            try:
                current_sess_id = await self.redis_store.get_current_session_id(user_id_str)
                self.logger.debug(f"get_or_create_session: current={current_sess_id}")
                if not current_sess_id:
                    self.logger.info(f"ℹ️ get_or_create_session: 未命中 current 书签 user_id={user_id_str}")
                if current_sess_id:
                    # 尝试读取元信息，短暂重试与自愈
                    data = await self.redis_store.get_session_data(current_sess_id)
                    self.logger.info(f"get_or_create_session: data(first)={data}")
                    if not data:
                        try:
                            import asyncio as _asyncio
                            await _asyncio.sleep(0.05)
                        except Exception:
                            pass
                        data = await self.redis_store.get_session_data(current_sess_id)
                        self.logger.info(f"get_or_create_session: data(second)={data}")
                    if data and isinstance(data, dict):
                        # 兼容嵌套 {'value': {...}} 的旧数据
                        if "session_id" not in data and "value" in data and isinstance(data.get("value"), dict):
                            data = data.get("value")
                        # 同步到内存后直接返回
                        role_id = data.get("role_id")
                        sess = {
                            "session_id": current_sess_id,
                            "user_id": user_id_str,
                            "role_id": role_id,
                            "history": [],
                        }
                        self._sessions[user_id_str] = sess
                        self.logger.info(f"✅ 命中 current 并返回: user_id={user_id_str}, session_id={current_sess_id}, role_id={role_id}")
                        return sess
                    else:
                        # 自愈：补写最小元信息，避免落回新建会话
                        try:
                            await self.redis_store.set_session_data(current_sess_id, {
                                "session_id": current_sess_id,
                                "user_id": user_id_str,
                                "role_id": None
                            })
                            self.logger.info(f"🧷 自愈: 回写最小元信息成功 user_id={user_id_str}, session_id={current_sess_id}")
                        except Exception as _e:
                            self.logger.debug(f"回写最小元信息失败: session_id={current_sess_id}, err={_e}")
                        # 返回自构会话对象
                        sess = {
                            "session_id": current_sess_id,
                            "user_id": user_id_str,
                            "role_id": None,
                            "history": [],
                        }
                        self._sessions[user_id_str] = sess
                        self.logger.info(f"✅ 命中 current(无data，自愈) 并返回: user_id={user_id_str}, session_id={current_sess_id}")
                        return sess
                # current 缺失则尝试 last，并提升为 current
                last_sess_id = await self.redis_store.get_last_session_id(user_id_str)
                self.logger.debug(f"get_or_create_session: last={last_sess_id}")
                if not last_sess_id:
                    self.logger.info(f"ℹ️ get_or_create_session: 未命中 last 书签 user_id={user_id_str}")
                if last_sess_id:
                    try:
                        await self.redis_store.set_current_session_id(user_id_str, last_sess_id)
                        self.logger.info(f"🧷 提升 last 为 current: user_id={user_id_str}, session_id={last_sess_id}")
                    except Exception as _e:
                        self.logger.debug(f"提升 last 为 current 失败: user_id={user_id_str}, err={_e}")
                    data = await self.redis_store.get_session_data(last_sess_id)
                    self.logger.debug(f"get_or_create_session: last.data={data}")
                    if not data:
                        try:
                            await self.redis_store.set_session_data(last_sess_id, {
                                "session_id": last_sess_id,
                                "user_id": user_id_str,
                                "role_id": None
                            })
                            data = {"role_id": None}
                            self.logger.info(f"🧷 last 自愈: 回写最小元信息成功 user_id={user_id_str}, session_id={last_sess_id}")
                        except Exception as _e:
                            self.logger.debug(f"回写 last 会话元信息失败: session_id={last_sess_id}, err={_e}")
                            data = {"role_id": None}
                    elif isinstance(data, dict) and "session_id" not in data and "value" in data and isinstance(data.get("value"), dict):
                        data = data.get("value")
                    sess = {
                        "session_id": last_sess_id,
                        "user_id": user_id_str,
                        "role_id": data.get("role_id"),
                        "history": [],
                    }
                    self._sessions[user_id_str] = sess
                    self.logger.info(f"✅ 命中 last 并返回: user_id={user_id_str}, session_id={last_sess_id}")
                    return sess
            except Exception as e:
                self.logger.debug(f"读取 Redis 书签失败: user_id={user_id}, err={e}")
        # 再看内存
        if user_id_str in self._sessions:
            return self._sessions[user_id_str]
        self.logger.info(f"⚠️ get_or_create_session: 未命中 current/last/内存，准备新建: user_id={user_id_str}")
        # 都没有，则创建新会话并写入书签
        return await self.create_session(user_id_str)

    async def new_session(self, user_id: str, role_id: str = None) -> Dict[str, Any]:
        """强制开启新会话（替换旧会话），并更新 Redis 书签"""
        return await self.create_session(str(user_id), role_id)

    async def get_session_role_id(self, session_id: str) -> Optional[str]:
        """根据 session_id 获取绑定的角色ID（Redis 优先）"""
        if self.redis_store:
            try:
                data = await self.redis_store.get_session_data(session_id)
                if data:
                    return data.get("role_id")
            except Exception as e:
                self.logger.debug(f"Redis 获取角色失败: session_id={session_id}, err={e}")
        session = await self.get_session(session_id)
        return session.get("role_id") if session else None

    async def set_session_role_id(self, session_id: str, role_id: str) -> bool:
        """为指定会话设置角色ID（同时更新 Redis 元信息）"""
        session = await self.get_session(session_id)
        if session:
            session["role_id"] = role_id
            if self.redis_store:
                try:
                    data = await self.redis_store.get_session_data(session_id) or {}
                    data["session_id"] = session_id
                    data["user_id"] = str(session.get("user_id"))
                    data["role_id"] = role_id
                    await self.redis_store.set_session_data(session_id, data)
                except Exception as e:
                    self.logger.debug(f"Redis 更新角色失败: session_id={session_id}, err={e}")
            self.logger.info(f"✅ 更新会话角色: session_id={session_id}, role_id={role_id}")
            return True
        self.logger.warning(f"⚠️ 会话不存在，无法设置角色: session_id={session_id}")
        return False

    async def create_session_with_role(self, user_id: str, role_id: str) -> Dict[str, Any]:
        """创建绑定特定角色的新会话"""
        return await self.create_session(user_id, role_id)



# ✅ 全局唯一实例 
session_service = None
