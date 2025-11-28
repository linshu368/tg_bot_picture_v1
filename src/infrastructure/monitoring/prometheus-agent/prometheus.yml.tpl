global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'railway-tg-bot'
    scheme: https
    static_configs:
      # 你的应用公网地址（Prometheus 会自动添加 /metrics）
      - targets: ['tgbotpicturev1-production.up.railway.app:443']

remote_write:
  - url: "${GRAFANA_REMOTE_URL}"
    basic_auth:
      username: "${GRAFANA_USERNAME}"
      password: "${GRAFANA_PASSWORD}"
