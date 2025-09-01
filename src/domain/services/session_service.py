"""
会话服务
负责用户会话管理和会话记录的核心业务逻辑

修改：已迁移为仅依赖 SessionCompositeRepository，移除旧分支与并行验证
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class SessionService:
    """会话业务服务（已迁移：仅使用SessionCompositeRepository）"""
    
    # 修改：精简构造，仅保留组合仓库
    # 目的：服务层只编排业务，跨表与事务下沉到组合仓库
    def __init__(self, session_repo=None):
        if not session_repo:
            raise ValueError("必须提供session_repo")
        self.logger = logging.getLogger(__name__)
        self.session_repo = session_repo
        self.logger.info("🔧 SessionService初始化完成 - 使用SessionCompositeRepository")
    
    def generate_session_id(self) -> str:
        """生成唯一的会话ID"""
        return f"sess_{uuid.uuid4().hex[:16]}"
    
    async def create_session(self, user_id: int, expires_hours: int = 24) -> Optional[Dict[str, Any]]:
        """创建新会话"""
        try:
            session_id = self.generate_session_id()
            session_data = {
                'started_at': datetime.utcnow().isoformat(),
                'message_count_user': 0
            }
            result = await self.session_repo.create_session(
                user_id=user_id,
                session_id=session_id,
                session_data=session_data
            )
            if result and result.get('success'):
                session = result.get('data', {})
                self.logger.info(f"会话创建成功: user_id={user_id}, session_id={session_id}")
                return session
            else:
                self.logger.error(f"SessionCompositeRepository创建会话失败: {result.get('message', 'Unknown error')}")
                return None
            
        except Exception as e:
            self.logger.error(f"创建会话失败: {e}")
            return None
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            result = await self.session_repo.get_session_info(session_id)
            return result.get('data') if result and result.get('success') else None
        except Exception as e:
            self.logger.error(f"获取会话失败: {e}")
            return None
    
    async def get_or_create_session(self, user_id: int, session_id: str = None) -> Dict[str, Any]:
        """获取或创建会话"""
        try:
            # 如果提供了session_id，尝试获取现有会话
            if session_id:
                session = await self.get_session(session_id)
                if session and not await self._is_session_expired(session):
                    await self._update_session_activity(session_id)
                    return session
            
            # 创建新会话
            return await self.create_session(user_id)
            
        except Exception as e:
            self.logger.error(f"获取或创建会话失败: {e}")
            return await self.create_session(user_id)
    
    async def update_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """更新会话数据"""
        try:
            # 修改：调用组合仓库的兼容方法（内部映射为活动更新/计数增量）
            return await self.session_repo.update_session_data(session_id, data)
        except Exception as e:
            self.logger.error(f"更新会话数据失败: {e}")
            return False
    
    async def end_session(self, session_id: str, summary: str = None) -> bool:
        """结束会话"""
        try:
            result = await self.session_repo.end_session(
                session_id=session_id,
                summary=summary
            )
            if result and result.get('success'):
                self.logger.info(f"会话结束成功: session_id={session_id}")
                return True
            else:
                self.logger.error(f"SessionCompositeRepository结束会话失败: {result.get('message', 'Unknown error')}")
                return False
            
        except Exception as e:
            self.logger.error(f"结束会话失败: {e}")
            return False
    
    async def increment_message_count(self, session_id: str) -> bool:
        """增加消息计数"""
        try:
            result = await self.session_repo.update_session_activity(
                session_id=session_id,
                message_count=1,
                update_stats=True
            )
            return result and result.get('success', False)
        except Exception as e:
            self.logger.error(f"增加消息计数失败: {e}")
            return False
    
    async def get_user_sessions(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户的会话列表"""
        try:
            result = await self.session_repo.get_user_sessions(
                user_id=user_id,
                include_records=True,
                limit=limit
            )
            return result.get('data', []) if result and result.get('success') else []
        except Exception as e:
            self.logger.error(f"获取用户会话列表失败: {e}")
            return []
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """获取当前活跃的会话"""
        try:
            result = await self.session_repo.get_active_sessions()
            return result.get('data', []) if result and result.get('success') else []
        except Exception as e:
            self.logger.error(f"获取活跃会话失败: {e}")
            return []
    
    async def cleanup_expired_sessions(self) -> int:
        """清理过期的会话"""
        try:
            # 修改：调用组合仓库兼容别名，默认清理90天以前记录
            return await self.session_repo.cleanup_expired_sessions()
        except Exception as e:
            self.logger.error(f"清理过期会话失败: {e}")
            return 0
    
    async def get_session_statistics(self, user_id: int = None, days: int = 7) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            if user_id:
                result = await self.session_repo.get_user_session_stats(
                    user_id=user_id,
                    days=days
                )
                return result.get('data', {}) if result and result.get('success') else {}
            return {}
            
        except Exception as e:
            self.logger.error(f"获取会话统计失败: {e}")
            return {
                'total_sessions': 0,
                'completed_sessions': 0,
                'active_sessions': 0,
                'total_messages': 0,
                'avg_duration_sec': 0,
                'avg_messages_per_session': 0
            }
    
    async def _is_session_expired(self, session: Dict[str, Any]) -> bool:
        """检查会话是否过期（V2：ended_at 或 空闲超时10分钟）"""
        try:
            # 已结束直接过期
            if session.get('ended_at'):
                return True
            
            # 取最近活跃时间：优先 last_active_time，否则 started_at
            last_active_str = session.get('last_active_time') or session.get('started_at')
            if not last_active_str:
                # 缺少时间信息时保守判定过期，避免复用异常会话
                return True
            
            try:
                last_active = datetime.fromisoformat(last_active_str.replace('Z', '+00:00'))
            except Exception:
                # 兼容已为datetime对象的情况
                last_active = last_active_str if isinstance(last_active_str, datetime) else None
            
            if not last_active:
                return True
            
            # 空闲超时阈值：10分钟
            idle_seconds = (datetime.utcnow() - last_active.replace(tzinfo=None)).total_seconds()
            return idle_seconds > 10 * 60
            
        except Exception as e:
            self.logger.error(f"检查会话过期失败: {e}")
            return True
    
    async def _update_session_activity(self, session_id: str):
        """更新会话活动时间"""
        try:
            await self.session_repo.update_session_activity(
                session_id=session_id,
                update_stats=True
            )
        except Exception as e:
            self.logger.error(f"更新会话活动时间失败: {e}")
    