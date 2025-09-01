#!/usr/bin/env python3
"""
图像服务功能测试
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.app import Application
from src.utils.config.settings import get_settings
from src.domain.services.image_service import ImageGenerationParams, ImageStatus


async def test_image_service():
    """测试图像服务"""
    print("🧪 开始图像服务功能测试...")
    
    # 加载设置
    settings = get_settings()
    
    # 初始化应用
    app = Application(settings)
    await app.initialize()
    
    try:
        # 获取服务
        image_service = app.container.get("image_service")
        user_service = app.container.get("user_service")
        
        # 创建测试用户
        test_user_id = 12345
        registration_result = await user_service.register_user(
            user_id=test_user_id,
            username="test_image_user",
            full_name="图像测试用户"
        )
        
        if not registration_result["success"]:
            print(f"❌ 用户注册失败: {registration_result.get('error')}")
            return
        
        # 给用户添加积分
        await user_service.add_credits(test_user_id, 100, "测试积分")
        
        print("✅ 测试用户创建成功")
        
        # 测试1: 参数验证
        print("\n📝 测试1: 参数验证")
        
        # 测试有效参数
        valid_params = ImageGenerationParams(
            body_type="normal",
            breast_size="normal",
            butt_size="normal",
            cloth="naked",
            age="20"
        )
        
        errors = await image_service.validate_image_params(valid_params)
        if not errors:
            print("✅ 有效参数验证通过")
        else:
            print(f"❌ 有效参数验证失败: {errors}")
        
        # 测试无效参数
        invalid_params = ImageGenerationParams(
            body_type="invalid",
            breast_size="huge",
            butt_size="gigantic",
            cloth="armor",
            age="15"
        )
        
        errors = await image_service.validate_image_params(invalid_params)
        if errors:
            print(f"✅ 无效参数正确被拒绝: {len(errors)}个错误")
        else:
            print("❌ 无效参数验证失败")
        
        # 测试2: 成本计算
        print("\n💰 测试2: 成本计算")
        
        # 基础成本
        basic_cost = await image_service.calculate_cost(ImageGenerationParams())
        print(f"✅ 基础成本: {basic_cost}")
        
        # 复杂参数成本
        complex_params = ImageGenerationParams(
            body_type="curvy",
            cloth="bikini", 
            pose="sitting"
        )
        complex_cost = await image_service.calculate_cost(complex_params)
        print(f"✅ 复杂参数成本: {complex_cost}")
        
        if complex_cost > basic_cost:
            print("✅ 成本计算正确")
        else:
            print("❌ 成本计算可能有误")
        
        # 测试3: 任务创建
        print("\n🎨 测试3: 任务创建")
        
        task_result = await image_service.create_image_task(
            user_id=test_user_id,
            params=valid_params
        )
        
        if task_result["success"]:
            task_id = task_result["task_id"]
            print(f"✅ 任务创建成功: {task_id}")
            print(f"   成本: {task_result['credits_cost']}")
            print(f"   状态: {task_result['status']}")
        else:
            print(f"❌ 任务创建失败: {task_result.get('error')}")
            return
        
        # 测试4: 任务查询
        print("\n🔍 测试4: 任务查询")
        
        task_info = await image_service.get_task_info(task_id)
        if task_info:
            print(f"✅ 任务查询成功:")
            print(f"   任务ID: {task_info.task_id}")
            print(f"   用户ID: {task_info.user_id}")
            print(f"   状态: {task_info.status}")
            print(f"   成本: {task_info.credits_cost}")
        else:
            print("❌ 任务查询失败")
        
        # 测试5: 状态更新
        print("\n🔄 测试5: 状态更新")
        
        # 开始处理
        success = await image_service.start_processing(task_id)
        if success:
            print("✅ 任务状态更新为处理中")
        else:
            print("❌ 状态更新失败")
        
        # 验证状态
        task_info = await image_service.get_task_info(task_id)
        if task_info and task_info.status == ImageStatus.PROCESSING.value:
            print("✅ 状态验证成功")
        else:
            print("❌ 状态验证失败")
        
        # 完成任务
        success = await image_service.complete_task(task_id, "/path/to/result.jpg")
        if success:
            print("✅ 任务完成")
        else:
            print("❌ 任务完成失败")
        
        # 测试6: 任务历史
        print("\n📊 测试6: 任务历史")
        
        history = await image_service.get_user_task_history(test_user_id)
        if history:
            print(f"✅ 获取到 {len(history)} 个历史任务")
            for task in history:
                print(f"   - {task.task_id}: {task.status}")
        else:
            print("❌ 历史任务获取失败")
        
        # 测试7: 任务统计
        print("\n📈 测试7: 任务统计")
        
        stats = await image_service.get_task_statistics(test_user_id)
        print(f"✅ 任务统计:")
        print(f"   总任务数: {stats['total_tasks']}")
        print(f"   已完成: {stats['completed_tasks']}")
        print(f"   失败: {stats['failed_tasks']}")
        print(f"   待处理: {stats['pending_tasks']}")
        print(f"   总消费积分: {stats['total_credits_spent']}")
        
        # 测试8: 创建失败任务
        print("\n❌ 测试8: 任务失败处理")
        
        # 创建另一个任务用于测试失败
        task_result2 = await image_service.create_image_task(
            user_id=test_user_id,
            params=valid_params
        )
        
        if task_result2["success"]:
            task_id2 = task_result2["task_id"]
            # 直接设置失败
            success = await image_service.fail_task(task_id2, "测试失败消息")
            if success:
                print("✅ 任务失败处理成功")
                
                # 验证错误信息
                failed_task = await image_service.get_task_info(task_id2)
                if failed_task and failed_task.error_message:
                    print(f"✅ 错误信息记录成功: {failed_task.error_message}")
                else:
                    print("❌ 错误信息记录失败")
            else:
                print("❌ 任务失败处理失败")
        
        print("\n🎉 所有测试完成!")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理工作 - 由于没有shutdown方法，可以跳过
        pass


if __name__ == "__main__":
    asyncio.run(test_image_service()) 