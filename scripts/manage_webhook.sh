#!/bin/bash
# webhook 服务管理脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEBHOOK_SCRIPT="$PROJECT_DIR/start_payment_webhook.py"
PID_FILE="$PROJECT_DIR/logs/webhook.pid"
LOG_FILE="$PROJECT_DIR/logs/payment_webhook_v1.log"

function start_webhook() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            echo "❌ Webhook服务已在运行 (PID: $pid)"
            return 1
        else
            echo "🧹 清理过期的PID文件"
            rm -f "$PID_FILE"
        fi
    fi

    echo "🚀 启动Webhook服务..."
    cd "$PROJECT_DIR"
    nohup python3 "$WEBHOOK_SCRIPT" > /dev/null 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"
    
    sleep 3
    if ps -p $pid > /dev/null 2>&1; then
        echo "✅ Webhook服务启动成功 (PID: $pid)"
        echo "📋 端口: 5002"
        echo "📄 日志文件: $LOG_FILE"
        echo "🔗 健康检查: http://localhost:5002/payment/health"
        return 0
    else
        echo "❌ Webhook服务启动失败"
        rm -f "$PID_FILE"
        return 1
    fi
}

function stop_webhook() {
    if [ ! -f "$PID_FILE" ]; then
        echo "❌ Webhook服务未运行"
        return 1
    fi

    local pid=$(cat "$PID_FILE")
    if ps -p $pid > /dev/null 2>&1; then
        echo "🛑 停止Webhook服务 (PID: $pid)..."
        kill $pid
        sleep 2
        
        if ps -p $pid > /dev/null 2>&1; then
            echo "⚠️ 正常终止失败，强制停止..."
            kill -9 $pid
        fi
        
        rm -f "$PID_FILE"
        echo "✅ Webhook服务已停止"
    else
        echo "❌ Webhook服务进程不存在"
        rm -f "$PID_FILE"
    fi
}

function status_webhook() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            echo "✅ Webhook服务正在运行 (PID: $pid)"
            echo "📋 端口: 5002"
            if command -v curl > /dev/null 2>&1; then
                echo "🔍 健康状态检查..."
                local health=$(curl -s http://localhost:5002/payment/health 2>/dev/null)
                if [ $? -eq 0 ]; then
                    echo "✅ 服务响应正常: $health"
                else
                    echo "❌ 服务无响应"
                fi
            fi
        else
            echo "❌ Webhook服务未运行（PID文件过期）"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ Webhook服务未运行"
    fi
}

function show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "📄 最近的日志内容："
        tail -20 "$LOG_FILE"
    else
        echo "❌ 日志文件不存在: $LOG_FILE"
    fi
}

function restart_webhook() {
    echo "🔄 重启Webhook服务..."
    stop_webhook
    sleep 2
    start_webhook
}

case "$1" in
    start)
        start_webhook
        ;;
    stop)
        stop_webhook
        ;;
    status)
        status_webhook
        ;;
    restart)
        restart_webhook
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "用法: $0 {start|stop|status|restart|logs}"
        echo ""
        echo "命令说明："
        echo "  start   - 启动Webhook服务"
        echo "  stop    - 停止Webhook服务"
        echo "  status  - 查看服务状态"
        echo "  restart - 重启服务"
        echo "  logs    - 查看最近的日志"
        exit 1
        ;;
esac

exit $? 