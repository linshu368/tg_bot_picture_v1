# Webhook 服务使用指南

## 概述

`tg_bot_picture_v1` 项目现在支持独立的 webhook 服务，用于处理支付回调。该服务可以独立于主 Bot 应用运行，提供更好的可靠性和可维护性。

## 主要特性

### ✅ 已解决的问题

1. **端口冲突** - 使用端口 5002，避免与旧版本项目（端口 5001）冲突
2. **独立日志** - 专用的日志文件 `logs/payment_webhook_v1.log`
3. **独立运行** - 可单独启动 webhook 服务，无需启动整个 Bot 应用
4. **健康检查** - 提供状态检查端点
5. **管理脚本** - 便捷的服务管理工具

### 🚀 新增功能

- **独立启动脚本** - `start_payment_webhook.py`
- **服务管理脚本** - `scripts/manage_webhook.sh`
- **健康检查端点** - `/payment/health`
- **状态查询端点** - `/payment/status`
- **专用日志配置** - 文件 + 控制台双重日志

## 使用方法

### 1. 独立启动 Webhook 服务

```bash
cd tg_bot_picture_v1
python3 start_payment_webhook.py
```

### 2. 使用管理脚本

```bash
# 启动服务
./scripts/manage_webhook.sh start

# 检查状态
./scripts/manage_webhook.sh status

# 查看日志
./scripts/manage_webhook.sh logs

# 重启服务
./scripts/manage_webhook.sh restart

# 停止服务
./scripts/manage_webhook.sh stop
```

## 服务端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/payment/notify` | GET/POST | 支付异步通知 |
| `/payment/return` | GET | 支付跳转通知 |
| `/payment/health` | GET | 健康状态检查 |
| `/payment/status` | GET | 服务状态和信息 |

## 配置信息

### 端口配置
- **V1 项目**: 端口 5002
- **旧版本**: 端口 5001

### 日志文件
- **主应用**: `logs/bot_v1.log`
- **Webhook服务**: `logs/payment_webhook_v1.log`

### 支付回调URL
```
PAYMENT_NOTIFY_URL = "http://108.61.188.236:5002/payment/notify"
PAYMENT_RETURN_URL = "http://108.61.188.236:5002/payment/return"
```

## 架构优势

### 相比旧版本的改进

1. **模块化设计** - 使用依赖注入容器管理组件
2. **异步支持** - 完整的异步数据库操作
3. **更好的错误处理** - 完善的异常处理和日志记录
4. **独立部署** - 支持独立运行和主应用集成运行
5. **健康监控** - 内置健康检查和状态监控

### 依赖管理

V1 项目通过容器自动管理以下依赖：
- `DatabaseManager` - 数据库管理
- `PaymentService` - 支付业务逻辑
- `UserService` - 用户服务
- `PaymentAPI` - 支付API客户端
- `TelegramBot` - 机器人实例

## 故障排查

### 常见问题

1. **端口被占用**
   ```bash
   # 检查端口占用
   netstat -tlnp | grep 5002
   
   # 强制停止服务
   ./scripts/manage_webhook.sh stop
   ```

2. **服务无响应**
   ```bash
   # 检查服务状态
   ./scripts/manage_webhook.sh status
   
   # 查看错误日志
   ./scripts/manage_webhook.sh logs
   ```

3. **数据库初始化失败**
   ```bash
   # 检查数据库文件权限
   ls -la data/telegram_bot_v2.db
   
   # 重新创建数据库目录
   mkdir -p data
   ```

### 日志分析

#### 正常启动日志示例
```
2025-07-31 10:50:09,246 - src.infrastructure.database.manager - INFO - 数据库初始化完成
2025-07-31 10:50:09,417 - __main__ - INFO - 支付webhook服务V1初始化成功
2025-07-31 10:50:09,417 - __main__ - INFO - 启动支付webhook服务V1在端口5002...
```

#### 错误日志关键词
- `no running event loop` - 异步事件循环问题
- `Address already in use` - 端口冲突
- `初始化失败` - 依赖注入或配置问题

## 开发和测试

### 健康检查
```bash
curl http://localhost:5002/payment/health
# 响应: {"service":"payment-webhook-v1","status":"ok"}
```

### 状态查询
```bash
curl http://localhost:5002/payment/status
# 响应: {"endpoints":[...], "service":"payment-webhook-v1", "status":"running", "version":"2.0"}
```

### 模拟支付回调
```bash
curl -X POST http://localhost:5002/payment/notify \
  -d "pid=1002&trade_no=test123&out_trade_no=order123&type=alipay&money=1.00&trade_status=TRADE_SUCCESS&sign=xxx"
```

## 部署建议

### 生产环境
1. 使用 systemd 服务管理
2. 配置 nginx 反向代理
3. 设置日志轮转
4. 监控服务状态

### 开发环境
1. 使用管理脚本快速启停
2. 实时查看日志输出
3. 独立测试支付功能

---

> **注意**: 该指南适用于 `tg_bot_picture_v1` 重构版项目。如需了解旧版本的使用方法，请参考旧项目的相关文档。 