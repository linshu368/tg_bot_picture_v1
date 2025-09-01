#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库功能测试脚本
测试重构后的数据库层功能
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_database_basic():
    """测试数据库基础功能"""
    try:
        from src.utils.config.settings import get_settings
        from src.infrastructure.database.manager import DatabaseManager
        from src.infrastructure.database.repositories import UserRepository, PointRecordRepository
        
        # 获取配置
        settings = get_settings()
        print("✅ 配置加载成功")
        
        # 创建数据库管理器
        db_manager = DatabaseManager(settings.database)
        await db_manager.initialize()
        print("✅ 数据库初始化成功")
        
        # 创建Repository
        user_repo = UserRepository(db_manager)
        point_repo = PointRecordRepository(db_manager)
        print("✅ Repository创建成功")
        
        return db_manager, user_repo, point_repo
        
    except Exception as e:
        print(f"❌ 数据库基础功能测试失败: {e}")
        raise

async def test_user_operations(user_repo):
    """测试用户操作"""
    try:
        # 测试创建用户
        test_user_data = {
            'telegram_id': 123456789,
            'username': 'test_user',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        user = await user_repo.create(test_user_data)
        print(f"✅ 用户创建成功: {user['uid']}")
        
        # 测试根据telegram_id查询用户
        found_user = await user_repo.get_by_telegram_id(123456789)
        assert found_user is not None
        assert found_user['username'] == 'test_user'
        print("✅ 用户查询成功")
        
        # 测试更新用户
        update_result = await user_repo.update(user['id'], {'points': 100})
        assert update_result is True
        print("✅ 用户更新成功")
        
        # 测试用户绑定 - 创建新的UID进行测试
        new_uid = user_repo.generate_uid()
        # 先创建一个新用户作为绑定目标
        test_user_data2 = {
            'telegram_id': 987654321,
            'username': 'test_user2',
            'first_name': 'Test2',
            'last_name': 'User2'
        }
        user2 = await user_repo.create(test_user_data2)
        
        # 测试绑定新的telegram_id到现有UID
        bind_result = await user_repo.bind_user_to_uid(111111111, user2['uid'])
        assert bind_result is True
        print("✅ 用户绑定成功")
        
        return user
        
    except Exception as e:
        print(f"❌ 用户操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise

async def test_point_operations(point_repo, user):
    """测试积分操作"""
    try:
        # 测试创建积分记录
        point_data = {
            'user_id': user['id'],
            'points_change': 50,
            'action_type': 'registration',
            'description': '注册奖励',
            'points_balance': 150
        }
        
        point_record = await point_repo.create(point_data)
        print(f"✅ 积分记录创建成功: {point_record['id']}")
        
        # 测试获取用户积分记录
        user_records = await point_repo.get_user_records(user['id'])
        assert len(user_records) > 0
        print("✅ 积分记录查询成功")
        
        # 测试获取用户总获得积分
        try:
            total_earned = await point_repo.get_user_total_earned(user['id'])
            print(f"✅ 积分统计成功: 总获得 {total_earned}")
            # 应该至少有我们刚创建的50积分
            assert total_earned >= 50, f"期望至少50积分，但获得 {total_earned}"
        except Exception as e:
            print(f"积分统计调试信息: {e}")
            # 直接查询数据库验证
            conn = await point_repo.get_connection()
            cursor = await conn.execute("SELECT points_change FROM point_records WHERE user_id = ?", (user['id'],))
            rows = await cursor.fetchall()
            print(f"数据库中的积分记录: {rows}")
            raise
        
        return point_record
        
    except Exception as e:
        print(f"❌ 积分操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise

async def cleanup_test_data(user_repo, user):
    """清理测试数据"""
    try:
        # 软删除测试用户
        await user_repo.delete(user['id'])
        print("✅ 测试数据清理完成")
        
    except Exception as e:
        print(f"⚠️ 测试数据清理失败: {e}")

async def main():
    """主测试函数"""
    print("🚀 开始测试数据库功能...")
    print("=" * 50)
    
    db_manager = None
    user = None
    
    try:
        # 基础功能测试
        print("\n📋 测试: 数据库基础功能")
        db_manager, user_repo, point_repo = await test_database_basic()
        
        # 用户操作测试
        print("\n📋 测试: 用户操作")
        user = await test_user_operations(user_repo)
        
        # 积分操作测试
        print("\n📋 测试: 积分操作") 
        await test_point_operations(point_repo, user)
        
        print("\n" + "=" * 50)
        print("🎉 所有数据库功能测试通过！")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 数据库测试失败: {e}")
        return False
        
    finally:
        # 清理测试数据
        if user:
            try:
                await cleanup_test_data(user_repo, user)
            except:
                pass
        
        # 关闭数据库连接
        if db_manager:
            await db_manager.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 