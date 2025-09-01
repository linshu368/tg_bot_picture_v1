#!/bin/bash
#
# Service迁移模式切换脚本
# 支持一键切换所有Service的迁移模式：stable -> parallel_test -> migrated
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
APP_NAME="tg-bot-picture"  # PM2应用名称
PROJECT_DIR="/home/tg_bot_picture_v1"
LOG_FILE="/var/log/migration_switch.log"
BACKUP_FILE="/tmp/migration_mode_backup.env"

# 所有Service的环境变量
SERVICES=(
    "ACTION_RECORD_MIGRATION_MODE"
    "SESSION_SERVICE_MIGRATION_MODE"
    "IMAGE_SERVICE_MIGRATION_MODE"
    "PAYMENT_SERVICE_MIGRATION_MODE"  
    "USER_SERVICE_MIGRATION_MODE"
)

# 日志函数
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

# 显示当前模式
show_current_mode() {
    echo -e "${BLUE}📋 当前迁移模式:${NC}"
    for service in "${SERVICES[@]}"; do
        current=$(printenv "$service" || echo "stable")
        echo "  $service: $current"
    done
    echo
}

# 备份当前环境变量
backup_current_mode() {
    log "备份当前迁移模式配置..."
    
    echo "# Migration mode backup - $(date)" > "$BACKUP_FILE"
    for service in "${SERVICES[@]}"; do
        current=$(printenv "$service" || echo "stable")
        echo "export $service=\"$current\"" >> "$BACKUP_FILE"
    done
    
    log "配置已备份到: $BACKUP_FILE"
}

# 设置所有Service为指定模式
set_all_modes() {
    local mode=$1
    
    if [[ ! "$mode" =~ ^(stable|parallel_test|migrated)$ ]]; then
        error "无效的迁移模式: $mode"
        echo "支持的模式: stable, parallel_test, migrated"
        exit 1
    fi
    
    log "设置所有Service为 $mode 模式..."
    
    # 更新环境变量
    for service in "${SERVICES[@]}"; do
        export "$service"="$mode"
        echo "export $service=\"$mode\"" >> ~/.bashrc
        log "  $service -> $mode"
    done
    
    # 创建环境变量文件供PM2使用
    local env_file="$PROJECT_DIR/.env"
    log "更新环境变量文件: $env_file"
    
    # 备份原文件（如果存在）
    if [[ -f "$env_file" ]]; then
        cp "$env_file" "${env_file}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # 更新或创建.env文件
    for service in "${SERVICES[@]}"; do
        if [[ -f "$env_file" ]] && grep -q "^$service=" "$env_file"; then
            # 更新现有变量
            sed -i "s/^$service=.*/$service=$mode/" "$env_file"
        else
            # 添加新变量
            echo "$service=$mode" >> "$env_file"
        fi
    done
    
    log "环境变量设置完成"
}

# 重启服务
restart_service() {
    log "重启服务: $APP_NAME"
    
    cd "$PROJECT_DIR"
    
    # 检查PM2是否安装
    if ! command -v pm2 &> /dev/null; then
        error "❌ PM2 未安装！请先安装PM2"
        exit 1
    fi
    
    # 检查应用是否在PM2中运行
    if pm2 list | grep -q "$APP_NAME"; then
        # 应用存在，重启它
        pm2 restart "$APP_NAME"
        sleep 5
        
        # 检查应用状态
        if pm2 list | grep "$APP_NAME" | grep -q "online"; then
            log "✅ 服务重启成功"
        else
            error "❌ 服务重启失败"
            pm2 status "$APP_NAME"
            exit 1
        fi
    else
        warn "应用未在PM2中运行，启动服务..."
        # 使用pm2_manager.sh启动
        if [[ -f "$PROJECT_DIR/pm2_manager.sh" ]]; then
            bash "$PROJECT_DIR/pm2_manager.sh" start
        else
            # 直接启动
            pm2 start ecosystem.config.js
            pm2 save
        fi
        
        sleep 5
        
        if pm2 list | grep "$APP_NAME" | grep -q "online"; then
            log "✅ 服务启动成功"
        else
            error "❌ 服务启动失败"
            exit 1
        fi
    fi
}

# 验证切换结果
verify_switch() {
    local expected_mode=$1
    
    log "验证模式切换结果..."
    
    # 等待服务完全启动
    sleep 10
    
    # 检查PM2日志中的模式确认信息
    local log_patterns=(
        "🔧 ActionRecordService:"
        "🔧 UserService:" 
        "🔧 ImageService:"
        "🔧 PaymentService:"
        "🔧 SessionService:"
    )
    
    local success=true
    for pattern in "${log_patterns[@]}"; do
        # 使用PM2日志检查
        if pm2 logs "$APP_NAME" --lines 100 --nostream | grep -q "$pattern"; then
            log "✅ 检测到Service初始化日志: $pattern"
        else
            warn "⚠️  未检测到Service初始化日志: $pattern"
            success=false
        fi
    done
    
    if [[ "$success" == "true" ]]; then
        log "🎉 模式切换验证成功！"
    else
        warn "模式切换可能存在问题，请检查应用日志"
        log "💡 可以运行以下命令查看详细日志："
        log "   pm2 logs $APP_NAME"
    fi
}

# 显示使用说明
show_usage() {
    echo -e "${BLUE}Service迁移模式切换脚本${NC}"
    echo
    echo "用法: $0 [OPTIONS] <MODE>"
    echo
    echo "模式:"
    echo "  stable        - 稳定模式，使用旧Repository"
    echo "  parallel_test - 并行测试模式，验证新Repository"
    echo "  migrated      - 迁移完成模式，使用新Repository"
    echo
    echo "选项:"
    echo "  -s, --status  - 显示当前模式状态"
    echo "  -r, --rollback- 回滚到备份的模式"
    echo "  -h, --help    - 显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0 parallel_test    # 切换到并行测试模式"
    echo "  $0 stable           # 回滚到稳定模式"
    echo "  $0 -s               # 显示当前状态"
    echo "  $0 -r               # 回滚到备份的模式"
    echo
}

# 回滚到备份的模式
rollback_mode() {
    if [[ ! -f "$BACKUP_FILE" ]]; then
        error "未找到备份文件: $BACKUP_FILE"
        exit 1
    fi
    
    log "从备份文件回滚迁移模式..."
    
    # 加载备份的环境变量
    source "$BACKUP_FILE"
    
    # 应用到当前环境和systemd
    for service in "${SERVICES[@]}"; do
        local value=$(grep "export $service=" "$BACKUP_FILE" | cut -d'"' -f2)
        export "$service"="$value"
        log "  $service -> $value"
    done
    
    # 重启服务
    restart_service
    verify_switch "rollback"
    
    log "🎉 回滚完成！"
}

# 主函数
main() {
    case "${1:-}" in
        -h|--help)
            show_usage
            exit 0
            ;;
        -s|--status)
            show_current_mode
            exit 0
            ;;
        -r|--rollback)
            rollback_mode
            exit 0
            ;;
        stable|parallel_test|migrated)
            local target_mode=$1
            
            log "🚀 开始切换Service迁移模式: $target_mode"
            
            # 显示当前状态
            show_current_mode
            
            # 备份当前配置
            backup_current_mode
            
            # 设置新模式
            set_all_modes "$target_mode"
            
            # 重启服务
            restart_service
            
            # 验证结果
            verify_switch "$target_mode"
            
            log "🎉 迁移模式切换完成: $target_mode"
            echo
            echo -e "${GREEN}下一步建议:${NC}"
            if [[ "$target_mode" == "parallel_test" ]]; then
                echo "  - 运行监控脚本: python scripts/monitor_consistency.py daemon"
                echo "  - 观察一致性率，目标 >95%"
                echo "  - 监控日志: tail -f /var/log/consistency_monitor.log"
                echo "  - 查看应用日志: pm2 logs $APP_NAME"
            elif [[ "$target_mode" == "migrated" ]]; then
                echo "  - 监控系统稳定性"
                echo "  - 准备清理旧Repository相关代码"
                echo "  - 查看应用状态: pm2 status"
            fi
            ;;
        "")
            error "缺少参数"
            show_usage
            exit 1
            ;;
        *)
            error "无效参数: $1"
            show_usage
            exit 1
            ;;
    esac
}

# 检查权限
if [[ $EUID -eq 0 ]]; then
    warn "检测到root权限，建议使用普通用户运行PM2应用"
fi

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

# 执行主函数
main "$@" 