#!/usr/bin/env python3
"""
Supabase连接测试脚本
验证Supabase配置和基本操作是否正常
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

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


class SupabaseTestSuite:
    """Supabase测试套件"""
    
    def __init__(self, supabase_manager: SupabaseManager):
        self.supabase_manager = supabase_manager
        self.user_repo = None
        self.point_repo = None
        self.test_user_id = None
        
    async def initialize(self):
        """初始化测试环境"""
        try:
            await self.supabase_manager.initialize()
            self.user_repo = SupabaseUserRepository(self.supabase_manager)
            self.point_repo = SupabasePointRecordRepository(self.supabase_manager)
            logger.info("测试环境初始化完成")
        except Exception as e:
            logger.error(f"测试环境初始化失败: {e}")
            raise
    
    async def test_connection(self):
        """测试Supabase连接"""
        logger.info("测试Supabase连接...")
        
        try:
            client = self.supabase_manager.get_client()
            
            # 使用与supabase_manager.py相同的测试方式
            try:
                # 尝试查询一个不存在的表，如果连接正常会返回表不存在的错误
                result = client.table('test_connection_table').select('*').limit(1).execute()
            except Exception as e:
                # 如果错误信息包含表不存在，说明连接是正常的
                if "does not exist" in str(e).lower() or "not found" in str(e).lower():
                    logger.info("✅ Supabase连接测试通过")
                    return True
                else:
                    logger.error(f"❌ Supabase连接测试失败: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Supabase连接测试失败: {e}")
            return False
    
    async def test_create_user(self):
        """测试创建用户"""
        logger.info("测试创建用户...")
        
        try:
            # 测试用户数据
            test_user_data = {
                'telegram_id': 999999999,  # 测试用的Telegram ID
                'username': 'test_user',
                'first_name': 'Test',
                'last_name': 'User',
                'utm_source': 'test'
            }
            
            # 检查用户是否已存在
            existing_user = await self.user_repo.get_by_telegram_id(test_user_data['telegram_id'])
            if existing_user:
                logger.info("测试用户已存在，删除后重新创建...")
                await self.user_repo.delete(existing_user['id'], hard_delete=True)
            
            # 创建用户
            created_user = await self.user_repo.create(test_user_data)
            
            if created_user and 'id' in created_user:
                self.test_user_id = created_user['id']
                logger.info(f"✅ 用户创建测试通过: uid={created_user.get('uid')}")
                return True
            else:
                logger.error("❌ 用户创建测试失败：未返回有效数据")
                return False
                
        except Exception as e:
            logger.error(f"❌ 用户创建测试失败: {e}")
            return False
    
    async def test_get_user(self):
        """测试获取用户"""
        logger.info("测试获取用户...")
        
        if not self.test_user_id:
            logger.error("❌ 获取用户测试失败：没有测试用户ID")
            return False
        
        try:
            # 通过ID获取用户
            user_by_id = await self.user_repo.get_by_id(self.test_user_id)
            if not user_by_id:
                logger.error("❌ 通过ID获取用户失败")
                return False
            
            # 通过Telegram ID获取用户
            user_by_telegram_id = await self.user_repo.get_by_telegram_id(999999999)
            if not user_by_telegram_id:
                logger.error("❌ 通过Telegram ID获取用户失败")
                return False
            
            # 通过UID获取用户
            user_by_uid = await self.user_repo.get_by_uid(user_by_id['uid'])
            if not user_by_uid:
                logger.error("❌ 通过UID获取用户失败")
                return False
            
            logger.info("✅ 用户获取测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 用户获取测试失败: {e}")
            return False
    
    async def test_update_user(self):
        """测试更新用户"""
        logger.info("测试更新用户...")
        
        if not self.test_user_id:
            logger.error("❌ 更新用户测试失败：没有测试用户ID")
            return False
        
        try:
            # 更新用户数据
            update_data = {
                'first_name': 'Updated_Test',
                'points': 100,
                'level': 2
            }
            
            result = await self.user_repo.update(self.test_user_id, update_data)
            if not result:
                logger.error("❌ 用户更新失败")
                return False
            
            # 验证更新结果
            updated_user = await self.user_repo.get_by_id(self.test_user_id)
            if (updated_user['first_name'] == 'Updated_Test' and 
                updated_user['points'] == 100 and 
                updated_user['level'] == 2):
                logger.info("✅ 用户更新测试通过")
                return True
            else:
                logger.error("❌ 用户更新验证失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 用户更新测试失败: {e}")
            return False
    
    async def test_point_operations(self):
        """测试积分操作"""
        logger.info("测试积分操作...")
        
        if not self.test_user_id:
            logger.error("❌ 积分操作测试失败：没有测试用户ID")
            return False
        
        try:
            # 增加积分
            add_result = await self.user_repo.add_points(self.test_user_id, 50)
            if not add_result:
                logger.error("❌ 增加积分失败")
                return False
            
            # 验证积分增加
            user = await self.user_repo.get_by_id(self.test_user_id)
            if user['points'] != 150:  # 原来100 + 50
                logger.error(f"❌ 积分增加验证失败：期望150，实际{user['points']}")
                return False
            
            # 扣除积分
            subtract_result = await self.user_repo.subtract_points(self.test_user_id, 25)
            if not subtract_result:
                logger.error("❌ 扣除积分失败")
                return False
            
            # 验证积分扣除
            user = await self.user_repo.get_by_id(self.test_user_id)
            if user['points'] != 125:  # 150 - 25
                logger.error(f"❌ 积分扣除验证失败：期望125，实际{user['points']}")
                return False
            
            logger.info("✅ 积分操作测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 积分操作测试失败: {e}")
            return False
    
    async def test_point_records(self):
        """测试积分记录"""
        logger.info("测试积分记录...")
        
        if not self.test_user_id:
            logger.error("❌ 积分记录测试失败：没有测试用户ID")
            return False
        
        try:
            # 创建积分记录
            record_data = {
                'user_id': self.test_user_id,
                'points_change': 10,
                'action_type': 'test_action',
                'description': '测试积分记录',
                'points_balance': 135
            }
            
            created_record = await self.point_repo.create(record_data)
            if not created_record or 'id' not in created_record:
                logger.error("❌ 创建积分记录失败")
                return False
            
            record_id = created_record['id']
            
            # 获取积分记录
            retrieved_record = await self.point_repo.get_by_id(record_id)
            if not retrieved_record:
                logger.error("❌ 获取积分记录失败")
                return False
            
            # 获取用户的积分记录列表
            user_records = await self.point_repo.get_user_records(self.test_user_id, limit=10)
            if not user_records:
                logger.error("❌ 获取用户积分记录列表失败")
                return False
            
            logger.info(f"✅ 积分记录测试通过，记录数量: {len(user_records)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 积分记录测试失败: {e}")
            return False
    
    async def test_query_operations(self):
        """测试查询操作"""
        logger.info("测试查询操作...")
        
        try:
            # 获取活跃用户
            active_users = await self.user_repo.get_active_users(limit=5)
            logger.info(f"活跃用户数量: {len(active_users)}")
            
            # 用户统计
            if self.test_user_id:
                stats = await self.point_repo.get_user_total_stats(self.test_user_id)
                logger.info(f"用户积分统计: {stats}")
            
            # 计算记录数量
            if self.test_user_id:
                count = await self.point_repo.count(user_id=self.test_user_id)
                logger.info(f"用户积分记录数量: {count}")
            
            logger.info("✅ 查询操作测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 查询操作测试失败: {e}")
            return False
    
    async def cleanup_test_data(self):
        """清理测试数据"""
        logger.info("清理测试数据...")
        
        try:
            if self.test_user_id:
                # 删除测试用户（这会级联删除相关的积分记录）
                await self.user_repo.delete(self.test_user_id, hard_delete=True)
                logger.info("✅ 测试数据清理完成")
            
        except Exception as e:
            logger.error(f"❌ 测试数据清理失败: {e}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始Supabase完整测试...")
        
        tests = [
            ("连接测试", self.test_connection),
            ("创建用户测试", self.test_create_user),
            ("获取用户测试", self.test_get_user),
            ("更新用户测试", self.test_update_user),
            ("积分操作测试", self.test_point_operations),
            ("积分记录测试", self.test_point_records),
            ("查询操作测试", self.test_query_operations),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"测试 '{test_name}' 执行异常: {e}")
                failed += 1
        
        # 清理测试数据
        await self.cleanup_test_data()
        
        # 输出测试结果
        logger.info(f"\n📊 测试结果统计:")
        logger.info(f"✅ 通过: {passed}")
        logger.info(f"❌ 失败: {failed}")
        logger.info(f"📈 成功率: {passed/(passed+failed)*100:.1f}%")
        
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
            return
        
        # 创建Supabase管理器
        supabase_manager = SupabaseManager(settings.database)
        
        # 创建测试套件
        test_suite = SupabaseTestSuite(supabase_manager)
        
        # 初始化测试环境
        await test_suite.initialize()
        
        # 运行所有测试
        success = await test_suite.run_all_tests()
        
        # 关闭连接
        await supabase_manager.close()
        
        if success:
            logger.info("🎉 所有测试通过！Supabase配置正确。")
            sys.exit(0)
        else:
            logger.error("💥 部分测试失败，请检查配置和网络连接。")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"测试过程出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 