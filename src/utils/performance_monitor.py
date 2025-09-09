"""
性能监控工具
用于在bot响应链路中添加详细的性能打点日志
"""

import time
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, logger_name: str = "performance_monitor"):
        self.logger = logging.getLogger(logger_name)
        self.timers: Dict[str, float] = {}
        self.checkpoints: Dict[str, Dict[str, Any]] = {}
    
    def start_timer(self, operation_id: str, description: str = ""):
        """开始计时"""
        start_time = time.time()
        self.timers[operation_id] = start_time
        
        self.logger.info(f"⏱️  [PERF] 开始: {operation_id} - {description}")
        
        return start_time
    
    def end_timer(self, operation_id: str, description: str = ""):
        """结束计时"""
        if operation_id not in self.timers:
            self.logger.warning(f"⏱️  [PERF] 警告: 未找到计时器 {operation_id}")
            return None
        
        start_time = self.timers[operation_id]
        end_time = time.time()
        duration = end_time - start_time
        
        # 记录检查点
        self.checkpoints[operation_id] = {
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'description': description,
            'timestamp': datetime.now().isoformat()
        }
        
        # 删除计时器
        del self.timers[operation_id]
        
        self.logger.info(f"⏱️  [PERF] 完成: {operation_id} - {description} | 耗时: {duration:.3f}s")
        
        return duration
    
    def checkpoint(self, operation_id: str, checkpoint_name: str, description: str = ""):
        """记录检查点"""
        if operation_id not in self.timers:
            self.logger.warning(f"⏱️  [PERF] 警告: 未找到计时器 {operation_id}")
            return None
        
        start_time = self.timers[operation_id]
        current_time = time.time()
        elapsed = current_time - start_time
        
        self.logger.info(f"⏱️  [PERF] 检查点: {operation_id}.{checkpoint_name} - {description} | 已耗时: {elapsed:.3f}s")
        
        return elapsed
    
    def log_operation_summary(self, operation_id: str):
        """记录操作总结"""
        if operation_id not in self.checkpoints:
            self.logger.warning(f"⏱️  [PERF] 警告: 未找到操作记录 {operation_id}")
            return
        
        checkpoint = self.checkpoints[operation_id]
        self.logger.info(f"⏱️  [PERF] 总结: {operation_id} - 总耗时: {checkpoint['duration']:.3f}s")
    
    @contextmanager
    def timer(self, operation_id: str, description: str = ""):
        """上下文管理器，自动计时"""
        self.start_timer(operation_id, description)
        try:
            yield self
        finally:
            self.end_timer(operation_id, description)
    
    def async_timer(self, operation_id: str, description: str = ""):
        """异步上下文管理器，自动计时"""
        class AsyncTimer:
            def __init__(self, monitor, op_id, desc):
                self.monitor = monitor
                self.op_id = op_id
                self.desc = desc
            
            async def __aenter__(self):
                self.monitor.start_timer(self.op_id, self.desc)
                return self.monitor
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.monitor.end_timer(self.op_id, self.desc)
        
        return AsyncTimer(self, operation_id, description)
    
    def get_operation_summary(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """获取操作总结"""
        return self.checkpoints.get(operation_id)
    
    def clear_operation(self, operation_id: str):
        """清除操作记录"""
        if operation_id in self.timers:
            del self.timers[operation_id]
        if operation_id in self.checkpoints:
            del self.checkpoints[operation_id]


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器实例"""
    return performance_monitor


def log_performance(operation_id: str, description: str = ""):
    """性能日志装饰器"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            with monitor.timer(f"{operation_id}_{func.__name__}", description):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            with monitor.timer(f"{operation_id}_{func.__name__}", description):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 导入asyncio用于检查协程函数
import asyncio
