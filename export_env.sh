#!/bin/bash
echo "Pulling Railway variables into .env ..."
railway variables | sed -n 's/^║ \([^│]*\) │ \([^│]*\).*$/\1=\2/p' | sed 's/[[:space:]]*$//' > .env
echo "✅ Done. Saved to .env"
