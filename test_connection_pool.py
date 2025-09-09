#!/usr/bin/env python3
"""
连接池性能测试脚本
用于验证连接池优化是否有效
"""

import asyncio
import time
import logging
from src.infrastructure.database.supabase_manager import SupabaseManager
from src.utils.config.settings import DatabaseSettings
from src.infrastructure.database.repositories_v2.composite.user_composite_repository import UserCompositeRepository

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_user_registration_performance():
    """测试用户注册性能"""
    
    # 初始化数据库连接
    settings = DatabaseSettings(
        supabase_url="https://your-project.supabase.co",  # 替换为实际的URL
        supabase_key="your-anon-key"  # 替换为实际的Key
    )
    supabase_manager = SupabaseManager(settings)
    
    try:
        await supabase_manager.initialize()
        logger.info("数据库连接初始化完成")
        
        # 创建用户组合仓库
        user_repo = UserCompositeRepository(supabase_manager)
        
        # 测试数据
        test_users = [
            {
                'telegram_id': 1000001,
                'username': 'test_user_1',
                'first_name': 'Test',
                'last_name': 'User1'
            },
            {
                'telegram_id': 1000002,
                'username': 'test_user_2',
                'first_name': 'Test',
                'last_name': 'User2'
            },
            {
                'telegram_id': 1000003,
                'username': 'test_user_3',
                'first_name': 'Test',
                'last_name': 'User3'
            }
        ]
        
        # 测试单次注册性能
        logger.info("开始测试用户注册性能...")
        
        for i, user_data in enumerate(test_users, 1):
            start_time = time.time()
            
            try:
                result = await user_repo.create(user_data)
                end_time = time.time()
                duration = end_time - start_time
                
                if result and not result.get('success', True):
                    logger.error(f"用户 {i} 注册失败: {result.get('message', 'Unknown error')}")
                else:
                    logger.info(f"用户 {i} 注册成功，耗时: {duration:.3f}秒")
                    
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                logger.error(f"用户 {i} 注册异常，耗时: {duration:.3f}秒，错误: {e}")
        
        # 测试并发注册性能
        logger.info("开始测试并发注册性能...")
        
        async def register_user(user_data, user_id):
            start_time = time.time()
            try:
                result = await user_repo.create(user_data)
                end_time = time.time()
                duration = end_time - start_time
                return user_id, duration, result
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                return user_id, duration, str(e)
        
        # 并发注册测试
        concurrent_users = [
            {
                'telegram_id': 2000001,
                'username': 'concurrent_user_1',
                'first_name': 'Concurrent',
                'last_name': 'User1'
            },
            {
                'telegram_id': 2000002,
                'username': 'concurrent_user_2',
                'first_name': 'Concurrent',
                'last_name': 'User2'
            },
            {
                'telegram_id': 2000003,
                'username': 'concurrent_user_3',
                'first_name': 'Concurrent',
                'last_name': 'User3'
            }
        ]
        
        start_time = time.time()
        tasks = [register_user(user_data, i+1) for i, user_data in enumerate(concurrent_users)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        total_duration = end_time - start_time
        logger.info(f"并发注册总耗时: {total_duration:.3f}秒")
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"并发注册异常: {result}")
            else:
                user_id, duration, data = result
                logger.info(f"并发用户 {user_id} 注册耗时: {duration:.3f}秒")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
    finally:
        await supabase_manager.close()
        logger.info("数据库连接已关闭")

if __name__ == "__main__":
    asyncio.run(test_user_registration_performance())
