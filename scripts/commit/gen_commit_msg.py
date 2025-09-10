#!/usr/bin/env python3
import argparse
import json
import sys
import yaml
import subprocess
from pathlib import Path
from datetime import datetime

# 引入 gptCaller 与参数模板
root_path = Path(__file__).resolve().parents[2]
sys.path.append(str(root_path))  # 便于以包形式导入 gpt.*
from gpt.utils.direct_api import gptCaller
from gpt.param import commit_process_diff_prompt_template


def build_prompt(config_path: str, diff_file: str) -> str:
    """基于模板 commit_msg.prompt 渲染 prompt"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    project_intro = (config.get("project") or {}).get("intro") or ""
    current_mission = (config.get("workstream") or {}).get("current_mission") or ""
    scope_guide = (config.get("workstream") or {}).get("change_scope_guide") or ""

    with open(diff_file, "r", encoding="utf-8") as f:
        diff_content = f.read()

    prompt = (
        commit_process_diff_prompt_template
        .replace("{project.intro}", project_intro)
        .replace("{workstream.current_mission}", current_mission)
        .replace("{workstream.change_scope_guide}", scope_guide)
        .replace("{git diff --cached}", diff_content)
    )
    return prompt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="路径: gpt/prompt/config.yaml")
    parser.add_argument("--diff", required=True, help="路径: 暂存区/commit diff 文件")
    parser.add_argument("--commit-id", required=False, help="指定 commit id（post-commit 阶段使用）")
    args = parser.parse_args()

    # 构造 prompt
    prompt = build_prompt(args.prompt, args.diff)

    gpt = gptCaller()
    
    # 重试机制
    max_retries = 3
    retry_delay = 2  # 秒
    
    for attempt in range(max_retries):
        try:
            md = gpt.get_response(prompt)
            # 清理消息中的控制字符，确保JSON有效
            import re
            message = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', md)
            break  # 成功则跳出重试循环
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"AI 调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}", file=sys.stderr)
                print(f"等待 {retry_delay} 秒后重试...", file=sys.stderr)
                import time
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                message = f"> AI 生成失败: {str(e)}"

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