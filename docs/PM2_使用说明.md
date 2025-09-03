# Telegram Bot PM2 管理指南

## 🚀 概述

本指南将帮助你使用 PM2 来管理 Telegram Bot，避免与其他进程冲突，并提供更好的进程管理功能。

## 📋 安装要求

### 1. 安装 Node.js 和 npm
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nodejs npm

# 验证安装
node --version
npm --version
```

### 2. 安装 PM2
```bash
# 全局安装 PM2
sudo npm install -g pm2

# 验证安装
pm2 --version
```

## 🛠️ 配置文件说明

### `ecosystem.config.js`
这是 PM2 的主配置文件，当前使用的关键配置：

- **name**: 应用名称 `tg-bot-picture`
- **script**: 入口脚本 `main.py`
- **interpreter**: Python 解释器 `/home/tg_bot_picture_v1/venv/bin/python3`（已锁定到项目 venv）
- **cwd**: 工作目录 `/home/tg_bot_picture_v1`
- **instances**: `1`（单实例，避免端口冲突）
- **exec_mode**: `fork`
- **autorestart**: `true`
- **max_memory_restart**: `1G`
- **out_file**: `/home/tg_bot_picture_v1/logs/pm2-out.log`
- **error_file**: `/home/tg_bot_picture_v1/logs/pm2-error.log`
- **merge_logs**: `true`
- **time**: `true`
- **log_date_format**: `YYYY-MM-DD HH:mm:ss Z`
- **restart_delay**: `4000`
- **kill_timeout**: `3000`
- **env**: 环境变量（默认包含 `PYTHONUNBUFFERED: '1'`，可按需增加如 `BOT_TOKEN` 等）

## 🎮 使用方法

### 方法一：使用管理脚本 (推荐)

我们提供了一个方便的管理脚本 `pm2_manager.sh`：

```bash
# 进入项目目录
cd /home/tg_bot_picture_v1

# 启动 Bot
./pm2_manager.sh start

# 查看状态
./pm2_manager.sh status

# 查看日志
./pm2_manager.sh logs

# 重启 Bot
./pm2_manager.sh restart

# 停止 Bot
./pm2_manager.sh stop

# 查看帮助
./pm2_manager.sh help
```

### 方法二：直接使用 PM2 命令

```bash
# 进入项目目录
cd /home/tg_bot_picture_v1

# 启动应用
pm2 start ecosystem.config.js

# 查看所有进程状态
pm2 status

# 查看特定应用信息
pm2 info tg-bot-picture

# 查看日志
pm2 logs tg-bot-picture

# 重启应用
pm2 restart tg-bot-picture

# 停止应用
pm2 stop tg-bot-picture

# 删除应用
pm2 delete tg-bot-picture

# 保存当前进程列表
pm2 save

# 重启后自动启动已保存的进程
pm2 startup
```

## 📊 监控和管理

### 实时监控
```bash
# 打开 PM2 监控界面
pm2 monit
```

### 日志管理
PM2 日志路径：`/home/tg_bot_picture_v1/logs/pm2-out.log`（标准输出）与 `/home/tg_bot_picture_v1/logs/pm2-error.log`（错误输出）
```bash
# 查看实时日志
pm2 logs tg-bot-picture

# 查看错误日志
pm2 logs tg-bot-picture --err

# 清空日志
pm2 flush
```

### 进程管理
```bash
# 查看详细信息
pm2 describe tg-bot-picture

# 重新加载配置
pm2 reload ecosystem.config.js

# 重启所有应用
pm2 restart all
```

## 🔧 高级配置

### 开机自启动
```bash
# 生成启动脚本
pm2 startup

# 保存当前进程列表
pm2 save

# 取消开机自启动
pm2 unstartup
```

### 环境变量管理
在 `ecosystem.config.js` 的 `env` 字段中设置环境变量，例如：

```javascript
env: {
  PYTHONUNBUFFERED: '1',
  BOT_TOKEN: 'your_bot_token',
  // 其他环境变量...
}
```

## 🚨 故障排除

### 常见问题

1. **PM2 命令未找到**
   ```bash
   # 重新安装 PM2
   sudo npm install -g pm2
   ```

2. **权限问题**
   ```bash
   # 给脚本添加执行权限
   chmod +x pm2_manager.sh
   ```

3. **端口冲突**
   - 检查 `main.py` 中的端口配置
   - 确保端口 5002 没有被其他服务占用

4. **Python 环境问题**
   ```bash
   # 确保 Python3 和依赖已安装
   python3 --version
   pip3 install -r requirements.txt
   ```

### 查看错误日志
```bash
# 查看 PM2 错误日志
pm2 logs tg-bot-picture --err

# 查看应用自己的日志
tail -f logs/bot_v1.log
```

## 🌟 优势

使用 PM2 管理 Telegram Bot 的优势：

✅ **自动重启**: 进程崩溃时自动重启  
✅ **内存监控**: 内存使用过高时自动重启  
✅ **日志管理**: 统一的日志收集和查看  
✅ **进程隔离**: 避免与其他应用冲突  
✅ **监控界面**: 实时查看进程状态  
✅ **开机自启**: 系统重启后自动启动  
✅ **零停机重启**: 平滑重启应用  

## 📞 常用命令速查

| 命令 | 说明 |
|------|------|
| `pm2 start ecosystem.config.js` | 启动应用 |
| `pm2 stop tg-bot-picture` | 停止应用 |
| `pm2 restart tg-bot-picture` | 重启应用 |
| `pm2 status` | 查看状态 |
| `pm2 logs tg-bot-picture` | 查看日志 |
| `pm2 monit` | 监控界面 |
| `pm2 save` | 保存进程列表 |
| `pm2 startup` | 配置开机自启 |

---

