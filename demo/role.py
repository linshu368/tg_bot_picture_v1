# role.py
# 从 role_library.json 中选择一个角色用于测试

import json
from pathlib import Path

# 读取角色库 - 文件位于 scripts/publisher/ 目录
role_library_path = Path(__file__).parent.parent / "scripts" / "publisher" / "role_library.json"
with open(role_library_path, 'r', encoding='utf-8') as f:
    roles = json.load(f)

# 默认使用第一个角色（小鹿）
role_data = roles[0]

print(f"✅ 已加载角色: {role_data['name']}")

