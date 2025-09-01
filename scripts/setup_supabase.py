#!/usr/bin/env python3
"""
Supabase设置和测试脚本
使用提供的Supabase信息配置数据库并进行测试
"""

import os
import sys
import asyncio
import logging
from dataclasses import dataclass

# 设置环境变量
os.environ['SUPABASE_URL'] = 'https://lhcyrmigpqeloxjrfwmn.supabase.co'
os.environ['SUPABASE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxoY3lybWlncHFlbG94anJmd21uIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzM2MTQxNSwiZXhwIjoyMDY4OTM3NDE1fQ.I9kVX_39mit3nH8Ipzqy9jn59U1sZjQd6YhdPdvd__o'

# 其他必要的环境变量
os.environ['DATABASE_POOL_SIZE'] = '5'
os.environ['DATABASE_TIMEOUT'] = '30'
os.environ['BOT_TOKEN'] = 'test_token'
os.environ['ADMIN_USER_ID'] = '123456789'
os.environ['CLOTHOFF_API_URL'] = 'https://api.example.com'
os.environ['CLOTHOFF_API_KEY'] = 'test_key'
os.environ['CLOTHOFF_WEBHOOK_BASE_URL'] = 'https://example.com'
os.environ['PAYMENT_PID'] = 'test_pid'
os.environ['PAYMENT_KEY'] = 'test_key'
os.environ['PAYMENT_SUBMIT_URL'] = 'https://example.com'
os.environ['PAYMENT_API_URL'] = 'https://example.com'
os.environ['PAYMENT_NOTIFY_URL'] = 'https://example.com'
os.environ['PAYMENT_RETURN_URL'] = 'https://example.com'

# 添加项目根目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from src.utils.config.settings import get_settings
from src.infrastructure.database.supabase_manager import SupabaseManager
from src.infrastructure.database.repositories.supabase_user_repository import SupabaseUserRepository
from src.infrastructure.database.repositories.supabase_point_record_repository import SupabasePointRecordRepository

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_tables_in_supabase():
    """在Supabase中创建表结构"""
    logger.info("准备在Supabase中创建表结构...")
    
    try:
        settings = get_settings()
        supabase_manager = SupabaseManager(settings.database)
        await supabase_manager.initialize()
        
        # 获取表结构SQL
        await supabase_manager.create_tables()
        
        await supabase_manager.close()
        
    except Exception as e:
        logger.error(f"创建表结构时出错: {e}")
        raise


async def test_basic_operations():
    """测试基本的数据库操作"""
    logger.info("🚀 开始测试Supabase基本操作...")
    
    try:
        # 加载配置
        settings = get_settings()
        logger.info(f"Supabase URL: {settings.database.supabase_url}")
        
        # 创建管理器
        supabase_manager = SupabaseManager(settings.database)
        await supabase_manager.initialize()
        
        # 测试连接
        client = supabase_manager.get_client()
        logger.info("✅ Supabase客户端初始化成功")
        
        # 测试简单查询（检查是否有users表）
        try:
            result = client.table('users').select('*').limit(1).execute()
            logger.info("✅ users表访问成功")
            
            # 创建Repository
            user_repo = SupabaseUserRepository(supabase_manager)
            point_repo = SupabasePointRecordRepository(supabase_manager)
            
            # 测试创建用户
            test_user_data = {
                'telegram_id': 999999999,
                'username': 'test_user_setup',
                'first_name': 'Setup',
                'last_name': 'Test'
            }
            
            # 检查用户是否已存在
            existing_user = await user_repo.get_by_telegram_id(test_user_data['telegram_id'])
            if existing_user:
                logger.info("测试用户已存在，删除后重新创建...")
                delete_result = await user_repo.delete(existing_user['id'], hard_delete=True)
                if delete_result:
                    logger.info("✅ 旧测试用户删除成功")
                else:
                    logger.warning("⚠️ 旧测试用户删除失败，但继续测试")
                # 等待一下确保删除操作完成
                import asyncio
                await asyncio.sleep(1)
            
            # 创建用户
            created_user = await user_repo.create(test_user_data)
            logger.info(f"✅ 用户创建成功: uid={created_user['uid']}")
            
            # 测试积分操作
            await user_repo.add_points(created_user['id'], 25)
            logger.info("✅ 积分操作成功")
            
            # 创建积分记录
            record_data = {
                'user_id': created_user['id'],
                'points_change': 25,
                'action_type': 'setup_test',
                'description': '设置测试积分记录',
                'points_balance': 75
            }
            
            created_record = await point_repo.create(record_data)
            logger.info(f"✅ 积分记录创建成功: id={created_record['id']}")
            
            # 清理测试数据
            await user_repo.delete(created_user['id'])
            logger.info("✅ 测试数据清理完成")
            
        except Exception as e:
            if "does not exist" in str(e).lower():
                logger.warning("⚠️  users表不存在，请先在Supabase控制台创建表结构")
                logger.info("请在Supabase控制台的SQL编辑器中执行scripts/supabase_tables.sql文件中的所有SQL语句")
                await create_tables_in_supabase()
            else:
                raise
        
        await supabase_manager.close()
        logger.info("🎉 Supabase配置测试完成！")
        
    except Exception as e:
        logger.error(f"测试过程出错: {e}")
        raise


async def main():
    """主函数"""
    logger.info("🔧 开始配置和测试Supabase...")
    
    try:
        await test_basic_operations()
        
        logger.info("\n" + "="*60)
        logger.info("✅ Supabase配置成功！")
        logger.info("您现在可以：")
        logger.info("1. 在Supabase控制台创建必要的表结构（如果还没有的话）")
        logger.info("   - 执行 scripts/supabase_tables.sql 中的SQL语句")
        logger.info("2. 运行 python scripts/test_supabase.py 进行完整测试")
        logger.info("3. 如果有SQLite数据，运行 python scripts/migrate_to_supabase.py 迁移数据")
        logger.info("4. 配置其他环境变量（Bot Token等）后启动应用")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ 配置失败: {e}")
        logger.info("\n请检查：")
        logger.info("1. Supabase URL和Key是否正确")
        logger.info("2. 网络连接是否正常")
        logger.info("3. Supabase项目是否正常运行")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 