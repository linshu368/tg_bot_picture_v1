# Service与组合Repository调用关系分析报告

基于V2表结构和跨表操作场景分析，本报告梳理了每个Service应该调用哪些组合Repository的详细映射关系。

---

## 📋 总体架构关系

```
Service Layer (业务逻辑层)
    ↓ 调用
Composite Repository Layer (组合Repository层)
    ↓ 协调
Single Repository Layer (单表Repository层)
    ↓ 操作
Database V2 Tables (V2数据库表)
```

---

## 🎯 Service与组合Repository调用关系

### 1. UserService → 主要调用多个组合Repository

#### 调用关系：
- **主要调用**: `UserCompositeRepository` 
- **次要调用**: `PointCompositeRepository`

#### 具体场景分析：

**🔸 用户注册场景 (register_user)**
```
调用: UserCompositeRepository.create()
跨表: users_v2 + user_wallet_v2 + user_activity_stats_v2 + point_records_v2
```

**🔸 每日签到场景 (daily_checkin)**  
```
调用: UserCompositeRepository.daily_checkin()
跨表: daily_checkins_v2 + user_wallet_v2 + point_records_v2
```

**🔸 积分操作场景 (add_points/consume_points)**
```
调用: PointCompositeRepository.add_points() / PointCompositeRepository.subtract_points()
跨表: user_wallet_v2 + point_records_v2
```

---

### 2. PaymentService → 主要调用PointCompositeRepository

#### 调用关系：
- **主要调用**: `PointCompositeRepository`

#### 具体场景分析：

**🔸 支付成功处理 (_process_payment_success)**
```
调用: PointCompositeRepository.process_payment_success()
跨表: payment_orders_v2 + user_wallet_v2 + point_records_v2
```

**🔸 订单管理 (create_order/query_order_status)**
```
调用: PointCompositeRepository 的订单相关方法
跨表: payment_orders_v2（单表操作为主）
```

---

### 3. ImageService → 主要调用PointCompositeRepository

#### 调用关系：
- **主要调用**: `PointCompositeRepository`

#### 具体场景分析：

**🔸 图像任务创建+积分扣除 (create_image_task)**
```
调用: PointCompositeRepository.create_task_with_points_deduction()
跨表: user_wallet_v2 + image_tasks_v2 + point_records_v2
```

**说明**: ImageService本身的任务管理可能还需要单独的ImageTaskRepository，但涉及积分扣除的场景必须通过PointCompositeRepository处理。

---

### 4. SessionService → 主要调用SessionCompositeRepository

#### 调用关系：
- **主要调用**: `SessionCompositeRepository`

#### 具体场景分析：

**🔸 会话创建 (create_session)**
```
调用: SessionCompositeRepository.create_session()
跨表: user_sessions_v2 + session_records_v2 + user_activity_stats_v2
```

**🔸 会话管理 (get_session/update_session)**
```
调用: SessionCompositeRepository.get_session_info() / update_session_activity()
跨表: user_sessions_v2 + session_records_v2 + user_activity_stats_v2
```

**🔸 会话结束**
```
调用: SessionCompositeRepository.end_session()
跨表: session_records_v2 + user_activity_stats_v2
```

---

### 5. ActionRecordService → 主要调用ActionCompositeRepository

#### 调用关系：
- **主要调用**: `ActionCompositeRepository`

#### 具体场景分析：

**🔸 行为记录 (record_action)**
```
调用: ActionCompositeRepository.create()
跨表: user_action_records_v2 + user_activity_stats_v2（选择性更新）
```

**🔸 行为统计 (get_action_statistics)**
```
调用: ActionCompositeRepository.get_statistics() 等方法
跨表: user_action_records_v2 + user_activity_stats_v2
```

**🔸 特定行为记录 (record_image_generation/record_payment_action)**
```
调用: ActionCompositeRepository.create() + 特定的统计更新
跨表: user_action_records_v2 + user_activity_stats_v2
```


---

## 📊 调用关系总结表

| Service | 主要调用的组合Repository | 次要调用的组合Repository | 跨表场景数量 |
|---------|------------------------|------------------------|------------|
| UserService | UserCompositeRepository | PointCompositeRepository | 3个高频场景 |
| PaymentService | PointCompositeRepository | - | 1个高频场景 |
| ImageService | PointCompositeRepository | - | 1个高频场景 |
| SessionService | SessionCompositeRepository | - | 2个中频场景 |
| ActionRecordService | ActionCompositeRepository | - | 1个低频场景 |
| SystemConfigService | 无（单表操作） | - | 0个 |

---

## 🔄 依赖注入建议

### Container配置示例：
```python
# 在依赖注入容器中的配置建议
class Container:
    def __init__(self):
        # 组合Repository实例
        self.user_composite_repo = UserCompositeRepository(supabase_manager)
        self.point_composite_repo = PointCompositeRepository(supabase_manager)
        self.session_composite_repo = SessionCompositeRepository(supabase_manager)
        self.action_composite_repo = ActionCompositeRepository(supabase_manager)
        
        # Service实例配置
        self.user_service = UserService(
            user_composite_repo=self.user_composite_repo,
            point_composite_repo=self.point_composite_repo
        )
        
        self.payment_service = PaymentService(
            point_composite_repo=self.point_composite_repo
        )
        
        self.image_service = ImageService(
            point_composite_repo=self.point_composite_repo
        )
        
        self.session_service = SessionService(
            session_composite_repo=self.session_composite_repo
        )
        
        self.action_record_service = ActionRecordService(
            action_composite_repo=self.action_composite_repo
        )
```

---

## ⚡ 重构优先级建议

### 高优先级（必须立即重构）
1. **UserService** - 4表联动场景最复杂，影响最广
2. **PaymentService** - 涉及资金相关，安全性要求高  
3. **ImageService** - 核心业务功能，使用频率高

### 中优先级  
4. **SessionService** - 会话管理，用户体验相关

### 低优先级
5. **ActionRecordService** - 统计分析功能，非核心业务流程

### 不需要重构
6. **SystemConfigService** - 单表操作，现有方式即可

---

## 🚨 重要注意事项

### 1. 接口兼容性
- 所有组合Repository都设计为与旧版Repository接口兼容
- Service层调用方式基本不需要改变
- 渐进式迁移，降低风险

### 2. 事务一致性
- 所有跨表操作都封装在组合Repository的事务中
- 失败时自动回滚，保证数据一致性
- 避免Service层直接处理事务逻辑

### 3. 性能考虑
- 组合Repository内部优化了跨表查询
- 减少了Service层的多次Repository调用
- 统一的数据格式转换，提升效率

### 4. 监控与调试
- 每个组合Repository都有详细的日志记录
- 标准化的错误响应格式
- 便于问题排查和性能监控 