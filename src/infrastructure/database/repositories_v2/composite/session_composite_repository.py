"""
SessionCompositeRepository V2 - 会话管理组合Repository
负责跨表操作的会话管理业务逻辑

主要职责：
1. 会话创建（user_sessions_v2 + session_records_v2 + user_activity_stats_v2）
2. 会话结束（session_records_v2 + user_activity_stats_v2）
3. 会话活动更新（session_records_v2 + user_activity_stats_v2）
4. 会话查询和统计分析

设计特点：
- 封装跨表事务操作
- 对外提供与旧版Repository兼容的接口
- 统一的错误处理和数据格式输出
- 简单的事务管理机制
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from ..single.user_session_repository_v2 import UserSessionRepositoryV2
from ..single.session_record_repository_v2 import SessionRecordRepositoryV2
from ..single.user_activity_stats_repository_v2 import UserActivityStatsRepositoryV2


class SessionCompositeRepository:
    """会话组合Repository V2版本
    
    封装会话相关的跨表事务操作，对外提供与旧版Repository兼容的接口
    """
    
    def __init__(self, supabase_manager: Any):
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        
        # 初始化各个单表Repository
        self.session_repo = UserSessionRepositoryV2(supabase_manager)
        self.record_repo = SessionRecordRepositoryV2(supabase_manager)
        self.stats_repo = UserActivityStatsRepositoryV2(supabase_manager)
    
    def get_client(self) -> Any:
        """获取Supabase客户端"""
        return self.supabase_manager.get_client()
    
    @asynccontextmanager
    async def _transaction(self):
        """简单的事务管理上下文（后续可扩展为真正的DB事务）"""
        rollback_actions: List[Any] = []
        self.logger.debug("会话事务开始")
        try:
            yield rollback_actions
            self.logger.debug("会话事务成功完成")
        except Exception as e:
            self.logger.warning(f"会话事务异常，开始回滚: {e}")
            for action in reversed(rollback_actions):
                try:
                    await action()
                    self.logger.debug("会话事务回滚操作成功")
                except Exception as rollback_error:
                    self.logger.error(f"会话事务回滚操作失败: {rollback_error}")
            raise e
    
    def _standardize_error_response(self, success: bool = False, message: str = "", data: Any = None) -> Dict[str, Any]:
        """标准化错误响应格式"""
        return {
            'success': success,
            'message': message,
            'data': data
        }
    
    def _generate_session_id(self) -> str:
        """生成唯一的会话ID"""
        return f"sess_{uuid.uuid4().hex[:16]}"
    
    # ==================== 核心会话管理接口 ====================
    
    async def create_session(self, user_id: int, session_id: str = None, session_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建新会话
        
        跨表操作：
        1. user_sessions_v2: 创建用户会话关联
        2. session_records_v2: 创建会话详细记录
        3. user_activity_stats_v2: 更新会话计数和活动时间
        
        Args:
            user_id: 用户ID
            session_id: 可选的会话ID，不提供则自动生成
            session_data: 会话数据，包含started_at等
            
        Returns:
            标准化响应格式 {success, message, data}
        """
        try:
            if not session_id:
                session_id = self._generate_session_id()
            
            current_time = datetime.utcnow().isoformat()
            session_data = session_data or {}
            
            async with self._transaction() as rollback_actions:
                # 1. 核心写：创建用户会话关联（同步）
                session_association = await self.session_repo.create({
                    'user_id': user_id,
                    'session_id': session_id
                })
                rollback_actions.append(lambda: self.session_repo.delete(session_association['id']))

                # 2/3. 次要写：创建会话记录、更新统计（后台）
                record_data = {
                    'user_id': user_id,
                    'session_id': session_id,
                    'started_at': session_data.get('started_at', current_time),
                    'message_count_user': session_data.get('message_count_user', 0),
                    'ended_at': None,
                    'duration_sec': None,
                    'summary': session_data.get('summary')
                }

                async def _background_record_and_stats():
                    try:
                        created_record = await self.record_repo.create(record_data)
                        # 注意：后台任务不纳入回滚
                        await self.stats_repo.increment_session_count(user_id)
                    except Exception as bg_err:
                        self.logger.error(f"创建会话记录/更新统计失败(后台): {bg_err}")

                try:
                    asyncio.create_task(_background_record_and_stats())
                except Exception as schedule_err:
                    self.logger.error(f"调度会话后台任务失败: {schedule_err}")

                self.logger.info(f"会话创建成功: user_id={user_id}, session_id={session_id}")

                return self._standardize_error_response(
                    success=True,
                    message="会话创建成功",
                    data={
                        'session_id': session_id,
                        'user_id': user_id,
                        'started_at': record_data['started_at'],
                        'session_association': session_association
                    }
                )
                
        except Exception as e:
            self.logger.error(f"创建会话失败: {e}")
            return self._standardize_error_response(
                success=False,
                message=f"创建会话失败: {str(e)}",
                data=None
            )
    
    async def end_session(self, session_id: str, message_count_user: int = None, summary: str = None) -> Dict[str, Any]:
        """结束会话 (优化版)
        
        跨表操作：
        1. session_records_v2: 设置结束时间和统计信息 (同步)
        2. user_activity_stats_v2: 更新最后活跃时间和消息统计 (后台异步)
        """
        try:
            async with self._transaction() as rollback_actions:
                # 获取会话记录
                session_record = await self.record_repo.find_one(session_id=session_id)
                if not session_record:
                    return self._standardize_error_response(
                        success=False,
                        message=f"会话不存在: {session_id}",
                        data=None
                    )

                # 计算持续时间
                ended_at = datetime.utcnow().isoformat()
                started_at = session_record.get('started_at')
                duration_sec = None

                if started_at:
                    try:
                        start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(ended_at.replace('Z', '+00:00'))
                        duration_sec = int((end_dt - start_dt).total_seconds())
                    except Exception as e:
                        self.logger.warning(f"计算会话持续时间失败: {e}")

                # 更新会话记录 (同步)
                old_record_data = session_record.copy()
                update_data = {
                    'ended_at': ended_at,
                    'duration_sec': duration_sec
                }

                if message_count_user is not None:
                    update_data['message_count_user'] = message_count_user
                if summary is not None:
                    update_data['summary'] = summary

                success = await self.record_repo.update(session_record['id'], update_data)
                if not success:
                    raise Exception("更新会话记录失败")

                # 添加回滚操作
                rollback_actions.append(lambda: self.record_repo.update(session_record['id'], {
                    'ended_at': old_record_data.get('ended_at'),
                    'duration_sec': old_record_data.get('duration_sec'),
                    'message_count_user': old_record_data.get('message_count_user'),
                    'summary': old_record_data.get('summary')
                }))

                # 后台异步更新用户统计
                user_id = session_record['user_id']
                async def _background_update_stats():
                    try:
                        if message_count_user:
                            await self.stats_repo.increment_message_count(user_id, message_count_user)
                        await self.stats_repo.update_last_active_time(user_id)
                    except Exception as bg_err:
                        self.logger.error(f"会话结束时更新用户统计失败(后台): {bg_err}")

                asyncio.create_task(_background_update_stats())

                self.logger.info(f"会话结束成功: session_id={session_id}")

                return self._standardize_error_response(
                    success=True,
                    message="会话结束成功",
                    data={
                        'session_id': session_id,
                        'ended_at': ended_at,
                        'duration_sec': duration_sec,
                        'message_count_user': message_count_user,
                        'summary': summary
                    }
                )

        except Exception as e:
            self.logger.error(f"结束会话失败: {e}")
            return self._standardize_error_response(
                success=False,
                message=f"结束会话失败: {str(e)}",
                data=None
            )

    
    async def update_session_activity(self, session_id: str, message_count: int = None, update_stats: bool = True) -> Dict[str, Any]:
        """更新会话活动 (优化版)
        
        1. 更新 session_records_v2 (同步)
        2. user_activity_stats_v2 更新 (后台异步)
        """
        try:
            async with self._transaction() as rollback_actions:
                # 获取会话记录
                session_record = await self.record_repo.find_one(session_id=session_id)
                if not session_record:
                    return self._standardize_error_response(
                        success=False,
                        message=f"会话不存在: {session_id}",
                        data=None
                    )

                # 更新会话记录 (同步)
                if message_count:
                    old_count = session_record.get('message_count_user', 0)
                    new_count = old_count + message_count

                    success = await self.record_repo.update(session_record['id'], {
                        'message_count_user': new_count
                    })

                    if not success:
                        raise Exception("更新会话消息数量失败")

                    # 添加回滚操作
                    rollback_actions.append(lambda: self.record_repo.update(session_record['id'], {
                        'message_count_user': old_count
                    }))

                # 后台异步更新用户统计
                if update_stats:
                    user_id = session_record['user_id']
                    async def _background_update_stats():
                        try:
                            if message_count:
                                await self.stats_repo.increment_message_count(user_id, message_count)
                            await self.stats_repo.update_last_active_time(user_id)
                        except Exception as bg_err:
                            self.logger.error(f"更新会话活动时更新用户统计失败(后台): {bg_err}")

                    asyncio.create_task(_background_update_stats())

                self.logger.debug(f"会话活动更新成功: session_id={session_id}")

                return self._standardize_error_response(
                    success=True,
                    message="会话活动更新成功",
                    data={
                        'session_id': session_id,
                        'message_count_added': message_count,
                        'stats_updated': update_stats
                    }
                )

        except Exception as e:
            self.logger.error(f"更新会话活动失败: {e}")
            return self._standardize_error_response(
                success=False,
                message=f"更新会话活动失败: {str(e)}",
                data=None
            )

    
    # ==================== 查询接口（兼容旧版） ====================
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取完整会话信息
        
        聚合查询：会话关联 + 详细记录
        """
        try:
            # 获取会话关联信息
            session_association = await self.session_repo.get_by_session_id(session_id)
            if not session_association:
                return None
            
            # 获取会话详细记录
            session_record = await self.record_repo.find_one(session_id=session_id)
            # 获取用户活动统计（用于last_active_time）
            user_stats = None
            try:
                user_stats = await self.stats_repo.get_by_user_id(session_association['user_id'])
            except Exception as _:
                user_stats = None
            
            # 聚合数据
            session_info = {
                'id': session_association['id'],
                'user_id': session_association['user_id'],
                'session_id': session_id
            }
            
            # 合并会话记录数据
            if session_record:
                session_info.update(session_record)
            
            # 合并用户统计的最后活跃时间
            if user_stats and user_stats.get('last_active_time'):
                session_info['last_active_time'] = user_stats.get('last_active_time')
            
            return session_info
            
        except Exception as e:
            self.logger.error(f"获取会话信息失败: {e}")
            return None
    
    async def get_user_sessions(self, user_id: int, limit: int = 10, include_records: bool = True) -> List[Dict[str, Any]]:
        """获取用户会话列表
        
        Args:
            user_id: 用户ID  
            limit: 限制数量
            include_records: 是否包含详细记录
            
        Returns:
            会话列表
        """
        try:
            # 获取用户会话关联
            sessions = await self.session_repo.get_user_sessions(user_id, limit)
            
            if not include_records:
                return sessions
            
            # 批量获取会话记录
            session_ids = [s['session_id'] for s in sessions]
            records = {}
            
            for session_id in session_ids:
                record = await self.record_repo.find_one(session_id=session_id)
                if record:
                    records[session_id] = record
            
            # 合并数据
            result = []
            for session in sessions:
                session_id = session['session_id']
                merged_session = {
                    **session,
                    **records.get(session_id, {})
                }
                result.append(merged_session)
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取用户会话列表失败: {e}")
            return []
    
    async def get_user_session_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取用户会话统计
        
        Args:
            user_id: 用户ID
            days: 统计天数
            
        Returns:
            统计信息
        """
        try:
            # 获取会话记录统计
            record_stats = await self.record_repo.get_session_stats(user_id, days)
            
            # 获取用户活动统计
            user_stats = await self.stats_repo.get_by_user_id(user_id)
            
            # 合并统计信息
            combined_stats = {
                'user_id': user_id,
                'period_days': days,
                **record_stats,
                'total_sessions_all_time': user_stats.get('session_count', 0) if user_stats else 0,
                'total_messages_all_time': user_stats.get('total_messages_sent', 0) if user_stats else 0,
                'first_active_time': user_stats.get('first_active_time') if user_stats else None,
                'last_active_time': user_stats.get('last_active_time') if user_stats else None
            }
            
            return combined_stats
            
        except Exception as e:
            self.logger.error(f"获取用户会话统计失败: {e}")
            return {}
    
    async def get_active_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取活跃会话（未结束的会话）"""
        try:
            # 查询未结束的会话记录
            records = await self.record_repo.find_many(ended_at=None, limit=limit)
            
            # 获取对应的会话关联信息并合并
            result = []
            for record in records:
                session_association = await self.session_repo.get_by_session_id(record['session_id'])
                if session_association:
                    merged_session = {
                        **session_association,
                        **record
                    }
                    result.append(merged_session)
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取活跃会话失败: {e}")
            return []
    
    async def check_session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        try:
            session_association = await self.session_repo.get_by_session_id(session_id)
            return session_association is not None
        except Exception as e:
            self.logger.error(f"检查会话存在性失败: {e}")
            return False
    
    # ==================== 与旧版Repository完全兼容的接口 ====================
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """兼容旧版create接口"""
        user_id = data.get('user_id')
        session_id = data.get('session_id')
        
        if not user_id:
            raise ValueError("user_id is required")
        
        result = await self.create_session(user_id, session_id, data)
        if result['success']:
            return result['data']
        else:
            raise Exception(result['message'])
    
    async def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """兼容旧版根据session_id获取接口"""
        return await self.get_session_info(session_id)
    
    async def update_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """兼容旧版更新会话数据接口"""
        message_count = data.get('message_count_user') or data.get('message_count')
        result = await self.update_session_activity(session_id, message_count)
        return result['success']
    
    async def start_session(self, user_id: int, session_id: str) -> Dict[str, Any]:
        """兼容旧版开始会话接口"""
        result = await self.create_session(user_id, session_id)
        if result['success']:
            return result['data']
        else:
            raise Exception(result['message'])
    
    async def end_session_legacy(self, session_id: str, summary: str = None) -> bool:
        """兼容旧版结束会话接口"""
        result = await self.end_session(session_id, summary=summary)
        return result['success']
    
    # ==================== 清理和维护接口 ====================
    
    async def cleanup_old_sessions(self, days: int = 90) -> int:
        """清理旧会话数据
        
        Args:
            days: 保留天数
            
        Returns:
            清理的记录数量
        """
        try:
            # 清理会话记录
            cleaned_records = await self.record_repo.cleanup_old_sessions(days)
            
            self.logger.info(f"清理旧会话完成: 清理了 {cleaned_records} 条记录")
            return cleaned_records
            
        except Exception as e:
            self.logger.error(f"清理旧会话失败: {e}")
            return 0
    
    async def cleanup_user_sessions(self, user_id: int) -> bool:
        """清理用户会话数据（软删除）"""
        try:
            # 获取用户的所有活跃会话
            sessions = await self.session_repo.find_many(user_id=user_id, is_active=True)
            
            success_count = 0
            for session in sessions:
                # 软删除会话
                if await self.session_repo.update(session['id'], {'is_active': False}):
                    success_count += 1
            
            self.logger.info(f"清理用户会话完成: user_id={user_id}, 清理数量={success_count}")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"清理用户会话失败: {e}")
            return False

    # ==================== 兼容性方法别名 ====================
    
    async def record_message(self, session_id: str, message_type: str = 'text', message_content: str = None, **kwargs) -> Dict[str, Any]:
        """记录会话消息（兼容接口）"""
        try:
            record_data = {
                'session_id': session_id,
                'message_type': message_type,
                'message_content': message_content or '',
                'created_at': datetime.utcnow().isoformat(),
                **kwargs
            }
            return await self.record_repo.create(record_data)
        except Exception as e:
            self.logger.error(f"记录会话消息失败: {e}")
            raise
    
    async def get_session_records(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取会话记录（兼容接口）"""
        try:
            return await self.record_repo.get_by_session_id(session_id, limit)
        except Exception as e:
            self.logger.error(f"获取会话记录失败: {e}")
            return []
    
    async def get_user_activity_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取用户活动摘要（兼容别名）"""
        return await self.get_user_session_stats(user_id, days)
    
    async def cleanup_expired_sessions(self, days: int = 90) -> int:
        """清理过期会话（兼容别名）"""
        return await self.cleanup_old_sessions(days) 