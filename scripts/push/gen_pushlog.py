import argparse, json, os, datetime, yaml, sys
from pathlib import Path

# 引入 gptCaller 与参数模板
root_path = Path(__file__).resolve().parents[2]
sys.path.append(str(root_path))  # 便于以包形式导入 gpt.*
from gpt.utils.direct_api import gptCaller
from gpt.param import commit_process_diff_prompt_template 
from gpt.param import push_log_title_prompt_template


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


def collect_commit_diffs(commits):
    """收集所有 commit 的 diff 内容"""
    diff_content = ""
    for cid in commits:
        path = str(root_path / f"logs/snapshots/{cid}.json")
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
    path = str(root_path / f"logs/snapshots/{cid}.json")
    if os.path.exists(path):
        with open(path) as f:
            commitlogs.append(json.load(f))

# 🔹 AI 生成 message
# 收集所有 commit 的 diff 内容
diff_content = collect_commit_diffs(commits)

# 构造 prompt
prompt = build_prompt(args.prompt, diff_content)

# 调用 GPT（直接使用原始 Markdown 作为 message）
gpt = gptCaller()
try:
    md = gpt.get_response(prompt)
    message = md
except Exception as e:
   
    if commitlogs:
        # commitlogs 里历史可能是对象或字符串，这里做兼容
        parts = []
        for c in commitlogs:
            m = c.get("message")
            if isinstance(m, dict):
                parts.append(m.get("title") or "")
            elif isinstance(m, str):
                parts.append(m)
        message = "\n".join([p for p in parts if p]) or "> fallback: no titles found"
    else:
        message = "push update\nno commitlogs found"

# 🔹 第二次调用 GPT，生成 pushlog 目录名
try:
    filename_prompt = push_log_title_prompt_template.replace("{commit_message}", message)
    dir_name = gpt.get_response(filename_prompt).strip()
    # 防御：替换非法路径字符
    dir_name = "".join(c for c in dir_name if c not in r"\/:*?\"<>|")
except Exception:
    dir_name = "未命名改动"


# pushlog 对象
pushlog = {
    "push_id": push_id,
    "remote": args.remote,
    "branch": args.branch,
    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %z"),
    "commits": commits,
    "message": message,
    "dir_name": dir_name
}

# 写入 pushlog 目录（目录名 = dir_name + date[YYYYMMDD]，date取自 pushlog["date"]）
date_str = pushlog["date"].strip()
try:
    dir_date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z").strftime("%Y%m%d")
except Exception:
    dir_date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d")
push_dir = str(root_path / f"logs/pushlogs/{dir_name}_{dir_date}")
os.makedirs(f"{push_dir}/commits", exist_ok=True)

with open(f"{push_dir}/push_log.json", "w") as f:
    json.dump(pushlog, f, indent=2, ensure_ascii=False)

# 迁移 commitlog
for cid in commits:
    src = str(root_path / f"logs/snapshots/{cid}.json")
    dst = f"{push_dir}/commits/{cid}.json"
    if os.path.exists(src):
        os.rename(src, dst)
