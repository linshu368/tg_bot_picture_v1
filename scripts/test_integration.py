#!/usr/bin/env python3
"""
集成测试脚本 - 测试图像服务与数据库的集成
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.infrastructure.database.supabase_manager import SupabaseManager
from src.infrastructure.database.repositories.supabase_image_task_repository import SupabaseImageTaskRepository
from src.infrastructure.database.repositories.supabase_user_repository import SupabaseUserRepository
from src.domain.services.image_service import ImageService, ImageGenerationParams, ImageStatus
from src.utils.config.settings import get_settings

async def test_image_service_integration():
    """测试图像服务与数据库的集成"""
    print("🔧 开始图像服务集成测试...")
    
    # 加载配置
    settings = get_settings()
    
    # 初始化Supabase管理器
    supabase_manager = SupabaseManager(settings.database)
    await supabase_manager.initialize()
    
    # 初始化Repository
    image_task_repo = SupabaseImageTaskRepository(supabase_manager)
    user_repo = SupabaseUserRepository(supabase_manager)
    
    # 初始化服务
    image_service = ImageService(image_task_repo)
    
    # 创建测试用户
    print("\n👤 创建测试用户...")
    test_telegram_id = 12345
    test_user_data = {
        'telegram_id': test_telegram_id,
        'username': 'test_integration_user',
        'first_name': '集成测试用户',
        'last_name': 'Test',
        'points': 100
    }
    
    try:
        created_user = await user_repo.create(test_user_data)
        if created_user:
            test_user_id = created_user['id']
            print(f"✅ 创建测试用户成功: ID={test_user_id}")
        else:
            print("❌ 创建测试用户失败")
            return
    except Exception as e:
        # 如果用户已存在，尝试获取现有用户
        existing_user = await user_repo.find_one(telegram_id=test_telegram_id)
        if existing_user:
            test_user_id = existing_user['id']
            print(f"✅ 使用现有测试用户: ID={test_user_id}")
        else:
            print(f"❌ 无法创建或获取测试用户: {e}")
            return
    
    # 测试参数
    test_params = ImageGenerationParams(
        body_type="normal",
        breast_size="normal",
        butt_size="normal",
        cloth="naked",
        age="25",
        pose="standing"
    )
    
    print(f"📝 测试用户ID: {test_user_id}")
    print(f"📝 测试参数: {test_params.to_dict()}")
    
    # 测试1: 创建图像任务
    print("\n1️⃣ 测试创建图像任务...")
    result = await image_service.create_image_task(test_user_id, test_params)
    
    if result["success"]:
        task_id = result["task_id"]
        print(f"✅ 创建任务成功: {task_id}")
        print(f"💰 消耗积分: {result['credits_cost']}")
        
        # 测试2: 获取任务信息
        print("\n2️⃣ 测试获取任务信息...")
        task_info = await image_service.get_task_info(task_id)
        
        if task_info:
            print(f"✅ 获取任务信息成功:")
            print(f"   - 状态: {task_info['status']}")
            print(f"   - 用户ID: {task_info['user_id']}")
            print(f"   - 积分消耗: {task_info['credits_cost']}")
        else:
            print("❌ 获取任务信息失败")
        
        # 测试3: 更新任务状态
        print("\n3️⃣ 测试更新任务状态...")
        success = await image_service.start_processing(task_id)
        if success:
            print("✅ 更新任务状态为处理中成功")
        else:
            print("❌ 更新任务状态失败")
        
        # 测试4: 完成任务
        print("\n4️⃣ 测试完成任务...")
        result_path = "https://example.com/test-image.jpg"
        success = await image_service.complete_task(task_id, result_path)
        if success:
            print("✅ 完成任务成功")
        else:
            print("❌ 完成任务失败")
        
        # 测试5: 获取用户任务历史
        print("\n5️⃣ 测试获取用户任务历史...")
        history = await image_service.get_user_task_history(test_user_id, 5)
        print(f"✅ 获取到 {len(history)} 条任务记录")
        
        # 测试6: 获取任务统计
        print("\n6️⃣ 测试获取任务统计...")
        stats = await image_service.get_task_statistics(test_user_id)
        print(f"✅ 任务统计:")
        print(f"   - 总任务数: {stats['total_tasks']}")
        print(f"   - 已完成: {stats['completed_tasks']}")
        print(f"   - 失败: {stats['failed_tasks']}")
        print(f"   - 待处理: {stats['pending_tasks']}")
        print(f"   - 总积分消耗: {stats['total_credits_spent']}")
        
    else:
        print(f"❌ 创建任务失败: {result['error']}")
    
    print("\n🎉 集成测试完成!")

if __name__ == "__main__":
    asyncio.run(test_image_service_integration()) 