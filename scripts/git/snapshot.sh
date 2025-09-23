# #!/usr/bin/env bash
# #可废弃
# set -e

# # 生成时间版号，如 v20250901-1530
# TAG="v$(date +%Y%m%d-%H%M)"
# MSG=${1:-"snapshot: ${TAG}"}

# # 兜底提交+推送（如果没有改动不会报错）
# git add -A
# git commit -m "${MSG}" || true
# git push origin main

# # 打标签并推送
# git tag "${TAG}"
# git push origin "${TAG}"

# echo "✅ snapshot created & pushed: ${TAG}"