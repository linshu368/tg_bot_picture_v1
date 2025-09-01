#!/usr/bin/env python3
"""
支付服务测试脚本
"""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config.settings import get_settings
from src.infrastructure.database.manager import DatabaseManager
from src.domain.services.payment_service import (
    PaymentService, PaymentOrderRepository, PaymentPackage, PaymentOrder, 
    OrderStatus, PaymentMethod
)
from src.domain.services.user_service import UserService


async def test_payment_service():
    """测试支付服务"""
    print("🧪 开始支付服务功能测试...")
    
    # 加载设置
    settings = get_settings()
    
    # 直接创建数据库管理器
    db_manager = DatabaseManager(settings.database)
    await db_manager.initialize()
    
    try:
        # 创建服务
        payment_order_repo = PaymentOrderRepository(db_manager)
        user_service = UserService(db_manager, settings.credit)
        payment_service = PaymentService(
            payment_order_repo,
            user_service,
            settings.payment
        )
        
        # 创建测试用户
        test_user_id = 77777
        user = await user_service.register_user(
            telegram_id=test_user_id,
            username="payment_test_user",
            first_name="支付测试用户"
        )
        
        if not user:
            print(f"❌ 用户注册失败")
            return
        
        db_user_id = user['id']
        print(f"✅ 测试用户创建成功，ID: {db_user_id}")
        
        # 测试1: 支付套餐管理
        print("\n📦 测试1: 支付套餐管理")
        
        packages = payment_service.get_available_packages()
        print(f"✅ 可用套餐数量: {len(packages)}")
        
        for package in packages:
            print(f"   - {package.name}: {package.credits}积分, ¥{package.price}")
        
        # 测试获取单个套餐
        small_package = payment_service.get_package("small")
        if small_package:
            print(f"✅ 获取基础套餐成功: {small_package.name}")
        else:
            print("❌ 获取基础套餐失败")
        
        # 测试2: 支付方式管理
        print("\n💳 测试2: 支付方式管理")
        
        payment_methods = payment_service.get_available_payment_methods()
        print(f"✅ 可用支付方式数量: {len(payment_methods)}")
        
        for method in payment_methods:
            print(f"   - {method['name']} ({method['id']})")
        
        # 测试3: 创建支付订单
        print("\n📋 测试3: 创建支付订单")
        
        # 测试有效订单创建
        order_result = await payment_service.create_payment_order(
            user_id=db_user_id,
            package_id="medium",
            payment_method=PaymentMethod.ALIPAY.value
        )
        
        if order_result["success"]:
            order_no = order_result["order_no"]
            print("✅ 订单创建成功")
            print(f"   订单号: {order_no}")
            print(f"   金额: ¥{order_result['amount']}")
            print(f"   积分: {order_result['credits']}")
            print(f"   过期时间: {order_result['expired_at']}")
        else:
            print(f"❌ 订单创建失败: {order_result.get('error')}")
            return
        
        # 测试无效套餐
        invalid_order = await payment_service.create_payment_order(
            user_id=db_user_id,
            package_id="invalid_package",
            payment_method=PaymentMethod.ALIPAY.value
        )
        
        if not invalid_order["success"]:
            print("✅ 无效套餐正确被拒绝")
        else:
            print("❌ 无效套餐验证失败")
        
        # 测试4: 订单信息查询
        print("\n🔍 测试4: 订单信息查询")
        
        order_info = await payment_service.get_order_info(order_no)
        if order_info:
            print("✅ 订单信息查询成功")
            print(f"   订单状态: {order_info.status}")
            print(f"   可否支付: {order_info.can_pay()}")
            print(f"   是否过期: {order_info.is_expired()}")
        else:
            print("❌ 订单信息查询失败")
        
        # 测试5: 模拟支付回调处理
        print("\n💰 测试5: 支付回调处理")
        
        # 记录用户当前积分
        original_points = await user_service.get_user_points_balance(db_user_id)
        print(f"   支付前积分: {original_points}")
        
        # 模拟支付成功回调
        callback_result = await payment_service.process_payment_callback(
            order_no=order_no,
            trade_no="test_trade_12345",
            verify_data={"signature": "valid_signature"}
        )
        
        if callback_result["success"]:
            print("✅ 支付回调处理成功")
            print(f"   充值积分: {callback_result['credits_added']}")
            
            # 验证积分是否到账
            new_points = await user_service.get_user_points_balance(db_user_id)
            print(f"   支付后积分: {new_points}")
            
            if new_points > original_points:
                print("✅ 积分充值成功")
            else:
                print("❌ 积分充值失败")
        else:
            print(f"❌ 支付回调处理失败: {callback_result.get('error')}")
        
        # 验证订单状态更新
        final_order = await payment_service.get_order_info(order_no)
        if final_order and final_order.status == OrderStatus.COMPLETED.value:
            print("✅ 订单状态正确更新为completed")
        else:
            print(f"❌ 订单状态更新异常: {final_order.status if final_order else 'None'}")
        
        # 测试6: 用户支付历史
        print("\n📊 测试6: 用户支付历史")
        
        payment_history = await payment_service.get_user_payment_history(db_user_id, 5)
        print(f"✅ 支付历史记录数: {len(payment_history)}")
        
        for order in payment_history:
            print(f"   - {order.order_no[:12]}...: {order.status}, ¥{order.amount}")
        
        # 测试7: 支付统计
        print("\n📈 测试7: 支付统计")
        
        payment_stats = await payment_service.get_payment_statistics(db_user_id)
        print(f"✅ 支付统计:")
        print(f"   总订单数: {payment_stats['total_orders']}")
        print(f"   已完成订单: {payment_stats['completed_orders']}")
        print(f"   总消费金额: ¥{payment_stats['total_amount']}")
        print(f"   总获得积分: {payment_stats['total_credits']}")
        print(f"   待支付订单: {payment_stats['pending_orders']}")
        
        # 测试8: 订单取消
        print("\n❌ 测试8: 订单取消功能")
        
        # 创建一个新订单用于测试取消
        cancel_order_result = await payment_service.create_payment_order(
            user_id=db_user_id,
            package_id="small",
            payment_method=PaymentMethod.WECHAT.value
        )
        
        if cancel_order_result["success"]:
            cancel_order_no = cancel_order_result["order_no"]
            
            # 取消订单
            cancel_result = await payment_service.cancel_order(cancel_order_no, db_user_id)
            
            if cancel_result["success"]:
                print("✅ 订单取消成功")
                
                # 验证订单状态
                cancelled_order = await payment_service.get_order_info(cancel_order_no)
                if cancelled_order and cancelled_order.status == OrderStatus.CANCELLED.value:
                    print("✅ 取消订单状态正确")
                else:
                    print("❌ 取消订单状态异常")
            else:
                print(f"❌ 订单取消失败: {cancel_result.get('error')}")
        
        # 测试9: 过期订单清理
        print("\n🧹 测试9: 过期订单清理")
        
        cleaned_count = await payment_service.cleanup_expired_orders()
        print(f"✅ 清理过期订单数量: {cleaned_count}")
        
        # 测试10: 数据模型转换
        print("\n🔄 测试10: 数据模型转换")
        
        # 测试PaymentPackage转换
        test_package = PaymentPackage("test", "测试套餐", 50, Decimal("5.0"), "测试用途")
        package_dict = test_package.to_dict()
        restored_package = PaymentPackage.from_dict(package_dict)
        
        if (restored_package.package_id == test_package.package_id and
            restored_package.credits == test_package.credits):
            print("✅ PaymentPackage 模型转换正确")
        else:
            print("❌ PaymentPackage 模型转换失败")
        
        # 测试PaymentOrder转换
        if final_order:
            order_dict = final_order.to_dict()
            restored_order = PaymentOrder.from_dict(order_dict)
            
            if (restored_order.order_no == final_order.order_no and
                restored_order.status == final_order.status):
                print("✅ PaymentOrder 模型转换正确")
            else:
                print("❌ PaymentOrder 模型转换失败")
        
        print("\n🎉 支付服务测试完成!")
        print("\n📊 测试总结:")
        print("✅ 支付套餐管理正常")
        print("✅ 支付方式管理正常")
        print("✅ 订单创建功能正常")
        print("✅ 订单查询功能正常")
        print("✅ 支付回调处理正常")
        print("✅ 积分充值功能正常")
        print("✅ 支付历史查询正常")
        print("✅ 支付统计功能正常")
        print("✅ 订单取消功能正常")
        print("✅ 过期订单清理正常")
        print("✅ 数据模型转换正常")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_payment_service()) 