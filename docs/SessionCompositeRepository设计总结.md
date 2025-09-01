# 组合Repository V2 文档

## 概述

组合Repository模块负责跨表操作的复杂业务逻辑，封装多个单表Repository的协同工作，对外提供简洁的业务接口。

## 设计原则

1. **最小变更**：延续"一表一 repo"的基础模式，保证单表 CRUD 简洁
2. **解耦屏蔽**：repo 层屏蔽表结构细节，service 层不用感知数据库变化  
3. **渐进演进**：优先采用 表 repo + 组合 repo 模式，避免一次性重构

## 组合Repository列表

### 1. UserCompositeRepository
**职责**：用户生命周期管理
- 用户注册（users + wallet + stats + points）
- 签到奖励（checkins + wallet + points）
- 用户基础信息和关联数据的统一管理

### 2. PointCompositeRepository  
**职责**：积分流转管理
- 积分操作（wallet + points）- 增加/减少积分，记录流水
- 积分支付（payment + wallet + points）- 充值积分，更新钱包，记录订单和流水
- 任务积分扣除（wallet + tasks + points）- 创建任务，扣除积分，记录流水

### 3. SessionCompositeRepository ✨
**职责**：会话管理
- 会话创建（sessions + records + stats）- 创建会话关联，初始化记录，更新统计
- 会话结束（records + stats）- 关闭会话，更新统计数据
- 会话活动更新（records + stats）- 更新消息数量，活动时间
- 会话查询和统计分析

## SessionCompositeRepository 详细说明

### 核心功能

#### 1. 会话创建 `create_session()`
```python
result = await session_composite.create_session(
    user_id=123,
    session_id="optional-custom-id",  # 可选，不提供则自动生成UUID
    session_data={
        'started_at': '2024-01-01T10:00:00Z',
        'message_count_user': 0
    }
)
```

**涉及的表操作**：
- `user_sessions_v2`: 创建用户会话关联记录
- `session_records_v2`: 创建会话详细统计记录  
- `user_activity_stats_v2`: 更新用户会话计数和活动时间

#### 2. 会话结束 `end_session()`
```python
result = await session_composite.end_session(
    session_id="session-uuid",
    message_count_user=15,
    summary="用户咨询了产品功能"
)
```

**涉及的表操作**：
- `session_records_v2`: 设置结束时间，计算持续时间
- `user_activity_stats_v2`: 更新最后活跃时间和消息统计

#### 3. 会话活动更新 `update_session_activity()`
```python
result = await session_composite.update_session_activity(
    session_id="session-uuid",
    message_count=20,
    update_stats=True
)
```

#### 4. 查询接口
- `get_session_info()`: 获取完整会话信息（基础信息+详细记录）
- `get_user_sessions()`: 获取用户会话列表（可包含详细信息）
- `get_user_session_stats()`: 获取用户会话统计（时期统计+总体统计）
- `get_active_sessions()`: 获取活跃会话
- `check_session_exists()`: 检查会话存在性

#### 5. 清理和维护
- `cleanup_old_sessions()`: 清理旧会话数据
- `cleanup_user_sessions()`: 清理指定用户的所有会话

### 事务管理

使用简单的事务管理机制，确保跨表操作的一致性：
- 提供回滚操作列表
- 异常时自动执行回滚
- 记录详细的操作日志

### 响应格式

所有接口都返回标准化的响应格式：
```python
{
    'success': True/False,
    'message': '操作结果描述',
    'data': {
        # 具体的业务数据
    }
}
```

## 使用示例

```python
# 初始化
session_composite = SessionCompositeRepository(supabase_manager)

# 创建会话
result = await session_composite.create_session(user_id=123)
session_id = result['data']['session_id']

# 更新会话活动
await session_composite.update_session_activity(session_id, message_count=5)

# 结束会话
await session_composite.end_session(session_id, message_count_user=10, summary="会话结束")

# 查询用户会话
sessions = await session_composite.get_user_sessions(user_id=123, limit=10)

# 获取统计信息
stats = await session_composite.get_user_session_stats(user_id=123, days=30)
```

## 下一步计划

1. **ActionCompositeRepository**：行为记录和统计分析
2. **集成测试**：编写跨表操作的完整性测试
3. **Service层迁移**：逐步替换Service层对单表Repository的直接调用
4. **性能优化**：优化跨表查询和批量操作 