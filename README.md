# Telegram Bot V2 - 重构版

基于模块化架构重构的Telegram图像处理机器人，遵循领域驱动设计(DDD)原则。

## 🏗️ 架构设计

### 目录结构

```
tg_bot_picture_v1/
├── main.py                    # 📍 应用程序入口点
├── requirements.txt           # 📦 Python依赖管理
├── ecosystem.config.js        # 🔧 PM2进程管理配置
├── pm2_manager.sh            # 🛠️ PM2管理脚本
├── README.md                 # 📚 项目文档
├── 快速启动.md               # 🚀 快速启动指南
│
├── src/                      # 💻 核心源代码目录
│   ├── __init__.py
│   │
│   ├── core/                 # 🔧 应用核心层
│   │   ├── __init__.py
│   │   ├── app.py           # 应用程序配置和初始化
│   │   ├── container.py     # 依赖注入容器 (DI Container)
│   │   └── lifecycle.py     # 应用生命周期管理
│   │
│   ├── domain/              # 🏛️ 领域层 - 业务逻辑核心
│   │   ├── models/          # 📊 领域模型/实体
│   │   └── services/        # 🔄 领域服务
│   │       ├── user_service.py           # 用户管理服务
│   │       ├── payment_service.py        # 支付处理服务
│   │       ├── image_service.py          # 图像处理服务
│   │       ├── session_service.py        # 会话管理服务
│   │       ├── system_config_service.py  # 系统配置服务
│   │       └── action_record_service.py  # 操作记录服务
│   │
│   ├── infrastructure/      # 🏗️ 基础设施层
│   │   ├── database/        # 💾 数据持久化
│   │   │   ├── __init__.py
│   │   │   ├── supabase_manager.py      # Supabase数据库管理器
│   │   │   └── repositories/            # 数据仓储模式实现
│   │   │       ├── __init__.py
│   │   │       ├── base_repository.py   # 基础仓储抽象
│   │   │       ├── user_repository.py   # 用户数据仓储
│   │   │       ├── supabase_user_repository.py
│   │   │       ├── supabase_payment_repository.py
│   │   │       ├── supabase_image_task_repository.py
│   │   │       ├── supabase_session_record_repository.py
│   │   │       ├── supabase_point_record_repository.py
│   │   │       ├── supabase_daily_checkin_repository.py
│   │   │       ├── supabase_user_session_repository.py
│   │   │       ├── supabase_user_action_record_repository.py
│   │   │       └── supabase_system_config_repository.py
│   │   │
│   │   ├── external_apis/   # 🌐 外部API集成
│   │   │   ├── __init__.py
│   │   │   ├── clothoff_api.py          # ClothOff图像处理API
│   │   │   └── payment_api.py           # 支付API集成
│   │   │
│   │   ├── messaging/       # 📨 消息处理基础设施
│   │   └── monitoring/      # 📊 监控和日志基础设施
│   │
│   ├── interfaces/          # 🔌 接口适配层
│   │   ├── telegram/        # 🤖 Telegram Bot接口
│   │   │   ├── bot.py                   # Telegram Bot主控制器
│   │   │   ├── ui_handler.py            # UI交互处理器
│   │   │   ├── user_state_manager.py    # 用户状态管理
│   │   │   └── handlers/                # 各种处理器
│   │   │       ├── callback_manager.py  # 回调处理管理器
│   │   │       ├── message_handlers.py  # 消息处理器
│   │   │       ├── image_processing.py  # 图像处理处理器
│   │   │       ├── callback/            # 回调处理器集合
│   │   │       └── command/             # 命令处理器集合
│   │   │
│   │   ├── web/             # 🌐 Web API接口
│   │   └── cli/             # 💻 命令行接口
│   │
│   └── utils/               # 🛠️ 通用工具层
│       ├── config/          # ⚙️ 配置管理
│       ├── constants/       # 📋 常量定义
│       └── helpers/         # 🔧 辅助函数
│
├── tests/                   # 🧪 测试代码目录
│   ├── test_telegram_bot.py             # Telegram Bot测试
│   ├── test_user_service.py             # 用户服务测试
│   ├── test_payment_service.py          # 支付服务测试
│   ├── test_image_service.py            # 图像服务测试
│   ├── test_clothoff_api.py             # ClothOff API测试
│   ├── test_database.py                 # 数据库测试
│   ├── test_supabase.py                 # Supabase集成测试
│   ├── test_integration.py              # 集成测试
│   ├── test_webhook_handler.py          # Webhook处理器测试
│   ├── quick_test.py                    # 快速测试脚本
│   └── setup_supabase.py                # Supabase设置脚本
│
├── scripts/                 # 📜 运维和数据库脚本目录
│   ├── migrate_to_supabase.py           # Supabase迁移脚本
│   ├── check_migration_status.py        # 迁移状态检查
│   ├── supabase_tables.sql              # 数据库表结构
│   ├── manage_webhook.sh                # Webhook管理脚本
│   └── test_integration.py              # 集成测试脚本
│
├── logs/                    # 📝 日志文件目录
├── data/                    # 📁 数据存储目录
└── docs/                    # 📖 文档目录
```
如果您想理解更详细的项目架构，请移步  docs/项目结构图.md 

### 架构层次
```
┌─────────────────────────────────────┐
│           接口适配层                  │  ← 处理外部请求/响应
│   (Telegram/Web/CLI Interfaces)     │
├─────────────────────────────────────┤
│            业务领域层                 │  ← 核心业务逻辑
│      (Domain Services & Models)     │
├─────────────────────────────────────┤
│           基础设施层                  │  ← 技术实现细节
│  (Database/APIs/Monitoring)         │
└─────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 环境准备
```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置设置
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件，设置您的Bot Token等
nano .env
```

### 3. 运行应用
```bash
# 启动机器人
python main.py
```

## 🔧 重构改进

### 与V1版本对比

**V1版本问题：**
- 单一大文件（telegram_bot.py 4000+行）
- 高耦合度，难以测试
- 配置分散，难以管理
- 无清晰的模块边界

**V2版本改进：**
- ✅ 模块化架构，单一职责
- ✅ 依赖注入，低耦合度
- ✅ 统一配置管理
- ✅ 清晰的层次分离
- ✅ 易于测试和扩展

### 设计原则

1. **单一职责** - 每个模块只负责一个业务领域
2. **依赖倒置** - 面向接口编程，而非具体实现
3. **开闭原则** - 对扩展开放，对修改关闭
4. **接口隔离** - 客户端不应依赖它不需要的接口

## 📝 开发指南

### 添加新功能
1. 在`domain/services/`中创建业务服务
2. 在`infrastructure/`中实现具体技术细节
3. 在`interfaces/telegram/handlers/`中添加用户接口
4. 在`container.py`中注册依赖关系

### 测试
```bash
# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行所有测试
pytest
```

## 🔄 迁移说明

这是原项目的重构版本，使用新的Bot Token以便于独立测试。

**迁移优势：**
- 渐进式重构，降低风险
- 保持功能完整性
- 提高代码质量
- 便于后续维护

## 📋 待办事项

- [ ] 完成数据库层重构
- [ ] 实现业务服务层
- [ ] 迁移Telegram接口层
- [ ] 添加单元测试
- [ ] 性能优化
- [ ] 文档完善 