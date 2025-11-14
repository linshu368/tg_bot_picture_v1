"""
用户消息处理状态管理器
用于防止用户连续发送消息时的并发处理问题
"""

import asyncio
import logging
import time
from typing import Set, Dict, Optional
from datetime import datetime, timezone

class UserProcessingState:
    """用户消息处理状态管理器
    
    功能:
    1. 防止同一用户的消息并发处理
    2. 确保严格的 user-bot-user-bot 交替模式
    3. 提供状态查询和管理接口
    """
    
    def __init__(self):
        self._processing_users: Set[str] = set()  # 正在处理消息的用户集合
        self._processing_start_time: Dict[str, float] = {}  # 处理开始时间（用于超时检测）
        self._last_window_start_time: Dict[str, float] = {}  # 最近一次处理窗口开始时间
        self._last_window_end_time: Dict[str, float] = {}    # 最近一次处理窗口结束时间
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)
        self.logger.info("🟢 UserProcessingState 初始化完成")
    
    async def is_processing(self, user_id: str) -> bool:
        """检查用户是否正在处理中
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: True表示正在处理中，False表示空闲
        """
        async with self._lock:
            return user_id in self._processing_users
    
    async def start_processing(self, user_id: str) -> bool:
        """开始处理用户消息，尝试获取处理锁
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: True表示成功获取锁，False表示用户已在处理中
        """
        async with self._lock:
            if user_id in self._processing_users:
                self.logger.info(f"🚫 用户 {user_id} 已在处理中，拒绝新请求")
                return False
            
            self._processing_users.add(user_id)
            now = time.time()
            self._processing_start_time[user_id] = now
            # 记录最近一次窗口开始时间
            self._last_window_start_time[user_id] = now
            # 清空窗口结束时间，表示窗口仍在进行
            self._last_window_end_time.pop(user_id, None)
            self.logger.info(f"🔒 用户 {user_id} 开始处理")
            return True
    
    async def finish_processing(self, user_id: str):
        """完成处理，释放用户锁
        
        Args:
            user_id: 用户ID
        """
        async with self._lock:
            if user_id in self._processing_users:
                self._processing_users.discard(user_id)
                start_time = self._processing_start_time.pop(user_id, None)
                now = time.time()
                # 记录最近一次窗口结束时间
                self._last_window_end_time[user_id] = now
                duration = now - start_time if start_time else 0
                self.logger.info(f"🔓 用户 {user_id} 处理完成，耗时: {duration:.2f}秒")
            else:
                self.logger.warning(f"⚠️ 尝试释放未锁定的用户: {user_id}")
    
    async def should_ignore_message(self, user_id: str, message_time: datetime) -> bool:
        """判断是否应忽略该消息（如果其发送时间处于上一个或当前处理窗口内）
        
        规则：
        - 若当前处于处理状态：忽略所有发送时间 >= 当前处理开始时间 的消息
        - 若当前空闲：忽略发送时间位于最近一次 [start, end] 窗口内的消息
        """
        # 统一为UTC时间戳
        if message_time.tzinfo is None:
            # 视为UTC
            msg_ts = message_time.replace(tzinfo=timezone.utc).timestamp()
        else:
            msg_ts = message_time.astimezone(timezone.utc).timestamp()
        
        async with self._lock:
            # 当前正在处理：丢弃在处理窗口开始之后发送的消息
            if user_id in self._processing_users:
                start_ts = self._processing_start_time.get(user_id)
                if start_ts is not None and msg_ts >= start_ts:
                    self.logger.info(f"⛔ 忽略消息（处于当前处理窗口内） user_id={user_id}")
                    return True
                return False
            
            # 当前空闲：若消息时间位于最近一次已结束窗口内，则忽略
            start_ts = self._last_window_start_time.get(user_id)
            end_ts = self._last_window_end_time.get(user_id)
            if start_ts is not None and end_ts is not None and start_ts <= msg_ts <= end_ts:
                self.logger.info(f"⛔ 忽略消息（属于上一处理窗口期间发送） user_id={user_id}")
                return True
            
            return False
    
    async def clear_all(self):
        """清除所有处理状态（重启时使用）"""
        async with self._lock:
            count = len(self._processing_users)
            self._processing_users.clear()
            self._processing_start_time.clear()
            self._last_window_start_time.clear()
            self._last_window_end_time.clear()
            self.logger.info(f"🧹 清除所有用户处理状态，共清除 {count} 个用户")
    
    async def get_processing_users_count(self) -> int:
        """获取当前正在处理的用户数量
        
        Returns:
            int: 正在处理的用户数量
        """
        async with self._lock:
            return len(self._processing_users)
    
    async def cleanup_timeout_users(self, timeout_seconds: int = 300):
        """清理超时的用户状态（防止死锁）
        
        Args:
            timeout_seconds: 超时时间（秒），默认5分钟
        """
        current_time = time.time()
        timeout_users = []
        
        async with self._lock:
            for user_id, start_time in self._processing_start_time.items():
                if current_time - start_time > timeout_seconds:
                    timeout_users.append(user_id)
            
            for user_id in timeout_users:
                self._processing_users.discard(user_id)
                self._processing_start_time.pop(user_id, None)
                self.logger.warning(f"⏰ 清理超时用户状态: {user_id}")
        
        if timeout_users:
            self.logger.info(f"🧹 清理了 {len(timeout_users)} 个超时用户状态")
        
        return len(timeout_users)
    
    async def get_status_report(self) -> Dict:
        """获取状态报告（用于监控和调试）
        
        Returns:
            dict: 包含当前状态的详细信息
        """
        async with self._lock:
            current_time = time.time()
            processing_details = {}
            
            for user_id in self._processing_users:
                start_time = self._processing_start_time.get(user_id, current_time)
                duration = current_time - start_time
                processing_details[user_id] = {
                    "start_time": start_time,
                    "duration": duration
                }
            
            return {
                "processing_count": len(self._processing_users),
                "processing_users": list(self._processing_users),
                "processing_details": processing_details,
                "timestamp": current_time
            }


# 全局单例实例
user_processing_state = UserProcessingState()


async def start_background_cleanup_task():
    """启动后台清理任务（可选）"""
    async def cleanup_loop():
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟执行一次
                await user_processing_state.cleanup_timeout_users()
            except Exception as e:
                logging.getLogger(__name__).error(f"后台清理任务异常: {e}")
    
    asyncio.create_task(cleanup_loop())


# 如果需要在模块导入时自动启动后台清理，取消下面的注释
# asyncio.create_task(start_background_cleanup_task())
