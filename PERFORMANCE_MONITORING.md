# Bot性能监控系统

## 概述

为了诊断bot响应慢的问题，我们实现了一个详细的性能监控系统，可以在bot的整个响应链路中添加性能打点，帮助识别性能瓶颈。

## 功能特性

### 1. 性能监控器 (PerformanceMonitor)

- **自动计时**: 记录操作的开始和结束时间
- **检查点**: 在操作过程中记录关键步骤的耗时
- **操作总结**: 提供完整的操作耗时统计
- **异常处理**: 即使出现异常也能正确记录耗时

### 2. 监控的流程节点

#### 按钮点击流程
- 用户状态检查
- 函数分发
- 具体功能处理

#### 图片处理流程
- 后台任务调度
- 用户信息获取
- 图片信息获取
- 状态检查
- 功能选择

#### 图像生成确认流程
- 用户信息获取
- 积分检查
- 图片文件ID获取
- 积分扣除
- 图片下载
- API调用
- 数据库操作
- 状态清理

#### API调用流程
- 请求构建
- HTTP请求发送
- 响应接收
- 响应解析

#### Webhook回调流程
- 请求解析
- 数据验证
- 异步处理

## 日志格式

性能监控日志使用统一的格式：

```
⏱️  [PERF] 开始: operation_id - 操作描述
⏱️  [PERF] 检查点: operation_id.checkpoint_name - 检查点描述 | 已耗时: X.XXXs
⏱️  [PERF] 完成: operation_id - 操作完成描述 | 耗时: X.XXXs
```

## 使用方法

### 1. 基本使用

```python
from src.utils.performance_monitor import get_performance_monitor

monitor = get_performance_monitor()

# 开始计时
operation_id = f"my_operation_{user_id}_{int(time.time())}"
monitor.start_timer(operation_id, "我的操作")

# 添加检查点
monitor.checkpoint(operation_id, "step1", "完成步骤1")

# 结束计时
monitor.end_timer(operation_id, "操作完成")
```

### 2. 异步上下文管理器

```python
async with monitor.async_timer("operation_id", "操作描述") as m:
    await some_async_operation()
    m.checkpoint("step1", "完成步骤1")
    await another_async_operation()
```

### 3. 获取操作总结

```python
summary = monitor.get_operation_summary(operation_id)
if summary:
    print(f"总耗时: {summary['duration']:.3f}s")
```

## 已添加监控的关键节点

### 1. 消息处理器 (message_handlers.py)
- `_handle_button_dispatch`: 按钮分发处理
- `_handle_quick_undress_button`: 快速去衣按钮处理
- `handle_photo_message`: 图片消息处理

### 2. 图像处理 (image_processing.py)
- `process_quick_undress_confirmation`: 快速去衣确认处理

### 3. API调用 (clothoff_api.py)
- `generate_image`: ClothOff API调用

### 4. Webhook处理 (image_webhook.py)
- `handle_image_process_callback`: 图片处理回调

## 性能分析

通过查看日志，你可以：

1. **识别慢操作**: 查看哪些操作耗时最长
2. **定位瓶颈**: 通过检查点找出具体哪个步骤最慢
3. **优化重点**: 优先优化耗时最长的操作
4. **监控趋势**: 观察性能是否随时间变化

## 示例日志输出

```
2025-09-09 20:41:06,864 - performance_monitor - INFO - ⏱️  [PERF] 开始: button_click_12345_1757421666 - 用户 12345 点击快速去衣按钮
2025-09-09 20:41:06,915 - performance_monitor - INFO - ⏱️  [PERF] 检查点: button_click_12345_1757421666.get_user - 获取用户信息 | 已耗时: 0.051s
2025-09-09 20:41:06,946 - performance_monitor - INFO - ⏱️  [PERF] 检查点: button_click_12345_1757421666.check_points - 检查积分 | 已耗时: 0.082s
2025-09-09 20:41:06,967 - performance_monitor - INFO - ⏱️  [PERF] 检查点: button_click_12345_1757421666.set_state - 设置用户状态 | 已耗时: 0.104s
2025-09-09 20:41:06,978 - performance_monitor - INFO - ⏱️  [PERF] 检查点: button_click_12345_1757421666.send_reply - 发送回复消息 | 已耗时: 0.115s
2025-09-09 20:41:06,978 - performance_monitor - INFO - ⏱️  [PERF] 完成: button_click_12345_1757421666 - 快速去衣按钮处理完成 | 耗时: 0.115s
```

## 测试

运行测试脚本验证性能监控功能：

```bash
python3 test_performance_monitor.py
```

## 注意事项

1. 性能监控会产生额外的日志，在生产环境中可能需要调整日志级别
2. 操作ID使用时间戳确保唯一性，避免冲突
3. 监控器是单例模式，全局共享状态
4. 异常情况下也会正确记录耗时信息

## 下一步优化建议

基于性能监控结果，可能的优化方向：

1. **数据库查询优化**: 如果用户信息获取慢，考虑添加缓存
2. **API调用优化**: 如果外部API慢，考虑异步处理或重试机制
3. **图片处理优化**: 如果图片下载慢，考虑压缩或预处理
4. **状态管理优化**: 如果状态检查慢，考虑内存缓存
