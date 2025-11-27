FROM grafana/alloy:latest

# 暴露调试端口（可选）
EXPOSE 12345

# 复制配置文件到容器内
COPY config.alloy /etc/alloy/config.alloy

# 启动 Alloy
# --server.http.listen-addr 用于本地调试界面
ENTRYPOINT ["/bin/alloy", "run", "/etc/alloy/config.alloy", "--server.http.listen-addr=0.0.0.0:12345"]

