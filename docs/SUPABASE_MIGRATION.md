# Supabase数据库迁移指南

本文档详细说明了如何将Telegram机器人项目从SQLite迁移到Supabase。

## 📋 迁移概述

### 为什么选择Supabase？

1. **云端托管** - 无需自行管理数据库服务器
2. **PostgreSQL** - 更强大的关系型数据库
3. **实时功能** - 支持实时数据同步
4. **自动备份** - 数据安全有保障
5. **扩展性好** - 支持高并发访问
6. **REST API** - 自动生成RESTful API

### 迁移内容

- ✅ 用户表 (users)
- ✅ 积分记录表 (point_records)
- 🔄 每日签到表 (daily_checkins)
- 🔄 用户会话表 (user_sessions)
- 🔄 支付订单表 (payment_orders)
- 🔄 系统配置表 (system_config)
- 🔄 会话记录表 (session_records)
- 🔄 用户行为记录表 (user_action_records)

## 🚀 迁移步骤

### 1. 设置Supabase项目

1. 访问 [Supabase官网](https://supabase.com/)
2. 注册账号并创建新项目
3. 获取项目的URL和API密钥

### 2. 安装依赖

```bash
# 安装新的依赖包
pip install supabase==2.3.4 asyncpg==0.29.0
```

### 3. 配置环境变量

创建`.env`文件，添加Supabase配置：

```bash
# Supabase数据库配置
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key  # 可选

# 其他现有配置保持不变
BOT_TOKEN=your_telegram_bot_token
# ...
```

### 4. 创建数据库表结构

在Supabase控制台的SQL编辑器中执行以下SQL：

```sql
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    uid TEXT UNIQUE NOT NULL,
    points INTEGER DEFAULT 50,
    level INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    session_count INTEGER DEFAULT 0,
    total_points_spent INTEGER DEFAULT 0,
    total_paid_amount DECIMAL DEFAULT 0.0,
    first_add BOOLEAN DEFAULT false,
    utm_source TEXT DEFAULT '000',
    first_active_time TIMESTAMPTZ,
    last_active_time TIMESTAMPTZ,
    total_messages_sent INTEGER DEFAULT 0
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_uid ON users(uid);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- 积分记录表
CREATE TABLE IF NOT EXISTS point_records (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    points_change INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    points_balance INTEGER DEFAULT 0
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_point_records_user_id ON point_records(user_id);
CREATE INDEX IF NOT EXISTS idx_point_records_created_at ON point_records(created_at);
CREATE INDEX IF NOT EXISTS idx_point_records_action_type ON point_records(action_type);

-- 其他表的完整SQL请参考 scripts/supabase_tables.sql
```

### 5. 测试连接

运行测试脚本验证配置：

```bash
python scripts/test_supabase.py
```

如果看到类似输出，说明配置正确：

```
✅ Supabase连接测试通过
✅ 用户创建测试通过
✅ 用户获取测试通过
✅ 用户更新测试通过
✅ 积分操作测试通过
✅ 积分记录测试通过
✅ 查询操作测试通过
🎉 所有测试通过！Supabase配置正确。
```

### 6. 迁移现有数据

如果您有现有的SQLite数据需要迁移：

```bash
python scripts/migrate_to_supabase.py
```

### 7. 更新应用配置

应用已经自动配置为使用Supabase，无需额外修改。

### 8. 启动应用

```bash
python main.py
```

## 🔧 技术细节

### 架构变更

#### 原有架构 (SQLite)
```
DatabaseManager (SQLite) 
    ↓
BaseRepository 
    ↓
UserRepository, PointRecordRepository, ...
```

#### 新架构 (Supabase)
```
SupabaseManager 
    ↓
SupabaseBaseRepository 
    ↓
SupabaseUserRepository, SupabasePointRecordRepository, ...
```

### 主要变更

1. **数据库管理器**
   - `DatabaseManager` → `SupabaseManager`
   - `aiosqlite` → `supabase-py`

2. **Repository层**
   - `BaseRepository` → `SupabaseBaseRepository`
   - SQL查询 → Supabase客户端API调用

3. **数据类型映射**
   - `INTEGER` → `BIGINT`
   - `TIMESTAMP` → `TIMESTAMPTZ`
   - `BOOLEAN` → `BOOLEAN`
   - `TEXT` → `TEXT`
   - `REAL` → `DECIMAL`

### 性能优化

1. **索引优化** - 为常用查询字段创建索引
2. **连接池** - 使用连接池管理数据库连接
3. **批量操作** - 支持批量插入和更新
4. **查询优化** - 使用Supabase的查询优化器

## 🛠️ 故障排除

### 常见问题

#### 1. 连接失败
```
❌ Supabase连接测试失败: Could not connect to server
```

**解决方案：**
- 检查`SUPABASE_URL`和`SUPABASE_KEY`是否正确
- 确认网络连接正常
- 验证Supabase项目是否正常运行

#### 2. 权限错误
```
❌ 用户创建测试失败: insufficient_privilege
```

**解决方案：**
- 检查API密钥权限
- 使用Service Role Key（仅在服务端）
- 检查Row Level Security (RLS) 设置

#### 3. 表不存在
```
❌ 用户创建测试失败: relation "users" does not exist
```

**解决方案：**
- 确认已在Supabase控制台创建所有必要的表
- 检查表名是否正确
- 验证SQL脚本是否执行成功

#### 4. 数据类型错误
```
❌ 迁移用户失败: invalid input syntax for type bigint
```

**解决方案：**
- 检查数据迁移脚本中的数据类型转换
- 确认源数据格式正确
- 处理NULL值和空字符串

### 调试技巧

1. **启用详细日志**
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **检查Supabase日志**
   - 在Supabase控制台查看实时日志
   - 监控API调用和错误

3. **验证数据一致性**
   ```python
   # 比较迁移前后的数据
   python scripts/verify_migration.py
   ```

## 📊 性能监控

### 关键指标

1. **响应时间** - API调用延迟
2. **连接数** - 并发连接数量
3. **查询性能** - 复杂查询的执行时间
4. **错误率** - 失败的操作比例

### 监控工具

- **Supabase Dashboard** - 内置监控面板
- **应用日志** - 结构化日志记录
- **自定义监控** - 使用monitoring模块

## 🔒 安全考虑

1. **API密钥管理**
   - 使用环境变量存储敏感信息
   - 定期轮换API密钥
   - 区分开发和生产环境

2. **Row Level Security (RLS)**
   - 启用RLS保护敏感数据
   - 设置适当的访问策略
   - 限制用户只能访问自己的数据

3. **网络安全**
   - 使用HTTPS加密传输
   - 配置防火墙规则
   - 限制访问IP范围

## 📚 参考资源

- [Supabase官方文档](https://supabase.com/docs)
- [Supabase Python客户端](https://github.com/supabase/supabase-py)
- [PostgreSQL文档](https://www.postgresql.org/docs/)
- [项目架构文档](../README.md)

## 🤝 支持

如果在迁移过程中遇到问题，请：

1. 查看日志文件了解详细错误信息
2. 参考本文档的故障排除部分
3. 检查Supabase项目状态和配置
4. 创建Issue并提供详细的错误信息

---

**注意：** 在生产环境进行迁移前，请务必：
- 备份现有数据
- 在测试环境充分验证
- 制定回滚计划
- 通知相关用户可能的服务中断 