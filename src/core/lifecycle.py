"""
应用生命周期管理
处理启动和关闭钩子
"""

import asyncio
import logging
from typing import List, Callable


class LifecycleManager:
    """生命周期管理器"""
    
    def __init__(self):
        self.startup_hooks: List[Callable] = []
        self.shutdown_hooks: List[Callable] = []
        self.logger = logging.getLogger(__name__)
    
    def register_startup_hook(self, hook: Callable):
        """注册启动钩子"""
        self.startup_hooks.append(hook)
        self.logger.debug(f"注册启动钩子: {hook.__name__}")
    
    def register_shutdown_hook(self, hook: Callable):
        """注册关闭钩子"""
        self.shutdown_hooks.append(hook)
        self.logger.debug(f"注册关闭钩子: {hook.__name__}")
    
    async def run_startup_hooks(self):
        """执行所有启动钩子"""
        self.logger.info(f"执行 {len(self.startup_hooks)} 个启动钩子...")
        
        for hook in self.startup_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
                self.logger.debug(f"启动钩子执行成功: {hook.__name__}")
            except Exception as e:
                self.logger.error(f"启动钩子执行失败 {hook.__name__}: {e}")
                # 启动钩子失败可能需要终止启动过程
                raise
    
    async def run_shutdown_hooks(self):
        """执行所有关闭钩子"""
        self.logger.info(f"执行 {len(self.shutdown_hooks)} 个关闭钩子...")
        
        # 反向执行关闭钩子（后进先出）
        for hook in reversed(self.shutdown_hooks):
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
                self.logger.debug(f"关闭钩子执行成功: {hook.__name__}")
            except Exception as e:
                self.logger.error(f"关闭钩子执行失败 {hook.__name__}: {e}")
                # 关闭钩子失败不应该阻止其他钩子执行
                continue 