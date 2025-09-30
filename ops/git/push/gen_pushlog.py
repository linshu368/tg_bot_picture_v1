import argparse, json, os, datetime, sys
from pathlib import Path
import subprocess
# 引入 gptCaller 与参数模板
# 从环境变量获取配置，如果没有则使用默认值
root_path = Path(os.environ.get('GPT_MODULE_ROOT', Path(__file__).resolve().parents[2]))
prompt_dir = Path(os.environ.get('PROMPT_DIR', root_path / "ops/gpt/prompt"))
logs_dir = Path(os.environ.get('LOGS_DIR', root_path / "ops/git/logs"))
sys.path.append(str(root_path))  # 便于以包形式导入 ops.gpt.*
from ops.gpt.utils.direct_api import gptCaller
from ops.gpt.param import commit_process_diff_prompt_template 
from ops.gpt.param import push_log_title_prompt_template
from ops.gpt.param import push_log_arch2pr_prompt_template


def build_prompt(diff_content: str) -> str:
    """基于模板 push_msg.prompt 渲染 prompt"""
    with open(prompt_dir / "solid_save/long/arch.txt", "r", encoding="utf-8") as f:
        project_arch = f.read()
    with open(prompt_dir / "solid_save/long/principle.txt", "r", encoding="utf-8") as f:
        project_principle = f.read()
    with open(prompt_dir / "solid_save/mid/workstream/mission_textbot_p1.txt", "r", encoding="utf-8") as f:
        workstream_current_mission = f.read()

    prompt = commit_process_diff_prompt_template.format(
        project_arch=project_arch,
        project_principle=project_principle,
        workstream_current_mission=workstream_current_mission,
        git_push_commit_logs=diff_content,
    )
    return prompt


def build_prompt_arch2pr(diff_content: str) -> str:
    """基于模板 push_log_pr2arch.prompt 渲染 prompt"""
    with open(prompt_dir / "solid_save/long/project_business_goal.txt", "r", encoding="utf-8") as f:
        product_business_goal = f.read()
    with open(prompt_dir / "solid_save/mid/requirements_functional_spec.txt", "r", encoding="utf-8") as f:
        requirements_functional_spec = f.read()
    with open(prompt_dir / "solid_save/long/arch.txt", "r", encoding="utf-8") as f:
        project_architecture = f.read()
    with open(prompt_dir / "solid_save/long/principle.txt", "r", encoding="utf-8") as f:
        project_principle = f.read()

    prompt = push_log_arch2pr_prompt_template.format(
        product_business_goal=product_business_goal,
        requirements_functional_spec=requirements_functional_spec,
        project_architecture=project_architecture,
        project_principle=project_principle,
        git_push_commit_logs=diff_content,
    )
    return prompt



def collect_push_diff(remote: str, branch: str) -> str:
    """获取本次 push 的整体 diff"""
    rev_range = f"{remote}/{branch}..HEAD"
    diff_content = subprocess.getoutput(f"git diff {rev_range}")
    print(diff_content)
    return diff_content


parser = argparse.ArgumentParser()
parser.add_argument("--remote", required=True)
parser.add_argument("--branch", required=True)
parser.add_argument("--commits", required=True)
args = parser.parse_args()

commits = args.commits.split()
if not commits:
    exit(0)

# 生成 push_id
push_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

# 收集本次push 的 diff 内容
diff_content = collect_push_diff(args.remote, args.branch)

# 构造 prompt（面向研发）
prompt = build_prompt(diff_content)

# 调用 GPT（直接使用原始 Markdown 作为 message）
gpt = gptCaller()

# gpt_4o_mini = gptCaller(model="gpt-4o-mini")
# try:
md = gpt.get_response(prompt)
message = md

# 🔹 新增：构造 prompt（面向产品）并调用 GPT
try:
    prompt_arch2pr = build_prompt_arch2pr(diff_content)
    message_for_product = gpt.get_response(prompt_arch2pr)
except Exception:
    message_for_product = "未生成产品说明"  
# ----------------------------


# 🔹 第二次调用 GPT，生成 pushlog 目录名
try:
    filename_prompt = push_log_title_prompt_template.replace("{message}", message)
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
    "message": message,#工程侧
    "message_for_product": message_for_product,#产品侧
    "dir_name": dir_name
}

# 写入 pushlog 目录（目录名 = dir_name + date[YYYYMMDD]，date取自 pushlog["date"]）
date_str = pushlog["date"].strip()
try:
    dir_date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z").strftime("%Y%m%d")
except Exception:
    dir_date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d")
push_dir = str(logs_dir / f"pushlogs/{dir_name}_{dir_date}")
os.makedirs(f"{push_dir}/commits", exist_ok=True)

with open(f"{push_dir}/push_log.json", "w") as f:
    json.dump(pushlog, f, indent=2, ensure_ascii=False)

# 迁移当前 snapshots 目录下的所有 JSON 快照到本次 push 目录
snap_dir = logs_dir / "snapshots"
if os.path.isdir(snap_dir):
    for name in os.listdir(snap_dir):
        if not name.endswith(".json"):
            continue
        src = str(snap_dir / name)
        dst = f"{push_dir}/commits/{name}"
        try:
            os.rename(src, dst)
        except FileNotFoundError:
            pass