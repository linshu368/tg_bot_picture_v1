#!/bin/bash

# Telegram Bot PM2 管理脚本
# 使用方法: ./pm2_manager.sh [start|stop|restart|status|logs|delete]

APP_NAME="tg-bot-picture"
PROJECT_DIR="/home/tg_bot_picture_v1"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查PM2是否安装
check_pm2() {
    if ! command -v pm2 &> /dev/null; then
        echo -e "${RED}❌ PM2 未安装！${NC}"
        echo -e "${YELLOW}请运行以下命令安装PM2:${NC}"
        echo "  npm install -g pm2"
        echo "  或者"
        echo "  sudo npm install -g pm2"
        exit 1
    fi
}

# 启动应用
start_app() {
    echo -e "${BLUE}🚀 启动 Telegram Bot...${NC}"
    cd "$PROJECT_DIR"
    pm2 start ecosystem.config.js
    pm2 save
    echo -e "${GREEN}✅ Bot 启动完成！${NC}"
}

# 停止应用
stop_app() {
    echo -e "${YELLOW}🛑 停止 Telegram Bot...${NC}"
    pm2 stop "$APP_NAME"
    echo -e "${GREEN}✅ Bot 已停止！${NC}"
}

# 重启应用
restart_app() {
    echo -e "${BLUE}🔄 重启 Telegram Bot...${NC}"
    pm2 restart "$APP_NAME"
    echo -e "${GREEN}✅ Bot 重启完成！${NC}"
}

# 查看状态
status_app() {
    echo -e "${BLUE}📊 查看应用状态...${NC}"
    pm2 status
    echo ""
    pm2 info "$APP_NAME"
}

# 查看日志
logs_app() {
    echo -e "${BLUE}📋 查看实时日志...${NC}"
    pm2 logs "$APP_NAME" --lines 50
}

# 删除应用
delete_app() {
    echo -e "${RED}🗑️  删除 PM2 应用...${NC}"
    pm2 delete "$APP_NAME"
    echo -e "${GREEN}✅ 应用已从 PM2 中删除！${NC}"
}

# 显示监控界面
monitor_app() {
    echo -e "${BLUE}📊 打开 PM2 监控界面...${NC}"
    pm2 monit
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}=== Telegram Bot PM2 管理脚本 ===${NC}"
    echo ""
    echo "使用方法: $0 [命令]"
    echo ""
    echo "可用命令:"
    echo -e "  ${GREEN}start${NC}     - 启动 Bot"
    echo -e "  ${YELLOW}stop${NC}      - 停止 Bot"
    echo -e "  ${BLUE}restart${NC}   - 重启 Bot"
    echo -e "  ${BLUE}status${NC}    - 查看状态"
    echo -e "  ${BLUE}logs${NC}      - 查看日志"
    echo -e "  ${BLUE}monitor${NC}   - 打开监控界面"
    echo -e "  ${RED}delete${NC}    - 删除应用"
    echo -e "  ${BLUE}help${NC}      - 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start    # 启动 Bot"
    echo "  $0 logs     # 查看日志"
    echo "  $0 status   # 查看状态"
}

# 检查PM2是否安装
check_pm2

# 根据参数执行相应命令
case "$1" in
    "start")
        start_app
        ;;
    "stop")
        stop_app
        ;;
    "restart")
        restart_app
        ;;
    "status")
        status_app
        ;;
    "logs")
        logs_app
        ;;
    "monitor")
        monitor_app
        ;;
    "delete")
        delete_app
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    "")
        echo -e "${YELLOW}⚠️  请指定一个命令${NC}"
        show_help
        ;;
    *)
        echo -e "${RED}❌ 未知命令: $1${NC}"
        show_help
        exit 1
        ;;
esac 