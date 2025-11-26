import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 尝试导入 prometheus_client，如果不存在则使用桩代码，防止阻塞主流程
try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("⚠️ prometheus_client module not found. Metrics will not be recorded.")
    
    # 桩类定义，用于在未安装库时静默失败，保证业务不中断
    class DummyMetric:
        def inc(self, amount=1): pass
        def observe(self, amount): pass
        def labels(self, **kwargs): return self
    
    class Counter:
        def __init__(self, name, documentation, labelnames=()): pass
        def inc(self, amount=1): pass
        def labels(self, **kwargs): return DummyMetric()
        
    class Histogram:
        def __init__(self, name, documentation, labelnames=(), buckets=()): pass
        def observe(self, amount): pass
        def labels(self, **kwargs): return DummyMetric()

# ==============================================================================
# T0：响应成功率指标（系统级，不引入业务角色维度）
# ==============================================================================

# 1. bot_response_success_total
# 记录 Bot 完整回复用户的成功次数（不携带业务角色）
BOT_RESPONSE_SUCCESS_TOTAL = Counter(
    'bot_response_success_total',
    'Total number of successful bot responses (full reply rendered)'
)

# 2. bot_response_failure_total
# 记录 Bot 回复失败的次数
BOT_RESPONSE_FAILURE_TOTAL = Counter(
    'bot_response_failure_total',
    'Total number of failed bot responses',
    labelnames=['error_type']  # 错误类型：建议做枚举规范化
)

# 3. ai_provider_calls_total
# 记录 AI provider 的 API 调用次数
AI_PROVIDER_CALLS_TOTAL = Counter(
    'ai_provider_calls_total',
    'Total number of AI provider API calls',
    labelnames=['provider', 'model']
)

# 4. ai_provider_calls_failed_total
# 记录 AI provider 的调用失败次数
AI_PROVIDER_CALLS_FAILED_TOTAL = Counter(
    'ai_provider_calls_failed_total',
    'Total number of failed AI provider API calls',
    labelnames=['provider', 'error_type']
)

# ==============================================================================
# T1：响应速度指标（用户体验）
# ==============================================================================

# 5. bot_first_response_latency_seconds
# 用户发送消息 -> 第一个 AI 流式 chunk 到达 的耗时
BOT_FIRST_RESPONSE_LATENCY = Histogram(
    'bot_first_response_latency_seconds',
    'Latency from user message to first stream chunk (seconds)',
    buckets=(0.1, 0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 5.0, float('inf'))
)

# 6. bot_full_response_latency_seconds
# 用户发送消息 -> AI 回复全部内容渲染完成 的时间
BOT_FULL_RESPONSE_LATENCY = Histogram(
    'bot_full_response_latency_seconds',
    'Latency from user message to full response rendered (seconds)',
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 20.0, float('inf'))
)

# 7. ai_first_token_latency_seconds
# AI Completion API 请求发起 -> 第一个 chunk 到达 的耗时
AI_FIRST_TOKEN_LATENCY = Histogram(
    'ai_first_token_latency_seconds',
    'Latency from AI request to first token received (seconds)',
    labelnames=['provider', 'model'],
    buckets=(0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, float('inf'))
)
