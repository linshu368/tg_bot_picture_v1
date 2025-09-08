# 调用大模型 API，返回 commit message
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


# def parse_response(md: str):
#     """解析 AI 返回的 markdown，提取 title + body"""
#     lines = [l.strip() for l in md.splitlines() if l.strip()]
#     title = ""
#     body_lines = []

#     for i, line in enumerate(lines):
#         if line.startswith("# "):
#             title = line[2:].strip()
#             body_lines = lines[i + 1 :]
#             break

#     if not title and lines:
#         title = lines[0]
#         body_lines = lines[1:]

#     return title, "\n".join(body_lines).strip()


def get_git_metadata():
    """获取当前 commit 的元信息（author、date、短哈希）"""
    commit_id = subprocess.getoutput("git rev-parse HEAD")
    author = subprocess.getoutput("git config user.name") + " <" + subprocess.getoutput("git config user.email") + ">"
    # 使用本地时区，确保 %z 输出形如 +0800
    date = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    return commit_id, author, date


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="路径: gpt/prompt/config.yaml")
    parser.add_argument("--diff", required=True, help="路径: 暂存区 diff 文件")
    parser.add_argument("--output", required=False, help="输出文件（可选）")
    args = parser.parse_args()

    # 构造 prompt
    prompt = build_prompt(args.prompt, args.diff)

    # 调用 GPT（直接使用原始 Markdown 作为 message）
    gpt = gptCaller()
    try:
        md = gpt.get_response(prompt)
        message = md
    except Exception as e:
        message = f"> AI 生成失败: {str(e)}"

    # 获取 commit 元数据
    commit_id, author, date = get_git_metadata()

    # 组装完整日志（message 为原始 Markdown 字符串）
    commit_log = {
        "commit_id": commit_id,
        "author": author,
        "date": date,
        "message": message
    }

    # 输出 JSON（给 commit_msg.sh 用）- 使用缩进便于可读
    print(json.dumps(commit_log, ensure_ascii=False, indent=2))

    # 存档到 logs/snapshots
    log_dir = root_path / "logs" / "snapshots"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(log_dir / f"{ts}.json", "w", encoding="utf-8") as f:
        json.dump(commit_log, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

