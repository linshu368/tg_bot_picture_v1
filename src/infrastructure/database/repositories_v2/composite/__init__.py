"""
组合Repository模块 V2
负责跨表操作的组合Repository实现

主要组合Repository：
1. UserCompositeRepository - 用户注册、签到等用户生命周期操作
2. PointCompositeRepository - 积分操作、支付充值、任务扣费等积分流转操作  
3. SessionCompositeRepository - 会话管理和活动统计
4. ActionCompositeRepository - 行为记录和统计分析
"""

from .user_composite_repository import UserCompositeRepository
from .point_composite_repository import PointCompositeRepository
from .session_composite_repository import SessionCompositeRepository
from .action_composite_repository import ActionCompositeRepository

__all__ = [
    'UserCompositeRepository',
    'PointCompositeRepository',
    'SessionCompositeRepository',
    'ActionCompositeRepository',
] 