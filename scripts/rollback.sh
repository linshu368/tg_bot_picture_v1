cat > scripts/rollback.sh <<'EOF'
#!/usr/bin/env bash
set -e

LAST_TAG=$(git tag --sort=-creatordate | head -n 1)
if [ -z "$LAST_TAG" ]; then
  echo "❌ no tag found"; exit 1
fi

echo "↩️  checkout to ${LAST_TAG}"
git checkout "${LAST_TAG}"

echo "ℹ️  Now at a detached HEAD on tag ${LAST_TAG}."
echo "ℹ️  Run your app:  sh scripts/run.sh"
echo "ℹ️  Resume dev later: git checkout main"
EOF

chmod +x scripts/rollback.sh
