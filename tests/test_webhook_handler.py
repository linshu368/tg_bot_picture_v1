#!/usr/bin/env python3
"""
Webhook处理器测试脚本
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.infrastructure.database.supabase_manager import SupabaseManager
from src.infrastructure.database.repositories.supabase_image_task_repository import SupabaseImageTaskRepository
from src.infrastructure.database.repositories.supabase_user_repository import SupabaseUserRepository
from src.domain.services.image_service import ImageService, ImageGenerationParams
from src.infrastructure.messaging.webhook_handler import WebhookHandler, WebhookProcessor
from src.utils.config.settings import get_settings

async def test_webhook_handler():
    """测试Webhook处理器"""
    print("🔧 开始Webhook处理器测试...")
    
    # 加载配置
    settings = get_settings()
    
    # 初始化Supabase管理器
    supabase_manager = SupabaseManager(settings.database)
    await supabase_manager.initialize()
    
    # 初始化Repository和服务
    image_task_repo = SupabaseImageTaskRepository(supabase_manager)
    user_repo = SupabaseUserRepository(supabase_manager)
    image_service = ImageService(image_task_repo)
    webhook_handler = WebhookHandler(image_service)
    webhook_processor = WebhookProcessor(webhook_handler)
    
    # 创建测试用户
    print("\n👤 创建测试用户...")
    test_telegram_id = 12345
    test_user_data = {
        'telegram_id': test_telegram_id,
        'username': 'test_webhook_user',
        'first_name': 'Webhook测试用户',
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
        age="25"
    )
    
    print(f"📝 测试用户ID: {test_user_id}")
    
    # 创建测试任务
    print("\n1️⃣ 创建测试任务...")
    result = await image_service.create_image_task(test_user_id, test_params)
    
    if not result["success"]:
        print(f"❌ 创建任务失败: {result['error']}")
        return
    
    task_id = result["task_id"]
    print(f"✅ 创建任务成功: {task_id}")
    
    # 测试成功的Webhook回调
    print("\n2️⃣ 测试成功的Webhook回调...")
    success_callback_data = {
        'id_gen': task_id,
        'status': '200',
        'result_url': f'https://example.com/results/{task_id}_completed.jpg',
        'time_gen': '2024-01-01 12:00:00'
    }
    
    callback_result = await webhook_processor.process_clothoff_callback(
        success_callback_data,
        "image"
    )
    
    if callback_result['success']:
        print("✅ 成功回调处理正确")
        print(f"   结果路径: {callback_result.get('result_path')}")
    else:
        print(f"❌ 成功回调处理失败: {callback_result.get('error')}")
    
    # 验证任务状态
    task_info = await image_service.get_task_info(task_id)
    if task_info:
        print(f"✅ 任务状态: {task_info['status']}")
        print(f"   结果路径: {task_info.get('result_path')}")
    
    # 测试失败的Webhook回调
    print("\n3️⃣ 测试失败的Webhook回调...")
    
    # 创建另一个任务用于测试失败
    failed_result = await image_service.create_image_task(test_user_id, test_params)
    if failed_result["success"]:
        failed_task_id = failed_result["task_id"]
        
        failed_callback_data = {
            'id_gen': failed_task_id,
            'status': '500',
            'img_message': '测试：模拟API处理失败',
            'time_gen': '2024-01-01 12:05:00'
        }
        
        failed_callback_result = await webhook_processor.process_clothoff_callback(
            failed_callback_data,
            "image"
        )
        
        if failed_callback_result['success']:
            print("✅ 失败回调处理正确")
            
            # 验证失败任务状态
            failed_task_info = await image_service.get_task_info(failed_task_id)
            if failed_task_info:
                print(f"✅ 失败任务状态: {failed_task_info['status']}")
                print(f"   错误信息: {failed_task_info.get('error_message')}")
        else:
            print(f"❌ 失败回调处理异常: {failed_callback_result.get('error')}")
    
    print("\n🎉 Webhook处理器测试完成!")

if __name__ == "__main__":
    asyncio.run(test_webhook_handler()) 