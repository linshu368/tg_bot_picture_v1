#!/bin/sh

# 检查必要变量
if [ -z "$GRAFANA_REMOTE_URL" ]; then
  echo "Error: GRAFANA_REMOTE_URL is not set"
  exit 1
fi

# 使用 sed 替换模板中的环境变量
# 使用 | 作为分隔符以防止 URL 中的 / 冲突
sed -e "s|\${GRAFANA_REMOTE_URL}|$GRAFANA_REMOTE_URL|g" \
    -e "s|\${GRAFANA_USERNAME}|$GRAFANA_USERNAME|g" \
    -e "s|\${GRAFANA_PASSWORD}|$GRAFANA_PASSWORD|g" \
    /etc/prometheus/prometheus.yml.tpl > /etc/prometheus/prometheus.yml

echo "✅ Config generated. Starting Prometheus in Agent Mode..."

# 启动 Prometheus，开启 Agent 模式
exec /bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.agent.path=/prometheus \
    --enable-feature=agent
