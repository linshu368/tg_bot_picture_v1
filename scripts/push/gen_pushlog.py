import argparse, json, os, datetime, yaml, sys
from pathlib import Path

# 引入 gptCaller 与参数模板
root_path = Path(__file__).resolve().parents[2]
sys.path.append(str(root_path))  # 便于以包形式导入 gpt.*
from gpt.utils.direct_api import gptCaller
from gpt.param import commit_process_diff_prompt_template


def build_prompt(config_path: str, diff_content: str) -> str:
    """基于模板 push_msg.prompt 渲染 prompt"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    project_intro = (config.get("project") or {}).get("intro") or ""
    current_mission = (config.get("workstream") or {}).get("current_mission") or ""
    scope_guide = (config.get("workstream") or {}).get("change_scope_guide") or ""

    prompt = (
        commit_process_diff_prompt_template
        .replace("{project.intro}", project_intro)
        .replace("{workstream.current_mission}", current_mission)
        .replace("{workstream.change_scope_guide}", scope_guide)
        .replace("{git diff --cached}", diff_content)
    )
    return prompt


def parse_response(md: str):
    """解析 AI 返回的 markdown，提取 title + body + super_title"""
    lines = [l.strip() for l in md.splitlines() if l.strip()]
    title = ""
    body_lines = []
    super_title = ""

    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_lines = lines[i + 1 :]
            break

    if not title and lines:
        title = lines[0]
        body_lines = lines[1:]

    # 查找 super_title
    for line in lines:
        if line.startswith("> super_title:"):
            super_title = line[14:].strip()
            break

    return title, "\n".join(body_lines).strip(), super_title


def collect_commit_diffs(commits):
    """收集所有 commit 的 diff 内容"""
    diff_content = ""
    for cid in commits:
        path = f"logs/snapshots/{cid}.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                commit_data = json.load(f)
                # 假设 commit_data 中有 diff 字段，如果没有则跳过
                if "diff" in commit_data:
                    diff_content += f"\n=== Commit {cid} ===\n"
                    diff_content += commit_data["diff"]
                    diff_content += "\n"
    return diff_content


parser = argparse.ArgumentParser()
parser.add_argument("--remote", required=True)
parser.add_argument("--branch", required=True)
parser.add_argument("--commits", required=True)
parser.add_argument("--prompt", required=True, help="路径: gpt/prompt/config.yaml")
args = parser.parse_args()

commits = args.commits.split()
if not commits:
    exit(0)

# 生成 push_id
push_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

# 读取 commitlog
commitlogs = []
for cid in commits:
    path = f"logs/snapshots/{cid}.json"
    if os.path.exists(path):
        with open(path) as f:
            commitlogs.append(json.load(f))

# 🔹 AI 生成 message
# 收集所有 commit 的 diff 内容
diff_content = collect_commit_diffs(commits)

# 构造 prompt
prompt = build_prompt(args.prompt, diff_content)

# 调用 GPT
gpt = gptCaller()
try:
    md = gpt.get_response(prompt)
    title, body, super_title = parse_response(md)
except Exception as e:
    # fallback 到原来的逻辑
    if commitlogs:
        title = commitlogs[-1]["message"]["title"]
        body = "\n".join([c["message"]["title"] for c in commitlogs])
        super_title = title
    else:
        title, body, super_title = "push update", "no commitlogs found", "push update"

message = {
    "title": title,
    "body": body,
    "super_title": super_title
}

# pushlog 对象
pushlog = {
    "push_id": push_id,
    "remote": args.remote,
    "branch": args.branch,
    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %z"),
    "commits": commits,
    "message": message
}

# 写入 pushlog 目录
push_dir = f"logs/pushlogs/{push_id}"
os.makedirs(f"{push_dir}/commits", exist_ok=True)

with open(f"{push_dir}/push_log.json", "w") as f:
    json.dump(pushlog, f, indent=2, ensure_ascii=False)

# 迁移 commitlog
for cid in commits:
    src = f"logs/snapshots/{cid}.json"
    dst = f"{push_dir}/commits/{cid}.json"
    if os.path.exists(src):
        os.rename(src, dst)
