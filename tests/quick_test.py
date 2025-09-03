#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试脚本
验证新架构的基础组件是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    """测试模块导入"""
    try:
        from src.utils.config.settings import get_settings
        from src.core.container import setup_container
        from src.core.lifecycle import LifecycleManager
        print("✅ 所有核心模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_configuration():
    """测试配置系统"""
    try:
        from src.utils.config.settings import get_settings
        settings = get_settings()
        
        # 检查关键配置
        assert hasattr(settings, 'bot')
        assert hasattr(settings, 'database')
        assert hasattr(settings, 'api')
        assert hasattr(settings, 'payment')
        assert hasattr(settings, 'credit')
        
        print("✅ 配置系统正常工作")
        print(f"   - Bot Token: {settings.bot.token[:10]}...")
        print(f"   - 数据库: Supabase ({settings.database.supabase_url})")
        print(f"   - 管理员ID: {settings.bot.admin_user_id}")
        return True
    except Exception as e:
        print(f"❌ 配置系统测试失败: {e}")
        return False

def test_dependency_injection():
    """测试依赖注入"""
    try:
        from src.utils.config.settings import get_settings
        from src.core.container import setup_container
        
        settings = get_settings()
        container = setup_container(settings)
        
        # 检查服务注册
        assert container.has("settings")
        assert container.has("database_manager")
        
        print("✅ 依赖注入容器正常工作")
        print(f"   - 已注册服务数量: {len(container._factories) + len(container._singletons)}")
        return True
    except Exception as e:
        print(f"❌ 依赖注入测试失败: {e}")
        return False

def test_lifecycle():
    """测试生命周期管理"""
    try:
        from src.core.lifecycle import LifecycleManager
        
        lifecycle = LifecycleManager()
        
        # 注册测试钩子
        def test_hook():
            pass
        
        lifecycle.register_startup_hook(test_hook)
        lifecycle.register_shutdown_hook(test_hook)
        
        assert len(lifecycle.startup_hooks) == 1
        assert len(lifecycle.shutdown_hooks) == 1
        
        print("✅ 生命周期管理器正常工作")
        return True
    except Exception as e:
        print(f"❌ 生命周期测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("🚀 开始测试新架构基础组件...")
    print("=" * 50)
    
    tests = [
        ("模块导入", test_imports),
        ("配置系统", test_configuration), 
        ("依赖注入", test_dependency_injection),
        ("生命周期", test_lifecycle)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 测试: {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"   跳过后续测试...")
            break
    
    print("\n" + "=" * 50)
    print(f"🎯 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有基础组件测试通过！新架构框架工作正常。")
        print("\n📝 下一步建议:")
        print("   1. 设置您的Bot Token在 .env 文件中")
        print("   2. 开始实现数据库层 (src/infrastructure/database/)")
        print("   3. 实现业务服务层 (src/domain/services/)")
        return True
    else:
        print("❌ 部分测试失败，请检查代码实现。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 