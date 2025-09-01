"""
数据库Repository包
包含所有数据访问层的实现

优先使用Supabase Repository，保留SQLite Repository用于兼容和迁移
"""

# Supabase Repository (推荐使用)
from .supabase_base_repository import SupabaseBaseRepository
from .supabase_user_repository import SupabaseUserRepository
from .supabase_point_record_repository import SupabasePointRecordRepository
from .supabase_payment_repository import SupabasePaymentOrderRepository

# 原始SQLite Repository (兼容性保留)
from .base_repository import BaseRepository
from .user_repository import UserRepository as SQLiteUserRepository
from .point_record_repository import PointRecordRepository as SQLitePointRecordRepository

# 为了向后兼容，默认导出Supabase版本
UserRepository = SupabaseUserRepository
PointRecordRepository = SupabasePointRecordRepository
PaymentOrderRepository = SupabasePaymentOrderRepository

__all__ = [
    # 推荐使用的Supabase Repository
    'SupabaseBaseRepository',
    'SupabaseUserRepository',
    'SupabasePointRecordRepository', 
    'SupabasePaymentOrderRepository',
    
    # 默认导出（指向Supabase版本）
    'UserRepository',
    'PointRecordRepository',
    'PaymentOrderRepository',
    
    # SQLite Repository（显式命名）
    'BaseRepository',
    'SQLiteUserRepository',
    'SQLitePointRecordRepository',
] 