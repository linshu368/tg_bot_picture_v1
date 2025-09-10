#!/usr/bin/env bash
set -euo pipefail

COMMIT_MSG_FILE="${1:?usage: commit-msg .git/COMMIT_EDITMSG}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
CONFIG="$REPO_ROOT/gpt/prompt/config.yaml"

DIFF_FILE="$(mktemp -t diff.XXXXXX.patch)"
git diff --cached > "$DIFF_FILE"

if [[ ! -s "$DIFF_FILE" ]]; then
  echo "chore(core): empty commit" > "$COMMIT_MSG_FILE"
  exit 0
fi

PY_BIN="$REPO_ROOT/venv/bin/python"
if [ ! -x "$PY_BIN" ]; then
  PY_BIN="python3"
fi

# 调用 Python 脚本，生成 JSON
OUT_JSON="$("$PY_BIN" "$REPO_ROOT/scripts/commit/gen_commit_msg.py" \
  --prompt "$CONFIG" --diff "$DIFF_FILE")"

# 取出 message
raw_message="$(echo "$OUT_JSON" | jq -r '.message')"

# 如果 AI 返回失败提示，也阻止提交
if [[ "$raw_message" == "> AI 生成失败"* ]]; then
  echo "❌ AI 调用异常，提交已被阻止"
  exit 1
fi

# 写入 commit message
echo "$raw_message" > "$COMMIT_MSG_FILE"

echo "AI Commit Message:"
echo "$raw_message"