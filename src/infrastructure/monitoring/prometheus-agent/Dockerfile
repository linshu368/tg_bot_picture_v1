FROM prom/prometheus:v2.45.0

# 切换到 root 用户以处理文件权限
USER root

# 复制配置模板（从子目录复制）
COPY src/infrastructure/monitoring/prometheus-agent/prometheus.yml.tpl \
     /etc/prometheus/prometheus.yml.tpl

# 复制启动脚本（从子目录复制）
COPY src/infrastructure/monitoring/prometheus-agent/entrypoint.sh \
     /etc/prometheus/entrypoint.sh

# 赋予执行权限
RUN chmod +x /etc/prometheus/entrypoint.sh

# 切换回 nobody 用户 (Prometheus 默认运行用户)
USER nobody

# 设置入口点
ENTRYPOINT ["/etc/prometheus/entrypoint.sh"]
