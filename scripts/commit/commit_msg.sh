# hook入口，采集diff+调用AI
#!/usr/bin/env bash
set -euo pipefail

COMMIT_MSG_FILE="${1:?usage: commit_msg.sh .git/COMMIT_EDITMSG}"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# 配置文件路径（你放在 gpt/prompt/ 下）
CONFIG="$REPO_ROOT/gpt/prompt/config.yaml"

# 快照目录（用于保存每次生成的 commit 信息）
LOG_DIR="$REPO_ROOT/logs/snapshots"
mkdir -p "$LOG_DIR"

# 临时 diff 文件
DIFF_FILE="$(mktemp -t diff.XXXXXX.patch)"
git diff --cached > "$DIFF_FILE"

# 如果没有改动，写入一个默认信息
if [[ ! -s "$DIFF_FILE" ]]; then
  echo "chore(core): empty commit" > "$COMMIT_MSG_FILE"
  exit 0
fi

# 调用 Python 脚本（会输出 JSON 格式结果）
PY_BIN="$REPO_ROOT/venv/bin/python"
if [ -x "$PY_BIN" ]; then
  :
else
  PY_BIN="python3"
fi

OUT_JSON="$("$PY_BIN" "$REPO_ROOT/scripts/commit/gen_commit_msg.py" \
  --prompt "$CONFIG" --diff "$DIFF_FILE")"

# 解析 JSON（需要 jq 工具，如果没有 jq，可以换成 python 解析）
title="$(echo "$OUT_JSON" | jq -r '.title')"
body="$(echo "$OUT_JSON" | jq -r '.body')"

# 写入最终 commit message
{
  echo "$title"
  echo
  echo "$body"
} > "$COMMIT_MSG_FILE"

# 额外保存快照
ts="$(date +%Y%m%d-%H%M%S)"
echo -e "# $title\n\n$body" > "$LOG_DIR/$ts.md"
