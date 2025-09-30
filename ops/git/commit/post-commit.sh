#!/usr/bin/env bash
set -euo pipefail

# 加载配置
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
source "$SCRIPT_DIR/../config.sh"

# 设置Python环境
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="$PYTHON_FALLBACK"

COMMIT_ID="$(git rev-parse HEAD)"

DIFF_FILE="$(mktemp -t diff.XXXXXX.patch)"
git show "$COMMIT_ID" --pretty=format: > "$DIFF_FILE"

# 调用 Python 生成 JSON（不保存文件）
OUT_JSON="$("$PYTHON_BIN" "$PROJECT_ROOT/ops/git/commit/gen_commit_msg.py" \
  --diff "$DIFF_FILE" \
  --commit-id "$COMMIT_ID")"

# 保存快照（文件名 = 时间戳.json）
mkdir -p "$SNAPSHOTS_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
echo "$OUT_JSON" > "$SNAPSHOTS_DIR/$TIMESTAMP.json"

echo "Commit log saved: $SNAPSHOTS_DIR/$TIMESTAMP.json"