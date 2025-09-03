#!/usr/bin/env bash
set -e

show_help() {
  echo "用法:"
  echo "  rollback.sh [tag]      回滚到指定 tag"
  echo "  rollback.sh            回滚到最新 tag"
  echo "  rollback.sh --list     列出最近 5 个 tag"
  exit 0
}

# 如果传入 --list
if [ "$1" = "--list" ]; then
  echo "📌 最近 5 个 tag:"
  git tag --sort=-creatordate | head -n 5
  exit 0
fi

# 如果传入 tag，则使用该 tag，否则取最新
TARGET_TAG=${1:-$(git tag --sort=-creatordate | head -n 1)}

if [ -z "$TARGET_TAG" ]; then
  echo "❌ 未找到任何 tag"
  exit 1
fi

echo "↩️  checkout to ${TARGET_TAG}"
git checkout "${TARGET_TAG}"

echo "ℹ️  现在处于 detached HEAD 状态 (tag: ${TARGET_TAG})"
echo "   - 你不在任何分支上，只是指向该快照"
echo "   - commit 会生成悬空提交，不要直接开发"
echo "   - 如果要基于此版本开发，请新建分支:"
echo "       git switch -c hotfix/from-${TARGET_TAG}"
echo "   - 开发完成后再合并回 main"
echo ""
echo "ℹ️  验证应用可运行:"
echo "       sh scripts/run.sh"
echo "ℹ️  恢复到开发分支:"
echo "       git checkout main"
