#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户服务功能测试脚本
测试重构后的用户服务业务逻辑
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_user_service():
    """测试用户服务"""
    try:
        from src.utils.config.settings import get_settings
        from src.infrastructure.database.manager import DatabaseManager
        from src.domain.services.user_service import UserService
        
        # 获取配置
        settings = get_settings()
        print("✅ 配置加载成功")
        
        # 创建数据库管理器
        db_manager = DatabaseManager(settings.database)
        await db_manager.initialize()
        print("✅ 数据库初始化成功")
        
        # 创建用户服务
        user_service = UserService(db_manager, settings.credit)
        print("✅ 用户服务创建成功")
        
        return db_manager, user_service
        
    except Exception as e:
        print(f"❌ 用户服务初始化失败: {e}")
        raise

async def test_user_registration(user_service):
    """测试用户注册"""
    try:
        # 测试用户注册
        test_telegram_id = 999888777
        user = await user_service.register_user(
            telegram_id=test_telegram_id,
            username='test_service_user',
            first_name='Service',
            last_name='Test'
        )
        
        assert user is not None
        assert user['telegram_id'] == test_telegram_id
        assert user['username'] == 'test_service_user'
        print(f"✅ 用户注册成功: {user['uid']}")
        
        # 测试重复注册（应该返回现有用户）
        user2 = await user_service.register_user(
            telegram_id=test_telegram_id,
            username='test_service_user',
            first_name='Service',
            last_name='Test'
        )
        
        assert user2 is not None
        assert user2['id'] == user['id']
        print("✅ 重复注册处理正确")
        
        return user
        
    except Exception as e:
        print(f"❌ 用户注册测试失败: {e}")
        raise

async def test_points_operations(user_service, user):
    """测试积分操作"""
    try:
        user_id = user['id']
        
        # 获取初始积分
        initial_points = await user_service.get_user_points_balance(user_id)
        print(f"✅ 初始积分: {initial_points}")
        
        # 测试增加积分
        add_result = await user_service.add_points(user_id, 100, 'test', '测试增加积分')
        assert add_result is True
        
        new_balance = await user_service.get_user_points_balance(user_id)
        assert new_balance == initial_points + 100
        print(f"✅ 积分增加成功: {new_balance}")
        
        # 测试消耗积分
        consume_result = await user_service.consume_points(user_id, 50, 'test_consume', '测试消耗积分')
        assert consume_result is True
        
        final_balance = await user_service.get_user_points_balance(user_id)
        assert final_balance == new_balance - 50
        print(f"✅ 积分消耗成功: {final_balance}")
        
        # 测试积分不足的情况
        insufficient_result = await user_service.consume_points(user_id, 99999, 'test_insufficient', '测试积分不足')
        assert insufficient_result is False
        print("✅ 积分不足处理正确")
        
        # 测试积分检查
        sufficient = await user_service.check_points_sufficient(user_id, 10)
        assert sufficient is True
        
        insufficient = await user_service.check_points_sufficient(user_id, 99999)
        assert insufficient is False
        print("✅ 积分检查功能正常")
        
        return user_id
        
    except Exception as e:
        print(f"❌ 积分操作测试失败: {e}")
        raise

async def test_checkin_functionality(user_service, user_id):
    """测试签到功能"""
    try:
        # 测试签到
        checkin_result = await user_service.daily_checkin(user_id)
        assert checkin_result['success'] is True
        assert checkin_result['points_earned'] > 0
        print(f"✅ 签到成功: {checkin_result['message']}")
        
        # 测试重复签到
        checkin_result2 = await user_service.daily_checkin(user_id)
        assert checkin_result2['success'] is False
        assert checkin_result2['points_earned'] == 0
        print("✅ 重复签到处理正确")
        
    except Exception as e:
        print(f"❌ 签到功能测试失败: {e}")
        raise

async def test_user_statistics(user_service, user_id):
    """测试用户统计"""
    try:
        stats = await user_service.get_user_statistics(user_id)
        
        assert 'user_id' in stats
        assert 'telegram_id' in stats
        assert 'current_points' in stats
        assert 'total_earned' in stats
        assert 'total_spent' in stats
        
        print(f"✅ 用户统计获取成功:")
        print(f"   - 当前积分: {stats['current_points']}")
        print(f"   - 总获得: {stats['total_earned']}")
        print(f"   - 总消费: {stats['total_spent']}")
        
        # 测试积分历史
        history = await user_service.get_user_points_history(user_id, 10)
        assert isinstance(history, list)
        print(f"✅ 积分历史获取成功: {len(history)} 条记录")
        
    except Exception as e:
        print(f"❌ 用户统计测试失败: {e}")
        raise

async def test_account_binding(user_service):
    """测试账号绑定"""
    try:
        # 创建一个测试用户用于绑定测试
        test_user = await user_service.register_user(
            telegram_id=888777666,
            username='bind_test_user'
        )
        
        # 测试绑定功能
        bind_result = await user_service.bind_user_account(555444333, test_user['uid'])
        assert bind_result is True
        print("✅ 账号绑定成功")
        
        # 测试绑定不存在的UID
        bind_fail_result = await user_service.bind_user_account(222111000, 'non_existent_uid')
        assert bind_fail_result is False
        print("✅ 无效UID绑定处理正确")
        
    except Exception as e:
        print(f"❌ 账号绑定测试失败: {e}")
        raise

async def cleanup_test_data(user_service, test_user_ids):
    """清理测试数据"""
    try:
        for user_id in test_user_ids:
            await user_service.user_repo.delete(user_id)
        print("✅ 测试数据清理完成")
    except Exception as e:
        print(f"⚠️ 测试数据清理失败: {e}")

async def main():
    """主测试函数"""
    print("🚀 开始测试用户服务功能...")
    print("=" * 50)
    
    db_manager = None
    test_user_ids = []
    
    try:
        # 初始化测试
        print("\n📋 测试: 用户服务初始化")
        db_manager, user_service = await test_user_service()
        
        # 用户注册测试
        print("\n📋 测试: 用户注册")
        user = await test_user_registration(user_service)
        test_user_ids.append(user['id'])
        
        # 积分操作测试
        print("\n📋 测试: 积分操作")
        user_id = await test_points_operations(user_service, user)
        
        # 签到功能测试
        print("\n📋 测试: 签到功能")
        await test_checkin_functionality(user_service, user_id)
        
        # 用户统计测试
        print("\n📋 测试: 用户统计")
        await test_user_statistics(user_service, user_id)
        
        # 账号绑定测试
        print("\n📋 测试: 账号绑定")
        await test_account_binding(user_service)
        
        print("\n" + "=" * 50)
        print("🎉 所有用户服务功能测试通过！")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 用户服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理测试数据
        if test_user_ids:
            try:
                await cleanup_test_data(user_service, test_user_ids)
            except:
                pass
        
        # 关闭数据库连接
        if db_manager:
            await db_manager.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 