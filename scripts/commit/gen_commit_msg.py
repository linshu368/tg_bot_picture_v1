# 调用大模型 API，返回 commit message
#!/usr/bin/env python3
import argparse
import json
import sys
import yaml
from pathlib import Path

# 引入你写的 gptCaller
sys.path.append(str(Path(__file__).resolve().parents[2] / "gpt" / "utils"))
from direct_api import gptCaller


def build_prompt(config_path: str, diff_file: str) -> str:
    """
    构造 prompt（外圈+中圈+内圈diff）
    """
    # 加载 config.yaml
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    outer = config.get("project", {}).get("intro", "")
    inner = config.get("workstream", {}).get("current_mission", "")
    scope_guide = config.get("workstream", {}).get("change_scope_guide", "")

    # 读取 diff
    with open(diff_file, "r", encoding="utf-8") as f:
        diff = f.read()

    prompt = f"""
你是资深软件工程助理，请基于“靶心原则”生成**约定式提交**信息以及简明的要点列表。

【外圈：项目与架构（长期稳定）】
{outer}

【中圈：当前任务与阶段目标】
{inner}

【中圈：变更影响层级参考】
{scope_guide}

【内圈：本次暂存变更的diff（只读）】
{diff}

要求：
1. 生成一行符合 Conventional Commits 的标题，格式：
   <type>(<scope>): <subject-中文简述，不超过60字>
   type 必须是：feat / fix / docs / refactor / perf / test / chore
   scope 建议简短（如 api/db/core）
2. 给出3-6条要点（中文，短句，聚焦影响面与风险）
3. 如涉及数据库/接口变更，补充“回滚注意事项”，否则写“无”

只输出 Markdown，结构：
# title
- point1
- point2
...
> rollback: ...
"""
    return prompt


def parse_response(md: str):
    """
    解析 AI 返回的 markdown，提取 title + body
    """
    lines = [l.strip() for l in md.splitlines() if l.strip()]
    title = ""
    body_lines = []

    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_lines = lines[i + 1 :]
            break

    if not title and lines:
        title = lines[0]
        body_lines = lines[1:]

    return title, "\n".join(body_lines).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="路径: gpt/prompt/config.yaml")
    parser.add_argument("--diff", required=True, help="路径: 暂存区 diff 文件")
    args = parser.parse_args()

    # 构造 prompt
    prompt = build_prompt(args.prompt, args.diff)

    # 调用 GPT
    gpt = gptCaller()
    try:
        md = gpt.get_response(prompt)
    except Exception as e:
        # 兜底策略：AI 调用失败时避免 commit 中断
        fallback = {
            "title": "chore(core): update",
            "body": f"> AI 生成失败: {str(e)}"
        }
        print(json.dumps(fallback, ensure_ascii=False))
        return

    title, body = parse_response(md)

    # 输出 JSON 给 commit_msg.sh 使用
    result = {"title": title, "body": body}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
