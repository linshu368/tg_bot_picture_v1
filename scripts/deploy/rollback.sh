#!/usr/bin/env bash
set -euo pipefail

show_help() {
  echo "用法:"
  echo "  rollback.sh --list-tag          列出最近 5 个 tag"
  echo "  rollback.sh --list-commit TAG   列出某 tag 下最近的 commit"
  echo "  rollback.sh <commit_sha|tag>    回滚 main 到指定 commit 或 tag (会强推远程)"
  exit 0
}

# 列出最近 5 个 tag
if [ "${1:-}" = "--list-tag" ]; then
  echo "📌 最近 5 个 tag:"
  git tag --sort=-creatordate | head -n 5
  exit 0
fi

# 列出某个 tag 下的 commit
if [ "${1:-}" = "--list-commit" ]; then
  TAG=${2:-}
  if [ -z "$TAG" ]; then
    echo "❌ 缺少 tag 名称"
    exit 1
  fi
  echo "🔎 ${TAG} 下的最近 5 个 commit:"
  git log "$TAG" --oneline -n 5
  exit 0
fi

# 如果没有参数，提示帮助
if [ $# -lt 1 ]; then
  show_help
fi

TARGET=$1

# 确认 main 在最新状态
git fetch origin main
git checkout main
git pull origin main

# 创建备份 tag
BACKUP_TAG="backup-before-rollback-$(date +%F_%H%M%S)"
git tag "$BACKUP_TAG"
git push origin "$BACKUP_TAG"
echo "✅ 已创建备份 tag: $BACKUP_TAG"

# 回退 main 到目标 commit/tag
echo "↩️  回滚 main 到 $TARGET ..."
git reset --hard "$TARGET"

# 强推远程
git push origin main -f

echo "✅ main 已成功回滚到 $TARGET"
echo "ℹ️  如果要恢复，可以 checkout 或 reset 到备份 tag:"
echo "       git checkout $BACKUP_TAG"
