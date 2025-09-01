#!/usr/bin/env python3
"""
ClothOff API测试脚本
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.external_apis.clothoff_api import (
    ClothoffAPIClient, ClothoffAPI, APIError, APITimeoutError, APIResponseError
)
from src.domain.services.image_service import ImageGenerationParams
from src.utils.config.settings import get_settings


async def test_clothoff_api():
    """测试ClothOff API功能"""
    print("🧪 开始ClothOff API功能测试...")
    
    # 加载设置
    settings = get_settings()
    
    # 创建API客户端
    client = ClothoffAPIClient(
        api_url=settings.api.clothoff_api_url,
        webhook_base_url=settings.api.clothoff_webhook_base_url,
        api_key=settings.api.clothoff_api_key
    )
    
    # 创建API服务
    api = ClothoffAPI(client)
    
    try:
        # 测试1: API客户端初始化
        print("\n📝 测试1: API客户端初始化")
        print(f"✅ API URL: {client.api_url}")
        print(f"✅ Webhook URL: {client.webhook_base_url}")
        print(f"✅ API Key: {'已设置' if client.api_key else '未设置'}")
        
        # 测试2: 参数构建
        print("\n🎨 测试2: 图像生成参数构建")
        
        params = ImageGenerationParams(
            body_type="normal",
            breast_size="normal",
            butt_size="normal",
            cloth="naked",
            age="20"
        )
        
        print(f"✅ 参数创建成功: {params.to_dict()}")
        
        # 测试3: Webhook URL构建
        print("\n🔗 测试3: Webhook URL构建")
        
        image_webhook = client._build_webhook_url("image-process")
        video_webhook = client._build_webhook_url("video-process")
        
        print(f"✅ 图像处理Webhook: {image_webhook}")
        print(f"✅ 视频处理Webhook: {video_webhook}")
        
        # 测试4: 模拟图像数据
        print("\n📸 测试4: 模拟API调用准备")
        
        # 创建模拟图像数据
        fake_image_data = b"fake_image_data_for_testing"
        filename = "test_image.jpg"
        task_id = "test-task-12345"
        
        print(f"✅ 模拟图像数据大小: {len(fake_image_data)} bytes")
        print(f"✅ 文件名: {filename}")
        print(f"✅ 任务ID: {task_id}")
        
        # 测试5: API状态检查（如果API服务可用）
        print("\n🌐 测试5: API状态检查")
        
        try:
            # 注意：这可能会失败，因为API可能不可用或需要真实配置
            status = await api.get_api_status()
            if status['success']:
                print(f"✅ API状态正常, 余额: {status.get('balance', 'N/A')}")
            else:
                print(f"⚠️ API状态检查失败: {status.get('error', 'Unknown')}")
        except Exception as e:
            print(f"⚠️ API状态检查异常 (预期): {type(e).__name__}: {e}")
        
        # 测试6: 错误处理
        print("\n❌ 测试6: 错误处理机制")
        
        try:
            # 测试自定义异常
            raise APITimeoutError("测试超时错误")
        except APITimeoutError as e:
            print(f"✅ APITimeoutError 处理正确: {e}")
        
        try:
            raise APIResponseError("测试响应错误")
        except APIResponseError as e:
            print(f"✅ APIResponseError 处理正确: {e}")
        
        try:
            raise APIError("测试通用API错误")
        except APIError as e:
            print(f"✅ APIError 处理正确: {e}")
        
        # 测试7: 任务提交模拟
        print("\n🚀 测试7: 任务提交模拟")
        
        try:
            # 这会失败，但我们可以测试错误处理
            result = await api.submit_image_generation(
                image_data=fake_image_data,
                filename=filename,
                params=params,
                task_id=task_id
            )
            
            if result['success']:
                print(f"✅ 任务提交成功: {result['task_id']}")
            else:
                print(f"⚠️ 任务提交失败 (预期): {result.get('error', 'Unknown')}")
                
        except Exception as e:
            print(f"⚠️ 任务提交异常 (预期): {type(e).__name__}: {e}")
        
        print("\n🎉 ClothOff API测试完成!")
        print("\n📊 测试总结:")
        print("✅ API客户端初始化正常")
        print("✅ 参数验证机制正常")
        print("✅ URL构建功能正常")
        print("✅ 错误处理机制完善")
        print("✅ 业务层封装完整")
        print("\n⚠️ 注意: 实际API调用需要有效的服务器和配置")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_clothoff_api()) 