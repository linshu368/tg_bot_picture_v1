# hook入口，采集diff+调用AI
#!/usr/bin/env bash
set -euo pipefail

COMMIT_MSG_FILE="${1:?usage: commit_msg.sh .git/COMMIT_EDITMSG}"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# 配置文件路径（你放在 gpt/prompt/ 下）
CONFIG="$REPO_ROOT/gpt/prompt/config.yaml"

# 模板路径
TEMPLATE="$REPO_ROOT/gpt/prompt/commit_msg.prompt"

# 临时 diff 文件
DIFF_FILE="$(mktemp -t diff.XXXXXX.patch)"
git diff --cached > "$DIFF_FILE"

# 如果没有改动，写入一个默认信息
if [[ ! -s "$DIFF_FILE" ]]; then
  echo "chore(core): empty commit" > "$COMMIT_MSG_FILE"
  exit 0
fi

# Python 解释器（优先 venv）
PY_BIN="$REPO_ROOT/venv/bin/python"
if [ ! -x "$PY_BIN" ]; then
  PY_BIN="python3"
fi

# 调用 Python 脚本（返回完整 JSON）
OUT_JSON="$("$PY_BIN" "$REPO_ROOT/scripts/commit/gen_commit_msg.py" \
  --prompt "$CONFIG" --diff "$DIFF_FILE")"

# 用 jq 提取 commit message 部分（暂时注释，改为直接使用原始返回）
# title="$(echo "$OUT_JSON" | jq -r '.message.title')"
# body="$(echo "$OUT_JSON" | jq -r '.message.body')"

# 直接使用 AI 原始返回的 message
raw_message="$(echo "$OUT_JSON" | jq -r '.message')"

# 将原始返回写入最终 commit message，并在控制台打印
{
  echo "$raw_message"
} > "$COMMIT_MSG_FILE"

echo "AI raw message:"
echo "$raw_message"

# 保存完整 JSON 快照（gen_commit_msg.py 里已经保存过，这里可选）
SNAPSHOT_DIR="$REPO_ROOT/logs/snapshots"
mkdir -p "$SNAPSHOT_DIR"
ts="$(date +%Y%m%d-%H%M%S)"
echo "$OUT_JSON" > "$SNAPSHOT_DIR/$ts.json"
