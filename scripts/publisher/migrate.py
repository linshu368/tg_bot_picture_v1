import json
import os
from supabase import create_client, Client

# Supabase API URL 和 Key
url = "https://lhcyrmigpqeloxjrfwmn.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxoY3lybWlncHFlbG94anJmd21uIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzM2MTQxNSwiZXhwIjoyMDY4OTM3NDE1fQ.I9kVX_39mit3nH8Ipzqy9jn59U1sZjQd6YhdPdvd__o"
supabase: Client = create_client(url, key)


def update_role_summaries():
    """更新 Supabase 中角色的 summary 字段"""
    print("开始更新角色库 summary 字段到 Supabase...")
    print("=" * 50)
    
    # 获取角色库数据文件路径（相对于脚本所在目录）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    role_library_path = os.path.join(script_dir, "role_library_v2.json")
    
    if not os.path.exists(role_library_path):
        print(f"❌ 角色库文件不存在: {role_library_path}")
        return
    
    # 加载角色库数据
    try:
        with open(role_library_path, 'r', encoding='utf-8') as file:
            roles_data = json.load(file)
        print(f"✅ 成功加载角色库数据文件，共 {len(roles_data)} 个角色")
    except Exception as e:
        print(f"❌ 加载角色库数据文件失败: {str(e)}")
        return
    
    success_count = 0
    error_count = 0
    not_found_count = 0
    
    for role in roles_data:
        role_id = role.get("role_id")
        new_summary = role.get("summary")
        
        if not role_id:
            print(f"⚠️  跳过无效角色：缺少 role_id")
            error_count += 1
            continue
            
        if not new_summary:
            print(f"⚠️  角色 {role_id} ({role.get('name', '未知')}) 没有 summary 字段，跳过")
            continue
        
        try:
            # 先检查角色是否存在
            existing_role = supabase.table("role_library").select("role_id, name").eq("role_id", role_id).execute()
            
            if not existing_role.data:
                print(f"❌ 角色 {role_id} ({role.get('name', '未知')}) 在 Supabase 中不存在，跳过更新")
                not_found_count += 1
                continue
            
            print(f"📝 准备更新角色: {role_id} - {role.get('name', '未知')}")
            print(f"   - Summary 长度: {len(new_summary)} 字符")
            
            # 执行更新操作
            response = supabase.table("role_library").update({
                "summary": new_summary
            }).eq("role_id", role_id).execute()
            
            if response.data:
                print(f"✅ 角色 {role_id} ({role.get('name', '未知')}) summary 更新成功")
                success_count += 1
            else:
                print(f"❌ 更新角色 {role_id} summary 时发生错误: 没有返回数据")
                error_count += 1
                
        except Exception as e:
            print(f"❌ 更新角色 {role_id} ({role.get('name', '未知')}) summary 时发生错误: {str(e)}")
            error_count += 1
    
    print("=" * 50)
    print("📊 角色库 summary 更新统计:")
    print(f"   ✅ 成功: {success_count} 个")
    print(f"   ❌ 失败: {error_count} 个") 
    print(f"   🔍 未找到: {not_found_count} 个")
    print(f"   📋 总计: {len(roles_data)} 个")
    print("=" * 50)


def main():
    """主函数：执行角色库 summary 更新"""
    print("🚀 开始角色库 summary 更新任务")
    update_role_summaries()
    print("🎉 角色库 summary 更新任务完成")


if __name__ == "__main__":
    main()