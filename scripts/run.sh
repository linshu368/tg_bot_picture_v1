cat > scripts/run.sh <<'EOF'
#!/usr/bin/env bash
set -e

echo "[run] python: $(which python)"

if [ -f requirements.txt ]; then
  echo "[run] installing deps from requirements.txt"
  pip install -r requirements.txt
fi


if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs) || true
  echo "[run] loaded .env"
fi


echo "[run] starting service..."
python main.py
EOF

chmod +x scripts/run.sh
