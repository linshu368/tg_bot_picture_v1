# ActionRecordService迁移切换机制详解

本文档详细介绍ActionRecordService从旧Repository到新组合Repository的渐进式迁移切换机制。

---

## 📋 概述

ActionRecordService采用了一套完整的渐进式迁移机制，支持三种运行模式的无缝切换：
- **stable**: 稳定模式，完全使用旧Repository
- **parallel_test**: 并行测试模式，主用旧Repository，同时验证新Repository
- **migrated**: 迁移完成模式，完全使用新Repository

这套机制的核心特点是**最小改动原则**和**透明切换**，确保在迁移过程中业务逻辑不受影响。

---

## 🏗️ 架构设计

### 核心组件关系

```
Environment Variables → Settings → Container → ActionRecordService
                                      ↓
                            ActionCompositeRepository (新)
                                      ↓
                            UserActionRecordRepository (旧)
```

### 三种运行模式

| 模式 | 主Repository | 验证Repository | 并行测试 | 用途 |
|------|-------------|---------------|----------|------|
| stable | 旧Repository | 无 | 否 | 生产环境稳定运行 |
| parallel_test | 旧Repository | 新Repository | 是 | 数据一致性验证 |
| migrated | 新Repository | 无 | 否 | 迁移完成后运行 |

---

## ⚙️ 配置机制

### 1. 环境变量配置

```bash
# 设置迁移模式
export ACTION_RECORD_MIGRATION_MODE="parallel_test"

# 可选值：
# - stable: 稳定模式（默认）
# - parallel_test: 并行测试模式  
# - migrated: 迁移完成模式
```

### 2. Settings配置类

```python
class ServicesSettings:
    """服务配置"""
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        config_dict = config_dict or {}
        
        # ActionRecordService迁移模式配置
        self.action_record_migration_mode = config_dict.get(
            'action_record_migration_mode', 'stable'
        )
```

### 3. Container工厂配置

```python
def action_record_service_factory(c):
    """创建ActionRecordService实例，支持配置驱动的Repository切换"""
    
    settings = c.get("settings")
    migration_mode = getattr(settings.services, 'action_record_migration_mode', 'stable')
    
    # 根据模式选择主Repository
    if migration_mode == 'migrated':
        main_repo = c.get("action_composite_repository")  # 新Repository
        enable_test = False
    else:
        main_repo = c.get("user_action_record_repository")  # 旧Repository
        enable_test = (migration_mode == 'parallel_test')
    
    # 创建服务实例
    service = ActionRecordService(
        action_record_repo=main_repo,
        enable_parallel_test=enable_test
    )
    
    # 仅在parallel_test模式下注入验证repo
    if enable_test:
        verification_repo = c.get("action_composite_repository")
        service.set_verification_repo(verification_repo)
    
    return service
```

---

## 🔄 Service实现机制

### 1. 初始化逻辑

```python
class ActionRecordService:
    def __init__(self, action_record_repo=None, enable_parallel_test=False, db_manager=None):
        # 主要使用的Repository
        self.action_record_repo = action_record_repo
        
        # 并行测试配置
        self.enable_parallel_test = enable_parallel_test
        self.verification_repo = None
        
        # 监控指标（仅在测试模式下）
        if enable_parallel_test:
            self.test_stats = {
                'total': 0,
                'success': 0, 
                'failed': 0,
                'last_check_time': datetime.utcnow()
            }
```

### 2. 核心业务方法

```python
async def record_action(self, user_id: int, session_id: str, action_type: str, 
                       parameters: Dict[str, Any] = None, message_context: str = None,
                       points_cost: int = 0) -> Optional[Dict[str, Any]]:
    """记录用户成功行为"""
    try:
        # 1. 主要操作（使用主Repository）
        record = await self.action_record_repo.record_action(
            user_id, session_id, action_type, parameters, message_context, points_cost
        )
        
        # 2. 并行验证（仅在测试模式下）
        if self.enable_parallel_test and self.verification_repo:
            asyncio.create_task(self._verify_in_background({
                'user_id': user_id,
                'session_id': session_id,
                'action_type': action_type,
                'parameters': parameters or {},
                'message_context': message_context,
                'points_cost': points_cost,
                'status': 'success'
            }, record))
        
        return record
        
    except Exception as e:
        self.logger.error(f"记录用户行为失败: {e}")
        return None
```

### 3. 后台验证机制

```python
async def _verify_in_background(self, action_data: Dict[str, Any], main_result: Dict[str, Any]):
    """后台验证逻辑"""
    try:
        self.test_stats['total'] += 1
        
        # 使用验证Repository执行相同操作
        verification_result = await self.verification_repo.create(action_data)
        
        # 一致性检查
        key_fields = ['user_id', 'session_id', 'action_type', 'status']
        is_consistent = all(
            main_result.get(field) == verification_result.get(field) 
            for field in key_fields
        )
        
        if is_consistent:
            self.test_stats['success'] += 1
        else:
            self.test_stats['failed'] += 1
            self.logger.warning(f"数据不一致: {action_data['action_type']}")
        
        # 定期输出统计
        if self.test_stats['total'] % 100 == 0:
            success_rate = self.test_stats['success'] / self.test_stats['total'] * 100
            self.logger.info(f"验证统计: {self.test_stats['total']}次, 一致性={success_rate:.1f}%")
            
    except Exception as e:
        self.test_stats['failed'] += 1
        self.logger.error(f"验证异常: {e}")
```

---

## 🧪 测试验证体系

### 1. 单元测试 (test_action_record_service_migration.py)

#### 测试覆盖范围：
- ✅ **稳定模式测试**: 验证只使用旧Repository
- ✅ **并行测试模式**: 验证主用旧Repository，验证新Repository  
- ✅ **迁移完成模式**: 验证只使用新Repository
- ✅ **数据一致性验证**: 验证新旧Repository数据一致性
- ✅ **异常处理**: 验证验证过程异常不影响主流程

#### 关键测试用例：

```python
@pytest.mark.asyncio
async def test_parallel_test_mode(self, mock_old_repo, mock_new_repo):
    """测试并行测试模式：主用旧Repository，验证新Repository"""
    service = ActionRecordService(
        action_record_repo=mock_old_repo,
        enable_parallel_test=True
    )
    service.set_verification_repo(mock_new_repo)
    
    # 测试记录行为
    result = await service.record_action(
        user_id=123,
        session_id='sess_test',
        action_type='test_action',
        parameters={'test': 'data'}
    )
    
    # 验证主要结果来自旧repo
    assert result is not None
    mock_old_repo.record_action.assert_called_once()
    
    # 等待异步验证任务完成
    await asyncio.sleep(0.1)
    
    # 验证新repo也被调用用于验证
    mock_new_repo.create.assert_called_once()
```

### 2. 并行写入一致性测试 (test_parallel_write_consistency.py)

#### 测试特点：
- 🎯 **真实数据库操作**: 非Mock，直接操作Supabase
- 📊 **详细数据对比**: 逐字段对比新旧Repository写入结果
- ⚡ **可配置测试规模**: 支持quick和comprehensive模式
- 📈 **实时监控统计**: 提供一致性率和详细差异报告

#### 测试流程：

```python
async def run_test(self, test_actions: List[TestAction]) -> ConsistencyTestResult:
    """运行完整的一致性测试"""
    # 1. 执行测试操作（同时写入新旧Repository）
    execution_results = await self.execute_test_actions(test_actions)
    
    # 2. 从数据库查询实际数据
    old_data, new_data = await self.query_data_from_repos(session_ids)
    
    # 3. 对比一致性
    result = self.compare_records(old_data, new_data)
    
    return result
```

#### 一致性检查逻辑：

```python
def compare_records(self, old_records: List[Dict], new_records: List[Dict]) -> ConsistencyTestResult:
    """对比新旧数据的一致性"""
    # 核心字段匹配
    match_fields = ['user_id', 'session_id', 'action_type']
    # 对比字段
    compare_fields = ['user_id', 'session_id', 'action_type', 'status', 'points_cost', 'message_context']
    
    # 逐条对比，识别：
    # - 字段值不一致
    # - 新Repository缺失记录
    # - 旧Repository缺失记录
```

---

## 📊 监控与统计

### 1. Service内部统计

```python
# 实时统计指标
self.test_stats = {
    'total': 0,        # 总验证次数
    'success': 0,      # 验证成功次数  
    'failed': 0,       # 验证失败次数
    'last_check_time': datetime.utcnow()
}

# 获取统计数据
def get_test_stats(self) -> Dict[str, Any]:
    """获取测试统计（仅用于监控）"""
    if not self.enable_parallel_test:
        return {}
    return self.test_stats.copy()
```

### 2. 定期日志输出

```python
# 每100次验证输出一次统计
if self.test_stats['total'] % 100 == 0:
    success_rate = self.test_stats['success'] / self.test_stats['total'] * 100
    self.logger.info(f"🔧 验证统计: {self.test_stats['total']}次, 一致性={success_rate:.1f}%")
```

---

## 🚀 实际使用指南

### 1. 启动稳定模式（生产环境）

```bash
# 不设置环境变量或显式设置
export ACTION_RECORD_MIGRATION_MODE="stable"
python main.py
```

**日志输出**：
```
ActionRecordService: 稳定 - 使用旧Repository
```

### 2. 启动并行测试模式（验证阶段）

```bash
# 设置并行测试模式
export ACTION_RECORD_MIGRATION_MODE="parallel_test"
python main.py
```

**日志输出**：
```
🔧 启用并行测试模式
🔧 已设置验证Repository
🔧 ActionRecordService: 并行测试 - 使用旧Repository，已启用验证
🔧 验证统计: 100次, 一致性=98.5%
```

### 3. 启动迁移完成模式（新Repository）

```bash
# 设置迁移完成模式
export ACTION_RECORD_MIGRATION_MODE="migrated"
python main.py
```

**日志输出**：
```
🔧 ActionRecordService: 迁移完成 - 使用新Repository
```

### 4. 运行一致性测试

```bash
# 快速测试（20条记录）
python tests/test_parallel_write_consistency.py --mode=quick

# 全面测试（100条记录）
python tests/test_parallel_write_consistency.py --mode=comprehensive --records=100

# 保存报告
python tests/test_parallel_write_consistency.py --mode=quick --output=consistency_report.txt
```

---

## 🎯 迁移实施策略

### 阶段1: 准备阶段
1. ✅ 实现ActionCompositeRepository
2. ✅ 配置Container工厂方法
3. ✅ 编写单元测试
4. ✅ 设置环境变量配置

### 阶段2: 验证阶段  
1. 🔄 **当前阶段**: 启用parallel_test模式
2. 🔄 运行并行写入一致性测试
3. 🔄 监控一致性率，目标>95%
4. 🔄 修复发现的数据不一致问题

### 阶段3: 迁移阶段
1. ⏳ 生产环境切换到parallel_test模式
2. ⏳ 观察运行一段时间（如1周）
3. ⏳ 确认一致性稳定后切换到migrated模式
4. ⏳ 清理旧Repository相关代码

### 阶段4: 完成阶段
1. ⏳ 移除parallel_test相关代码
2. ⏳ 更新文档和测试
3. ⏳ 为其他Service复制此模式

---

## 🚨 注意事项

### 1. 性能影响
- **stable模式**: 无额外性能开销
- **parallel_test模式**: 有额外的写入和验证开销，建议仅在测试环境长期使用
- **migrated模式**: 性能优于旧Repository（跨表事务优化）

### 2. 数据一致性
- 并行验证采用异步方式，不影响主流程性能
- 验证失败不会影响业务操作的正常执行
- 定期检查一致性统计，及时发现问题

### 3. 错误处理
- 验证Repository异常不影响主Repository操作
- 所有异常都有详细日志记录
- 支持降级到稳定模式

### 4. 监控建议
- 生产环境启用parallel_test前，先在测试环境充分验证
- 监控一致性率，低于95%需要排查问题
- 定期检查日志中的不一致警告

---

## 📈 成功指标

### 测试阶段成功标准：
- ✅ 单元测试通过率: 100%
- 🔄 并行写入一致性率: >95%
- 🔄 性能回归测试: 延迟增加<10%
- 🔄 错误处理测试: 异常不影响主流程

### 生产阶段成功标准：
- ⏳ 生产环境parallel_test模式稳定运行1周
- ⏳ 一致性率持续>98%
- ⏳ 无业务功能异常
- ⏳ 用户无感知切换

---

## 🔗 相关文档

- [跨表场景梳理报告](./跨表场景梳理报告.md)
- [Service与组合Repository调用关系分析报告](./Service与组合Repository调用关系分析报告.md)
- [ActionCompositeRepository设计文档](../src/infrastructure/database/repositories_v2/composite/README.md)

---

这套迁移切换机制为其他Service的迁移提供了完整的参考模板，确保了渐进式、安全的Repository升级路径。 