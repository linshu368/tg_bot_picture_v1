#!/usr/bin/env python3
"""
检查Supabase迁移状态
验证哪些组件已经迁移到Supabase，哪些还在使用SQLite
"""

import os
import sys
import re
from pathlib import Path

# 添加项目根目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

def check_file_imports(file_path: Path) -> dict:
    """检查文件中的导入情况"""
    result = {
        'file': str(file_path),
        'uses_sqlite': False,
        'uses_supabase': False,
        'uses_old_repo': False,
        'uses_new_repo': False,
        'uses_old_manager': False,
        'uses_new_manager': False
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 检查SQLite相关
            if 'aiosqlite' in content:
                result['uses_sqlite'] = True
            
            # 检查Supabase相关
            if 'supabase' in content.lower():
                result['uses_supabase'] = True
            
            # 检查Repository类型
            if re.search(r'from.*repositories\.user_repository', content):
                result['uses_old_repo'] = True
            if re.search(r'from.*repositories\.point_record_repository', content):
                result['uses_old_repo'] = True
            if re.search(r'from.*repositories\.base_repository', content):
                result['uses_old_repo'] = True
                
            if re.search(r'from.*repositories\.supabase_', content):
                result['uses_new_repo'] = True
            
            # 检查Manager类型
            if 'DatabaseManager' in content:
                result['uses_old_manager'] = True
            if 'SupabaseManager' in content:
                result['uses_new_manager'] = True
                
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return result

def scan_project():
    """扫描项目文件"""
    project_root = Path(__file__).parent.parent
    results = []
    
    # 扫描源代码目录
    src_dir = project_root / 'src'
    if src_dir.exists():
        for py_file in src_dir.rglob('*.py'):
            results.append(check_file_imports(py_file))
    
    # 扫描脚本目录
    scripts_dir = project_root / 'scripts'
    if scripts_dir.exists():
        for py_file in scripts_dir.glob('*.py'):
            # 跳过迁移相关的脚本
            if any(skip in py_file.name for skip in ['migrate', 'supabase', 'check_migration']):
                continue
            results.append(check_file_imports(py_file))
    
    return results

def print_migration_status():
    """打印迁移状态报告"""
    print("🔍 Supabase迁移状态检查")
    print("=" * 60)
    
    results = scan_project()
    
    # 分类统计
    fully_migrated = []
    partially_migrated = []
    not_migrated = []
    mixed_files = []
    
    for result in results:
        if result['uses_new_repo'] or result['uses_new_manager'] or result['uses_supabase']:
            if result['uses_old_repo'] or result['uses_old_manager'] or result['uses_sqlite']:
                mixed_files.append(result)
            else:
                fully_migrated.append(result)
        elif result['uses_old_repo'] or result['uses_old_manager'] or result['uses_sqlite']:
            not_migrated.append(result)
    
    print(f"\n📊 迁移统计:")
    print(f"✅ 完全迁移: {len(fully_migrated)} 个文件")
    print(f"🔄 混合状态: {len(mixed_files)} 个文件")
    print(f"❌ 未迁移: {len(not_migrated)} 个文件")
    
    if fully_migrated:
        print(f"\n✅ 已完全迁移到Supabase的文件:")
        for result in fully_migrated:
            print(f"   • {result['file']}")
    
    if mixed_files:
        print(f"\n🔄 混合状态的文件（同时使用新旧系统）:")
        for result in mixed_files:
            issues = []
            if result['uses_sqlite']:
                issues.append("SQLite")
            if result['uses_old_repo']:
                issues.append("旧Repository")
            if result['uses_old_manager']:
                issues.append("旧Manager")
            print(f"   • {result['file']} - 仍使用: {', '.join(issues)}")
    
    if not_migrated:
        print(f"\n❌ 尚未迁移的文件:")
        for result in not_migrated:
            issues = []
            if result['uses_sqlite']:
                issues.append("SQLite")
            if result['uses_old_repo']:
                issues.append("旧Repository")
            if result['uses_old_manager']:
                issues.append("旧Manager")
            print(f"   • {result['file']} - 使用: {', '.join(issues)}")
    
    print(f"\n📋 迁移建议:")
    if not_migrated:
        print("1. 优先迁移业务关键文件中的Repository和Manager")
        print("2. 更新测试脚本以使用新的Supabase组件")
        print("3. 保留迁移脚本中的SQLite代码（用于数据迁移）")
    else:
        print("🎉 所有核心文件已迁移到Supabase！")
    
    if mixed_files:
        print("4. 检查混合状态文件，确保向后兼容性或完成迁移")
    
    print(f"\n🔗 相关文件:")
    print("   • 表结构: scripts/supabase_tables.sql")
    print("   • 测试脚本: scripts/test_supabase.py")
    print("   • 迁移文档: docs/MIGRATION_SUMMARY.md")

if __name__ == "__main__":
    print_migration_status() 