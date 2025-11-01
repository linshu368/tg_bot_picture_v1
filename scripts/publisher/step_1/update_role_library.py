import json

# 读取结果数据
def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 写入数据到目标文件
def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 处理单个角色数据
def process_role_data(role_data, role_id):
    # 合并worldview和role_introduction为summary
    summary = f"{role_data.get('worldview', '')} {role_data.get('role_introduction', '')}"
    
    # 构建新角色数据
    processed_data = {
        "role_id": str(role_id),
        "name": role_data.get("role_name", ""),
        "tags": role_data.get("tag", []),
        "summary": summary,
        "system_prompt": role_data.get("role_system_prompt", ""),
        "history": [],
        "predefined_messages": "开始冒险之旅吧",
        "model": "gemini-2.5-flash",
        "deeplink": f"https://t.me/test1014_chat_bot?start=role_{role_id}"
    }
    
    return processed_data

# 主函数，读取原始数据并处理所有角色
def main():
    # 输入和输出文件路径
    input_file = '/Users/qj/python_project/tg_bot_picture_v1/scripts/publisher/step_1/results_step1.json'
    output_file = '/Users/qj/python_project/tg_bot_picture_v1/demo/role_library.json'

    # 加载已有的role_library.json数据
    role_library_data = load_json(output_file)

    # 加载来自results_step1.json的数据
    results_data = load_json(input_file)

    # 处理每个角色数据并添加到role_library_data
    for role_id, role_data in enumerate(results_data, start=1):
        processed_role = process_role_data(role_data, role_id)
        role_library_data.append(processed_role)

    # 保存更新后的role_library.json数据
    save_json(role_library_data, output_file)
    print(f"数据成功写入到 {output_file}")

# 执行主程序
if __name__ == '__main__':
    main()
