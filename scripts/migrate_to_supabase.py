#!/usr/bin/env python3
"""
数据库迁移脚本：SQLite -> Supabase
将现有的SQLite数据库迁移到Supabase
"""

import asyncio
import aiosqlite
import logging
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.config.settings import load_settings
from src.infrastructure.database.supabase_manager import SupabaseManager
from src.infrastructure.database.repositories.supabase_user_repository import SupabaseUserRepository
from src.infrastructure.database.repositories.supabase_point_record_repository import SupabasePointRecordRepository

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """数据库迁移工具"""
    
    def __init__(self, sqlite_path: str, supabase_manager: SupabaseManager):
        self.sqlite_path = sqlite_path
        self.supabase_manager = supabase_manager
        self.sqlite_conn = None
        
    async def initialize(self):
        """初始化连接"""
        try:
            # 连接SQLite
            self.sqlite_conn = await aiosqlite.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = aiosqlite.Row
            
            # 初始化Supabase
            await self.supabase_manager.initialize()
            
            logger.info("数据库连接初始化完成")
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise
    
    async def close(self):
        """关闭连接"""
        if self.sqlite_conn:
            await self.sqlite_conn.close()
        await self.supabase_manager.close()
        logger.info("数据库连接已关闭")
    
    async def migrate_users(self):
        """迁移用户表"""
        logger.info("开始迁移用户表...")
        
        try:
            # 从SQLite读取用户数据
            cursor = await self.sqlite_conn.execute("""
                SELECT id, telegram_id, username, first_name, last_name, uid, points, 
                       level, is_active, created_at, updated_at, session_count, 
                       total_points_spent, total_paid_amount, first_add, utm_source,
                       first_active_time, last_active_time, total_messages_sent
                FROM users
            """)
            
            users = await cursor.fetchall()
            logger.info(f"从SQLite读取到 {len(users)} 个用户")
            
            if not users:
                logger.info("没有用户数据需要迁移")
                return
            
            # 创建Supabase用户Repository
            user_repo = SupabaseUserRepository(self.supabase_manager)
            
            # 批量迁移用户
            migrated_count = 0
            failed_count = 0
            
            for user in users:
                try:
                    # 检查用户是否已存在
                    existing_user = await user_repo.get_by_telegram_id(user['telegram_id'])
                    if existing_user:
                        logger.info(f"用户已存在，跳过: telegram_id={user['telegram_id']}")
                        continue
                    
                    # 准备用户数据
                    user_data = {
                        'telegram_id': user['telegram_id'],
                        'username': user['username'],
                        'first_name': user['first_name'],
                        'last_name': user['last_name'],
                        'uid': user['uid'],
                        'points': user['points'],
                        'level': user['level'],
                        'is_active': bool(user['is_active']),
                        'session_count': user['session_count'],
                        'total_points_spent': user['total_points_spent'],
                        'total_paid_amount': float(user['total_paid_amount']),
                        'first_add': bool(user['first_add']),
                        'utm_source': user['utm_source'],
                        'total_messages_sent': user['total_messages_sent']
                    }
                    
                    # 处理时间字段
                    if user['created_at']:
                        user_data['created_at'] = user['created_at']
                    if user['updated_at']:
                        user_data['updated_at'] = user['updated_at']
                    if user['first_active_time']:
                        user_data['first_active_time'] = user['first_active_time']
                    if user['last_active_time']:
                        user_data['last_active_time'] = user['last_active_time']
                    
                    # 创建用户
                    await user_repo.create(user_data)
                    migrated_count += 1
                    
                    if migrated_count % 10 == 0:
                        logger.info(f"已迁移 {migrated_count} 个用户")
                        
                except Exception as e:
                    logger.error(f"迁移用户失败 telegram_id={user['telegram_id']}: {e}")
                    failed_count += 1
            
            logger.info(f"用户迁移完成: 成功={migrated_count}, 失败={failed_count}")
            
        except Exception as e:
            logger.error(f"迁移用户表失败: {e}")
            raise
    
    async def migrate_point_records(self):
        """迁移积分记录表"""
        logger.info("开始迁移积分记录表...")
        
        try:
            # 从SQLite读取积分记录数据
            cursor = await self.sqlite_conn.execute("""
                SELECT pr.id, pr.user_id, pr.points_change, pr.action_type, 
                       pr.description, pr.created_at, pr.points_balance,
                       u.telegram_id
                FROM point_records pr
                JOIN users u ON pr.user_id = u.id
                ORDER BY pr.created_at
            """)
            
            records = await cursor.fetchall()
            logger.info(f"从SQLite读取到 {len(records)} 条积分记录")
            
            if not records:
                logger.info("没有积分记录需要迁移")
                return
            
            # 创建Repository
            user_repo = SupabaseUserRepository(self.supabase_manager)
            point_repo = SupabasePointRecordRepository(self.supabase_manager)
            
            # 创建用户ID映射
            user_id_map = {}
            
            # 批量迁移积分记录
            migrated_count = 0
            failed_count = 0
            
            for record in records:
                try:
                    # 获取新的用户ID
                    telegram_id = record['telegram_id']
                    if telegram_id not in user_id_map:
                        supabase_user = await user_repo.get_by_telegram_id(telegram_id)
                        if not supabase_user:
                            logger.warning(f"找不到用户: telegram_id={telegram_id}")
                            failed_count += 1
                            continue
                        user_id_map[telegram_id] = supabase_user['id']
                    
                    new_user_id = user_id_map[telegram_id]
                    
                    # 准备积分记录数据
                    record_data = {
                        'user_id': new_user_id,
                        'points_change': record['points_change'],
                        'action_type': record['action_type'],
                        'description': record['description'] or '',
                        'points_balance': record['points_balance'],
                        'created_at': record['created_at']
                    }
                    
                    # 创建积分记录
                    await point_repo.create(record_data)
                    migrated_count += 1
                    
                    if migrated_count % 50 == 0:
                        logger.info(f"已迁移 {migrated_count} 条积分记录")
                        
                except Exception as e:
                    logger.error(f"迁移积分记录失败 id={record['id']}: {e}")
                    failed_count += 1
            
            logger.info(f"积分记录迁移完成: 成功={migrated_count}, 失败={failed_count}")
            
        except Exception as e:
            logger.error(f"迁移积分记录表失败: {e}")
            raise
    
    async def migrate_all(self):
        """迁移所有表"""
        logger.info("开始完整数据库迁移...")
        
        start_time = datetime.now()
        
        try:
            await self.initialize()
            
            # 迁移用户表
            await self.migrate_users()
            
            # 迁移积分记录表
            await self.migrate_point_records()
            
            # TODO: 添加其他表的迁移
            # await self.migrate_daily_checkins()
            # await self.migrate_payment_orders()
            # await self.migrate_system_config()
            # await self.migrate_session_records()
            # await self.migrate_user_action_records()
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            logger.info(f"数据库迁移完成，耗时: {duration}")
            
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}")
            raise
        finally:
            await self.close()


async def main():
    """主函数"""
    try:
        # 加载配置
        settings = load_settings()
        
        # SQLite数据库路径
        sqlite_path = "data/telegram_bot.db"  # 根据实际路径调整
        
        if not os.path.exists(sqlite_path):
            logger.error(f"SQLite数据库文件不存在: {sqlite_path}")
            return
        
        # 创建Supabase管理器
        supabase_manager = SupabaseManager(settings.database)
        
        # 创建迁移器
        migrator = DatabaseMigrator(sqlite_path, supabase_manager)
        
        # 执行迁移
        await migrator.migrate_all()
        
        logger.info("迁移任务完成！")
        
    except Exception as e:
        logger.error(f"迁移过程出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 