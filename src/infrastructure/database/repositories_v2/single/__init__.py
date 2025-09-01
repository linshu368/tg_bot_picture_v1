"""
数据库Repository v2包
基于新的v2表结构设计的Repository系统

按优先级逐步替换原有Repository：
1. BaseRepositoryV2 (基础抽象类) - ✅ 已完成
2. UserRepositoryV2 (users_v2) - ✅ 已完成 - 锚点表，优先替换
3. UserWalletRepositoryV2 (user_wallet_v2) - ✅ 已完成 - 钱包管理
4. PointRecordRepositoryV2 (point_records_v2) - ✅ 已完成 - 积分记录
5. UserSessionRepositoryV2 (user_sessions_v2) - ✅ 已完成 - 用户会话基础关联
6. SessionRecordRepositoryV2 (session_records_v2) - ✅ 已完成 - 会话详细统计
7. UserActionRecordRepositoryV2 (user_action_records_v2) - ✅ 已完成 - 用户行为记录
8. PaymentOrderRepositoryV2 (payment_orders_v2) - ✅ 已完成 - 支付订单管理
9. ImageTaskRepositoryV2 (image_tasks_v2) - ✅ 已完成 - 图像任务管理
10. DailyCheckinRepositoryV2 (daily_checkins_v2) - ✅ 已完成 - 每日签到管理
11. UserActivityStatsRepositoryV2 (user_activity_stats_v2) - ✅ 已完成 - 用户活动统计

🎉 所有v2单表Repository已完成！

设计原则：
- 数据分离：不同业务数据存储在专门的表中
- 专业化管理：每个Repository专注于特定业务领域
- 向后兼容：与v1版本Repository共存，逐步迁移
- 渐进演进：表repo + 组合repo 模式，最小化service层变更

v2版本特性：
- 适配部分表移除updated_at字段的情况
- 支持UUID和JSONB字段类型
- 提供软删除和硬删除选项
- 保持与原有Repository相同的接口规范
"""

# 基础Repository V2
from .base_repository_v2 import BaseRepositoryV2

# 核心用户Repository（优先替换）
from .user_repository_v2 import UserRepositoryV2

# 用户钱包Repository
from .user_wallet_repository_v2 import UserWalletRepositoryV2

# 积分记录Repository
from .point_record_repository_v2 import PointRecordRepositoryV2

# 用户会话Repository
from .user_session_repository_v2 import UserSessionRepositoryV2

# 会话记录Repository
from .session_record_repository_v2 import SessionRecordRepositoryV2

# 用户行为记录Repository
from .user_action_record_repository_v2 import UserActionRecordRepositoryV2

# 支付订单Repository
from .payment_order_repository_v2 import PaymentOrderRepositoryV2

# 图像任务Repository
from .image_task_repository_v2 import ImageTaskRepositoryV2

# 每日签到Repository
from .daily_checkin_repository_v2 import DailyCheckinRepositoryV2

# 用户活动统计Repository
from .user_activity_stats_repository_v2 import UserActivityStatsRepositoryV2

__all__ = [
    'BaseRepositoryV2',
    'UserRepositoryV2',
    'UserWalletRepositoryV2',
    'PointRecordRepositoryV2',
    'UserSessionRepositoryV2',
    'SessionRecordRepositoryV2',
    'UserActionRecordRepositoryV2',
    'PaymentOrderRepositoryV2',
    'ImageTaskRepositoryV2',
    'DailyCheckinRepositoryV2',
    'UserActivityStatsRepositoryV2',
] 