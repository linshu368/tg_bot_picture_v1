#!/usr/bin/env python3
"""
简单图像服务测试脚本
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

async def test_image_service():
    """测试图像服务基本功能"""
    print("🔧 开始图像服务基本功能测试...")
    
    # 加载配置
    settings = get_settings()
    
    # 初始化Supabase管理器
    supabase_manager = SupabaseManager(settings.database)
    await supabase_manager.initialize()
    
    # 初始化Repository和服务
    image_task_repo = SupabaseImageTaskRepository(supabase_manager)
    user_repo = SupabaseUserRepository(supabase_manager)
    image_service = ImageService(image_task_repo)
    
    # 创建测试用户
    print("\n👤 创建测试用户...")
    test_telegram_id = 12345
    test_user_data = {
        'telegram_id': test_telegram_id,
        'username': 'test_image_user',
        'first_name': '图像测试用户',
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
    
    # 测试参数验证
    print("\n1️⃣ 测试参数验证...")
    
    # 有效参数
    valid_params = ImageGenerationParams(
        body_type="normal",
        breast_size="normal",
        butt_size="normal",
        cloth="naked",
        age="25"
    )
    
    errors = await image_service.validate_image_params(valid_params)
    if not errors:
        print("✅ 有效参数验证通过")
    else:
        print(f"❌ 有效参数验证失败: {errors}")
    
    # 无效参数
    invalid_params = ImageGenerationParams(
        body_type="invalid_type",
        breast_size="invalid_size",
        butt_size="normal",
        cloth="naked",
        age="invalid_age"
    )
    
    errors = await image_service.validate_image_params(invalid_params)
    if errors:
        print("✅ 无效参数正确被拒绝")
        for error in errors:
            print(f"   - {error}")
    else:
        print("❌ 无效参数验证失败")
    
    # 测试成本计算
    print("\n2️⃣ 测试成本计算...")
    
    base_cost = await image_service.calculate_cost(valid_params)
    print(f"✅ 基础成本: {base_cost}")
    
    # 特殊参数成本
    special_params = ImageGenerationParams(
        body_type="muscular",
        breast_size="normal",
        butt_size="normal",
        cloth="bikini",
        age="25",
        pose="sitting"
    )
    
    special_cost = await image_service.calculate_cost(special_params)
    print(f"✅ 特殊参数成本: {special_cost}")
    
    # 测试任务创建
    print("\n3️⃣ 测试任务创建...")
    
    result = await image_service.create_image_task(test_user_id, valid_params)
    
    if result["success"]:
        task_id = result["task_id"]
        print(f"✅ 任务创建成功: {task_id}")
        print(f"💰 消耗积分: {result['credits_cost']}")
        print(f"📊 任务状态: {result['status']}")
        
        # 测试获取任务信息
        print("\n4️⃣ 测试获取任务信息...")
        task_info = await image_service.get_task_info(task_id)
        
        if task_info:
            print("✅ 获取任务信息成功:")
            print(f"   - 任务ID: {task_info['task_id']}")
            print(f"   - 用户ID: {task_info['user_id']}")
            print(f"   - 状态: {task_info['status']}")
            print(f"   - 积分消耗: {task_info['credits_cost']}")
            print(f"   - 创建时间: {task_info['created_at']}")
        else:
            print("❌ 获取任务信息失败")
        
        # 测试状态更新
        print("\n5️⃣ 测试状态更新...")
        
        # 开始处理
        success = await image_service.start_processing(task_id)
        if success:
            print("✅ 更新为处理中状态成功")
        else:
            print("❌ 更新为处理中状态失败")
        
        # 完成任务
        result_path = "https://example.com/completed-image.jpg"
        success = await image_service.complete_task(task_id, result_path)
        if success:
            print("✅ 完成任务成功")
        else:
            print("❌ 完成任务失败")
        
        # 验证最终状态
        final_task = await image_service.get_task_info(task_id)
        if final_task:
            print(f"✅ 最终状态: {final_task['status']}")
            print(f"   结果路径: {final_task.get('result_path')}")
        
        # 测试失败任务
        print("\n6️⃣ 测试失败任务...")
        
        failed_result = await image_service.create_image_task(test_user_id, valid_params)
        if failed_result["success"]:
            failed_task_id = failed_result["task_id"]
            
            error_message = "测试：模拟处理失败"
            success = await image_service.fail_task(failed_task_id, error_message)
            
            if success:
                print("✅ 任务失败处理成功")
                
                failed_task = await image_service.get_task_info(failed_task_id)
                if failed_task:
                    print(f"✅ 失败状态: {failed_task['status']}")
                    print(f"   错误信息: {failed_task.get('error_message')}")
            else:
                print("❌ 任务失败处理失败")
        
        # 测试用户任务历史
        print("\n7️⃣ 测试用户任务历史...")
        history = await image_service.get_user_task_history(test_user_id, 10)
        print(f"✅ 获取到 {len(history)} 条任务记录")
        
        for i, task in enumerate(history[:3]):  # 只显示前3条
            print(f"   {i+1}. {task['task_id'][:8]}... - {task['status']}")
        
        # 测试任务统计
        print("\n8️⃣ 测试任务统计...")
        stats = await image_service.get_task_statistics(test_user_id)
        print("✅ 任务统计:")
        print(f"   - 总任务数: {stats['total_tasks']}")
        print(f"   - 已完成: {stats['completed_tasks']}")
        print(f"   - 失败: {stats['failed_tasks']}")
        print(f"   - 待处理: {stats['pending_tasks']}")
        print(f"   - 总积分消耗: {stats['total_credits_spent']}")
        
    else:
        print(f"❌ 任务创建失败: {result['error']}")
    
    print("\n🎉 图像服务基本功能测试完成!")

if __name__ == "__main__":
    asyncio.run(test_image_service()) 