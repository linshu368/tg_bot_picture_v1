#!/usr/bin/env python3
"""
验证新Repository修复效果的脚本
检查代码修复是否正确应用
"""

import os
import sys
import uuid
import re

def check_uuid_fix():
    """检查UUID修复是否应用"""
    print("🧪 检查UUID修复...")
    
    file_path = "src/infrastructure/database/repositories_v2/composite/user_composite_repository.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否使用了正确的UUID生成
        if "str(uuid.uuid4())" in content and "str(checkin['id'])" not in content:
            print("✅ UUID修复已正确应用")
            return True
        elif "str(checkin['id'])" in content:
            print("❌ 仍然使用错误的checkin['id']")
            return False
        else:
            print("⚠️ 无法确认UUID修复状态")
            return False
            
    except Exception as e:
        print(f"❌ 检查UUID修复失败: {e}")
        return False


def check_verification_fix():
    """检查并行验证修复是否应用"""
    print("🧪 检查并行验证修复...")
    
    file_path = "src/domain/services/user_service.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ("用户注册验证修复", "get_by_telegram_id(telegram_id)" in content),
            ("积分验证修复", "get_by_user_id(user_id)" in content),
            ("跳过验证逻辑", "跳过验证" in content or "跳过积分验证" in content),
            ("移除重复创建", "await self.verification_user_repo.create(main_data)" not in content)
        ]
        
        all_good = True
        for check_name, check_result in checks:
            if check_result:
                print(f"✅ {check_name}: 已修复")
            else:
                print(f"❌ {check_name}: 未修复")
                all_good = False
        
        return all_good
        
    except Exception as e:
        print(f"❌ 检查验证修复失败: {e}")
        return False


def check_current_logs():
    """检查当前日志中是否还有相关错误"""
    print("🧪 检查最新日志错误...")
    
    log_files = [
        "logs/pm2-combined-4.log",
        "logs/pm2-error-4.log"
    ]
    
    error_patterns = [
        r"invalid input syntax for type uuid",
        r"用户注册数据不一致",
        r"用户钱包不存在.*user_id"
    ]
    
    recent_errors = []
    
    for log_file in log_files:
        if not os.path.exists(log_file):
            continue
            
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-100:]  # 只检查最后100行
                
            for line in lines:
                for pattern in error_patterns:
                    if re.search(pattern, line):
                        recent_errors.append(f"{log_file}: {line.strip()}")
        except Exception as e:
            print(f"⚠️ 无法读取日志 {log_file}: {e}")
    
    if recent_errors:
        print("❌ 发现相关错误（最近100行）：")
        for error in recent_errors[-5:]:  # 只显示最后5个错误
            print(f"   {error}")
        return False
    else:
        print("✅ 最近日志中未发现相关错误")
        return True


def check_service_status():
    """检查服务状态"""
    print("🧪 检查服务状态...")
    
    try:
        import subprocess
        result = subprocess.run(['ps', 'aux', '|', 'grep', 'tg_bot'], 
                              shell=True, capture_output=True, text=True)
        
        if 'main.py' in result.stdout or 'tg-bot-picture' in result.stdout:
            print("✅ 服务正在运行")
            return True
        else:
            print("⚠️ 服务可能未运行")
            return False
    except Exception as e:
        print(f"⚠️ 无法检查服务状态: {e}")
        return False


def main():
    """主验证函数"""
    print("🚀 开始验证修复效果...")
    print("=" * 50)
    
    checks = [
        ("UUID修复", check_uuid_fix()),
        ("并行验证修复", check_verification_fix()),
        ("日志错误检查", check_current_logs()),
        ("服务状态", check_service_status())
    ]
    
    print("=" * 50)
    print("📊 验证结果汇总:")
    
    all_good = True
    for check_name, result in checks:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {check_name}: {status}")
        if not result:
            all_good = False
    
    print("=" * 50)
    
    if all_good:
        print("🎉 所有检查通过！修复已正确应用")
        print("\n📋 建议操作：")
        print("1. 重启服务让修复生效：pm2 restart tg-bot-picture")
        print("2. 监控日志确认错误消失：tail -f logs/pm2-combined-4.log")
        print("3. 进行用户注册和签到测试")
        return 0
    else:
        print("⚠️ 部分检查未通过，请查看上述详情")
        print("\n🔧 可能需要的操作：")
        print("1. 确认代码修复是否正确保存")
        print("2. 重启服务应用修复")
        print("3. 检查是否有其他相关问题")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ 检查中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 检查异常: {e}")
        sys.exit(1) 