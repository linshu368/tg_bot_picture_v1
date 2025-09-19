#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
PY_BIN="$REPO_ROOT/venv/bin/python"
[ -x "$PY_BIN" ] || PY_BIN="python3"

COMMIT_ID="$(git rev-parse HEAD)"

DIFF_FILE="$(mktemp -t diff.XXXXXX.patch)"
git show "$COMMIT_ID" --pretty=format: > "$DIFF_FILE"

# 调用 Python 生成 JSON（不保存文件）
OUT_JSON="$("$PY_BIN" "$REPO_ROOT/scripts/commit/gen_commit_msg.py" \
  --diff "$DIFF_FILE" \
  --commit-id "$COMMIT_ID")"

# 保存快照（文件名 = 时间戳.json）
SNAPSHOT_DIR="$REPO_ROOT/logs/snapshots"
mkdir -p "$SNAPSHOT_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
echo "$OUT_JSON" > "$SNAPSHOT_DIR/$TIMESTAMP.json"

echo "Commit log saved: $SNAPSHOT_DIR/$TIMESTAMP.json"