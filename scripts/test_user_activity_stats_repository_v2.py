#!/usr/bin/env python3
"""
UserActivityStatsRepositoryV2 单独测试脚本
专门测试用户活动统计Repository的CRUD操作和业务方法
"""

import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.infrastructure.database.supabase_manager import SupabaseManager
from src.infrastructure.database.repositories_v2.user_activity_stats_repository_v2 import UserActivityStatsRepositoryV2
from src.infrastructure.database.repositories_v2.user_repository_v2 import UserRepositoryV2
from src.utils.config.settings import get_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UserActivityStatsRepositoryV2TestSuite:
    """UserActivityStatsRepositoryV2 专项测试套件"""
    
    def __init__(self, supabase_manager: SupabaseManager):
        self.supabase_manager = supabase_manager
        self.stats_repo = UserActivityStatsRepositoryV2(supabase_manager)
        self.user_repo = UserRepositoryV2(supabase_manager)  # 用于创建测试用户
        
        # 测试数据收集器
        self.test_data = {
            'users': [],
            'stats': []
        }
    
    async def initialize(self):
        """初始化测试环境"""
        try:
            await self.supabase_manager.initialize()
            logger.info("✅ 测试环境初始化完成")
        except Exception as e:
            logger.error(f"❌ 测试环境初始化失败: {e}")
            raise
    
    async def create_test_user(self, telegram_id: int, username: str) -> Dict[str, Any]:
        """创建测试用户"""
        user_data = {
            'telegram_id': telegram_id,
            'username': username,
            'first_name': 'Test',
            'last_name': 'User',
            'utm_source': 'test'
        }
        user = await self.user_repo.create(user_data)
        self.test_data['users'].append(user['id'])
        return user
    
    # ==================== CRUD 测试 ====================
    
    async def test_create_user_activity_stats(self):
        """测试创建用户活动统计"""
        logger.info("🧪 测试创建用户活动统计...")
        
        try:
            # 创建测试用户
            user = await self.create_test_user(123456789, 'test_stats_user')
            
            # 测试创建活动统计
            current_time = datetime.utcnow().isoformat()
            stats_data = {
                'user_id': user['id'],
                'session_count': 5,
                'total_messages_sent': 50,
                'first_active_time': current_time,
                'last_active_time': current_time
            }
            
            created_stats = await self.stats_repo.create(stats_data)
            self.test_data['stats'].append(created_stats['id'])
            
            assert created_stats is not None
            assert created_stats['user_id'] == user['id']
            assert created_stats['session_count'] == 5
            assert created_stats['total_messages_sent'] == 50
            logger.info(f"✅ 活动统计创建成功: stats_id={created_stats['id']}")
            
            return created_stats
            
        except Exception as e:
            logger.error(f"❌ 创建用户活动统计测试失败: {e}")
            raise
    
    async def test_get_user_activity_stats(self, stats: Dict[str, Any]):
        """测试获取用户活动统计"""
        logger.info("🧪 测试获取用户活动统计...")
        
        try:
            # 测试根据ID获取
            fetched_by_id = await self.stats_repo.get_by_id(stats['id'])
            assert fetched_by_id is not None
            assert fetched_by_id['id'] == stats['id']
            logger.info("✅ 根据ID获取活动统计成功")
            
            # 测试根据用户ID获取
            fetched_by_user_id = await self.stats_repo.get_by_user_id(stats['user_id'])
            assert fetched_by_user_id is not None
            assert fetched_by_user_id['id'] == stats['id']
            logger.info("✅ 根据用户ID获取活动统计成功")
            
            # 测试查找方法
            found_stats = await self.stats_repo.find_one(user_id=stats['user_id'])
            assert found_stats is not None
            assert found_stats['id'] == stats['id']
            logger.info("✅ find_one方法成功")
            
        except Exception as e:
            logger.error(f"❌ 获取用户活动统计测试失败: {e}")
            raise
    
    async def test_update_user_activity_stats(self, stats: Dict[str, Any]):
        """测试更新用户活动统计"""
        logger.info("🧪 测试更新用户活动统计...")
        
        try:
            # 测试根据ID更新
            update_data = {
                'session_count': 10,
                'total_messages_sent': 100,
                'last_active_time': datetime.utcnow().isoformat()
            }
            
            update_result = await self.stats_repo.update(stats['id'], update_data)
            assert update_result is True
            
            # 验证更新结果
            updated_stats = await self.stats_repo.get_by_id(stats['id'])
            assert updated_stats['session_count'] == 10
            assert updated_stats['total_messages_sent'] == 100
            logger.info("✅ 根据ID更新活动统计成功")
            
            # 测试根据用户ID更新
            user_update_data = {
                'session_count': 15,
                'total_messages_sent': 150
            }
            
            user_update_result = await self.stats_repo.update_by_user_id(stats['user_id'], user_update_data)
            assert user_update_result is True
            
            # 验证更新结果
            updated_by_user = await self.stats_repo.get_by_user_id(stats['user_id'])
            assert updated_by_user['session_count'] == 15
            assert updated_by_user['total_messages_sent'] == 150
            logger.info("✅ 根据用户ID更新活动统计成功")
            
        except Exception as e:
            logger.error(f"❌ 更新用户活动统计测试失败: {e}")
            raise
    
    # ==================== 业务方法测试 ====================
    
    async def test_get_or_create_user_stats(self):
        """测试获取或创建用户统计"""
        logger.info("🧪 测试获取或创建用户统计...")
        
        try:
            # 创建新测试用户
            user = await self.create_test_user(987654321, 'get_or_create_user')
            
            # 测试首次获取（应该创建新记录）
            stats = await self.stats_repo.get_or_create_user_stats(user['id'])
            self.test_data['stats'].append(stats['id'])
            
            assert stats is not None
            assert stats['user_id'] == user['id']
            assert stats['session_count'] == 0
            assert stats['total_messages_sent'] == 0
            logger.info("✅ 首次获取用户统计成功（自动创建）")
            
            # 测试再次获取（应该返回现有记录）
            existing_stats = await self.stats_repo.get_or_create_user_stats(user['id'])
            assert existing_stats['id'] == stats['id']
            logger.info("✅ 再次获取用户统计成功（返回现有记录）")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 获取或创建用户统计测试失败: {e}")
            raise
    
    async def test_increment_session_count(self, stats: Dict[str, Any]):
        """测试增加会话计数"""
        logger.info("🧪 测试增加会话计数...")
        
        try:
            initial_count = stats['session_count']
            
            # 测试增加会话计数
            result = await self.stats_repo.increment_session_count(stats['user_id'])
            assert result is True
            
            # 验证计数增加
            updated_stats = await self.stats_repo.get_by_user_id(stats['user_id'])
            assert updated_stats['session_count'] == initial_count + 1
            assert updated_stats['last_active_time'] is not None
            logger.info("✅ 增加会话计数成功")
            
            return updated_stats
            
        except Exception as e:
            logger.error(f"❌ 增加会话计数测试失败: {e}")
            raise
    
    async def test_increment_message_count(self, stats: Dict[str, Any]):
        """测试增加消息计数"""
        logger.info("🧪 测试增加消息计数...")
        
        try:
            initial_count = stats['total_messages_sent']
            
            # 测试增加单条消息
            result1 = await self.stats_repo.increment_message_count(stats['user_id'])
            assert result1 is True
            
            updated_stats1 = await self.stats_repo.get_by_user_id(stats['user_id'])
            assert updated_stats1['total_messages_sent'] == initial_count + 1
            logger.info("✅ 增加单条消息计数成功")
            
            # 测试增加多条消息
            result2 = await self.stats_repo.increment_message_count(stats['user_id'], 5)
            assert result2 is True
            
            updated_stats2 = await self.stats_repo.get_by_user_id(stats['user_id'])
            assert updated_stats2['total_messages_sent'] == initial_count + 1 + 5
            assert updated_stats2['last_active_time'] is not None
            logger.info("✅ 增加多条消息计数成功")
            
            return updated_stats2
            
        except Exception as e:
            logger.error(f"❌ 增加消息计数测试失败: {e}")
            raise
    
    async def test_update_last_active_time(self, stats: Dict[str, Any]):
        """测试更新最后活跃时间"""
        logger.info("🧪 测试更新最后活跃时间...")
        
        try:
            old_active_time = stats['last_active_time']
            
            # 等待一秒确保时间不同
            await asyncio.sleep(1)
            
            # 测试更新最后活跃时间
            result = await self.stats_repo.update_last_active_time(stats['user_id'])
            assert result is True
            
            # 验证时间更新
            updated_stats = await self.stats_repo.get_by_user_id(stats['user_id'])
            assert updated_stats['last_active_time'] != old_active_time
            logger.info("✅ 更新最后活跃时间成功")
            
        except Exception as e:
            logger.error(f"❌ 更新最后活跃时间测试失败: {e}")
            raise
    
    async def test_get_active_users_stats(self):
        """测试获取活跃用户统计"""
        logger.info("🧪 测试获取活跃用户统计...")
        
        try:
            # 创建几个不同活跃度的用户
            users_data = [
                {'telegram_id': 111111111, 'username': 'active_user_1', 'messages': 100},
                {'telegram_id': 222222222, 'username': 'active_user_2', 'messages': 200},
                {'telegram_id': 333333333, 'username': 'active_user_3', 'messages': 50}
            ]
            
            created_stats = []
            for user_data in users_data:
                user = await self.create_test_user(user_data['telegram_id'], user_data['username'])
                
                # 创建对应的统计记录
                current_time = datetime.utcnow().isoformat()
                stats_data = {
                    'user_id': user['id'],
                    'session_count': 10,
                    'total_messages_sent': user_data['messages'],
                    'first_active_time': current_time,
                    'last_active_time': current_time
                }
                
                stats = await self.stats_repo.create(stats_data)
                created_stats.append(stats)
                self.test_data['stats'].append(stats['id'])
            
            # 测试获取活跃用户统计（按消息数排序）
            active_users = await self.stats_repo.get_active_users_stats(limit=5)
            assert len(active_users) >= 3
            
            # 验证排序（按消息数降序）
            for i in range(len(active_users) - 1):
                assert active_users[i]['total_messages_sent'] >= active_users[i + 1]['total_messages_sent']
            
            logger.info(f"✅ 获取活跃用户统计成功: {len(active_users)} 个用户")
            
        except Exception as e:
            logger.error(f"❌ 获取活跃用户统计测试失败: {e}")
            raise
    
    async def test_compatibility_methods(self):
        """测试兼容性方法"""
        logger.info("🧪 测试兼容性方法...")
        
        try:
            # 创建测试用户
            user = await self.create_test_user(555555555, 'compatibility_user')
            
            # 测试兼容性创建方法
            compat_stats = await self.stats_repo.create_user_stats(user['id'])
            self.test_data['stats'].append(compat_stats['id'])
            
            assert compat_stats is not None
            assert compat_stats['user_id'] == user['id']
            assert compat_stats['session_count'] == 0
            assert compat_stats['total_messages_sent'] == 0
            assert compat_stats['first_active_time'] is not None
            assert compat_stats['last_active_time'] is not None
            logger.info("✅ 兼容性方法create_user_stats成功")
            
        except Exception as e:
            logger.error(f"❌ 兼容性方法测试失败: {e}")
            raise
    
    # ==================== 综合测试 ====================
    
    async def test_complete_user_activity_flow(self):
        """测试完整的用户活动流程"""
        logger.info("🧪 测试完整的用户活动流程...")
        
        try:
            # 1. 创建新用户
            user = await self.create_test_user(777777777, 'flow_test_user')
            
            # 2. 用户首次活动（自动创建统计记录）
            stats = await self.stats_repo.get_or_create_user_stats(user['id'])
            self.test_data['stats'].append(stats['id'])
            
            # 3. 模拟用户活动流程
            # 开始会话
            await self.stats_repo.increment_session_count(user['id'])
            
            # 发送消息
            await self.stats_repo.increment_message_count(user['id'], 3)
            
            # 更新活跃时间
            await self.stats_repo.update_last_active_time(user['id'])
            
            # 再次发送消息
            await self.stats_repo.increment_message_count(user['id'], 2)
            
            # 开始新会话
            await self.stats_repo.increment_session_count(user['id'])
            
            # 4. 验证最终状态
            final_stats = await self.stats_repo.get_by_user_id(user['id'])
            
            assert final_stats['session_count'] == 2  # 两次会话
            assert final_stats['total_messages_sent'] == 5  # 总共5条消息
            assert final_stats['first_active_time'] is not None
            assert final_stats['last_active_time'] is not None
            
            logger.info("✅ 完整用户活动流程测试成功")
            logger.info(f"   会话数: {final_stats['session_count']}")
            logger.info(f"   消息数: {final_stats['total_messages_sent']}")
            
        except Exception as e:
            logger.error(f"❌ 完整用户活动流程测试失败: {e}")
            raise
    
    # ==================== 数据清理 ====================
    
    async def cleanup_test_data(self):
        """清理测试数据"""
        logger.info("🧹 开始清理测试数据...")
        
        try:
            # 清理活动统计记录
            for stats_id in self.test_data['stats']:
                try:
                    await self.stats_repo.delete(stats_id)
                except Exception:
                    pass
            logger.info(f"✅ 清理活动统计记录: {len(self.test_data['stats'])} 条")
            
            # 清理用户（最后清理，因为统计表有外键依赖）
            for user_id in self.test_data['users']:
                try:
                    await self.user_repo.delete(user_id, hard_delete=True)
                except Exception:
                    pass
            logger.info(f"✅ 清理用户: {len(self.test_data['users'])} 个")
            
            logger.info("✅ 测试数据清理完成")
            
        except Exception as e:
            logger.error(f"⚠️ 测试数据清理失败: {e}")
    
    # ==================== 主测试运行方法 ====================
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始UserActivityStatsRepositoryV2完整测试...")
        print("=" * 80)
        
        tests = [
            ("创建用户活动统计", self.test_create_user_activity_stats),
            ("获取或创建用户统计", self.test_get_or_create_user_stats),
            ("获取活跃用户统计", self.test_get_active_users_stats),
            ("兼容性方法测试", self.test_compatibility_methods),
            ("完整用户活动流程", self.test_complete_user_activity_flow),
        ]
        
        passed = 0
        failed = 0
        created_stats = None
        get_or_create_stats = None
        
        try:
            for test_name, test_func in tests:
                try:
                    logger.info(f"\n📋 测试: {test_name}")
                    if test_name == "创建用户活动统计":
                        created_stats = await test_func()
                        passed += 1
                    elif test_name == "获取或创建用户统计":
                        get_or_create_stats = await test_func()
                        passed += 1
                    else:
                        await test_func()
                        passed += 1
                        
                except Exception as e:
                    logger.error(f"❌ 测试 '{test_name}' 失败: {e}")
                    failed += 1
            
            # 如果基础测试成功，继续测试其他功能
            if created_stats:
                additional_tests = [
                    ("获取用户活动统计", lambda: self.test_get_user_activity_stats(created_stats)),
                    ("更新用户活动统计", lambda: self.test_update_user_activity_stats(created_stats)),
                ]
                
                for test_name, test_func in additional_tests:
                    try:
                        logger.info(f"\n📋 测试: {test_name}")
                        await test_func()
                        passed += 1
                    except Exception as e:
                        logger.error(f"❌ 测试 '{test_name}' 失败: {e}")
                        failed += 1
            
            # 如果get_or_create测试成功，继续测试业务方法
            if get_or_create_stats:
                business_tests = [
                    ("增加会话计数", lambda: self.test_increment_session_count(get_or_create_stats)),
                    ("增加消息计数", lambda: self.test_increment_message_count(get_or_create_stats)),
                    ("更新最后活跃时间", lambda: self.test_update_last_active_time(get_or_create_stats)),
                ]
                
                current_stats = get_or_create_stats
                for test_name, test_func in business_tests:
                    try:
                        logger.info(f"\n📋 测试: {test_name}")
                        if test_name in ["增加会话计数", "增加消息计数"]:
                            current_stats = await test_func()
                        else:
                            await test_func()
                        passed += 1
                    except Exception as e:
                        logger.error(f"❌ 测试 '{test_name}' 失败: {e}")
                        failed += 1
            
        finally:
            # 清理测试数据
            await self.cleanup_test_data()
        
        # 输出测试结果
        total = passed + failed
        logger.info(f"\n📊 测试结果统计:")
        logger.info(f"✅ 通过: {passed}")
        logger.info(f"❌ 失败: {failed}")
        logger.info(f"📈 成功率: {passed/total*100:.1f}%" if total > 0 else "📈 成功率: 0%")
        
        return failed == 0


async def main():
    """主函数"""
    try:
        # 加载配置
        settings = get_settings()
        
        # 检查Supabase配置
        if not settings.database.supabase_url or not settings.database.supabase_key:
            logger.error("❌ Supabase配置不完整，请检查环境变量:")
            logger.error("  - SUPABASE_URL")
            logger.error("  - SUPABASE_KEY")
            return False
        
        logger.info("🔧 初始化测试环境...")
        logger.info(f"Supabase URL: {settings.database.supabase_url}")
        
        # 创建Supabase管理器
        supabase_manager = SupabaseManager(settings.database)
        
        # 创建测试套件
        test_suite = UserActivityStatsRepositoryV2TestSuite(supabase_manager)
        
        # 初始化测试环境
        await test_suite.initialize()
        
        # 运行所有测试
        success = await test_suite.run_all_tests()
        
        # 关闭连接
        await supabase_manager.close()
        
        print("=" * 80)
        if success:
            logger.info("🎉 UserActivityStatsRepositoryV2测试全部通过！Repository工作正常。")
            return True
        else:
            logger.error("💥 部分测试失败，请检查Repository实现。")
            return False
        
    except Exception as e:
        logger.error(f"测试过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 