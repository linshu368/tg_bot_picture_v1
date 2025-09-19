#!/usr/bin/env python3
import argparse
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 引入 gptCaller 与参数模板
root_path = Path(__file__).resolve().parents[2]
sys.path.append(str(root_path))  # 便于以包形式导入 gpt.*
from gpt.utils.direct_api import gptCaller
from gpt.param import commit_process_diff_prompt_template


def build_prompt(diff_content: str) -> str:
    """基于模板 commit_process_diff.prompt 渲染 prompt"""
    with open(root_path / "gpt/prompt/solid_save/long/arch.txt", "r", encoding="utf-8") as f:
        project_arch = f.read()
    with open(root_path / "gpt/prompt/solid_save/long/principle.txt", "r", encoding="utf-8") as f:
        project_principle = f.read()
    with open(root_path / "gpt/prompt/solid_save/mid/workstream/mission_textbot_p1.txt", "r", encoding="utf-8") as f:
        workstream_current_mission = f.read()

    prompt = commit_process_diff_prompt_template.format(
        project_arch=project_arch,
        project_principle=project_principle,
        workstream_current_mission=workstream_current_mission,
        git_push_commit_logs=diff_content,
    )
    return prompt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff", required=True, help="路径: 暂存区/commit diff 文件")
    parser.add_argument("--commit-id", required=False, help="指定 commit id（post-commit 阶段使用）")
    args = parser.parse_args()
    
#     # 调试用的硬编码值
#     class DebugArgs:
#         diff = "/tmp/test_diff.txt"  # 请替换为实际的测试 diff 文件路径
#         commit_id = "debug_commit_123"
    
#     args = DebugArgs()

#     # 读取 diff 文件内容
#     # 为了调试，如果文件不存在就创建一个测试内容
#     try:
#         with open(args.diff, "r", encoding="utf-8") as f:
#             diff_content = f.read()
#     except FileNotFoundError:
#         # 如果文件不存在，使用测试内容
#         diff_content = """
# diff --git a/test.py b/test.py
# index 1234567..abcdefg 100644
# --- a/test.py
# +++ b/test.py
# @@ -1,3 +1,4 @@
#  def hello():
# +    # 添加了注释
#      print("Hello World")
#      return True
# """
#         print(f"警告: diff 文件 {args.diff} 不存在，使用测试内容")


    with open(args.diff, "r", encoding="utf-8") as f:
            diff_content = f.read()
    prompt = build_prompt(diff_content)
    
    # # DEBUG: 打印 prompt 的前部分内容
    # print("=== 生成的 Prompt (前500字符) ===")
    # print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    # print("=" * 50)

    gpt = gptCaller()
    try:
        # 输出调试信息到stderr，避免干扰JSON输出
        print("正在调用 AI 生成 commit 消息...", file=sys.stderr)
        md = gpt.get_response(prompt)
        message = md
        print("AI 生成成功!", file=sys.stderr)
    except Exception as e:
        message = f"> AI 生成失败: {str(e)}"
        print(f"AI 调用失败: {e}", file=sys.stderr)

    # 元数据（commit_id 仅作透传，不做保存）
    commit_log = {
        "commit_id": args.commit_id or None,
        "author": subprocess.getoutput("git config user.name") + " <" + subprocess.getoutput("git config user.email") + ">",
        "date": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "message": message,
    }

    # 输出 JSON 给调用方
    print(json.dumps(commit_log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()