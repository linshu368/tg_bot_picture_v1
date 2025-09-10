#!/usr/bin/env bash
set -euo pipefail

show_help() {
  echo "用法:"
  echo "  rollback.sh <commit_sha>    回滚 main 到指定 commit (会强推远程)"
  exit 0
}

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
# BACKUP_TAG="backup-before-rollback-$(date +%F_%H%M%S)"
# git tag "$BACKUP_TAG"
# git push origin "$BACKUP_TAG"
# echo "✅ 已创建备份 tag: $BACKUP_TAG"

# 回退 main 到目标 commit
echo "↩️  回滚 main 到 $TARGET ..."
git reset --hard "$TARGET"

# 强推远程
git push origin main -f

echo "✅ main 已成功回滚到 $TARGET"
# echo "ℹ️  如果要恢复，可以 checkout 或 reset 到备份 tag:"
# echo "       git checkout $BACKUP_TAG"
