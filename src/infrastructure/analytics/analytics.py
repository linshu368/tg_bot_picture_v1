import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 尝试加载 .env（若存在）
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv(usecwd=True), override=False)
except Exception:
    # 无 dotenv 或加载失败时忽略，后续从进程环境读取
    pass

_posthog = None
_enabled = False
_executor: Optional[ThreadPoolExecutor] = None

try:
    from posthog import Posthog  # type: ignore
except Exception:
    Posthog = None  # type: ignore


def _init_client() -> None:
    global _posthog, _enabled
    api_key = os.getenv("POSTHOG_API_KEY", "").strip()
    host = os.getenv("POSTHOG_HOST", "").strip() or "https://app.posthog.com"
    if not api_key or Posthog is None:
        _enabled = False
        if not api_key:
            logger.info("PostHog disabled: missing POSTHOG_API_KEY")
        else:
            logger.info("PostHog disabled: posthog package not installed")
        return
    try:
        _posthog = Posthog(project_api_key=api_key, host=host)
        _enabled = True
        # 轻量线程池，保证不阻塞主线程也避免线程暴涨
        _init_executor()
        logger.info("✅ PostHog client initialized")
    except Exception as e:
        _posthog = None
        _enabled = False
        logger.error(f"Failed to initialize PostHog: {e}")

def _init_executor() -> None:
    global _executor
    if _executor is None:
        try:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="posthog-bg")
        except Exception as e:
            logger.debug(f"create executor failed: {e}")
            # 保持 None，后续调用将直接跳过


def is_enabled() -> bool:
    if not _posthog and not _enabled:
        _init_client()
    return _enabled and _posthog is not None


def _now_iso() -> str:
    # 东八区时区 (UTC+8)
    china_tz = timezone(timedelta(hours=8))
    return datetime.now(china_tz).isoformat()


def track_event(distinct_id: str, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
    """
    发送 PostHog 事件（无配置时自动降级为 no-op）
    """
    if not is_enabled():
        logger.debug(f"PostHog disabled, skipping event: {event} for user {distinct_id}")
        return
    try:
        props = dict(properties or {})
        # 确保存在 timestamp（东八区 ISO8601）
        if "timestamp" not in props:
            props["timestamp"] = _now_iso()
        _posthog.capture(distinct_id=distinct_id, event=event, properties=props)
        logger.info(f"✅ PostHog event sent: {event} for user {distinct_id}")
    except Exception as e:
        logger.error(f"❌ PostHog track failed: {event} for user {distinct_id}, error: {e}")

def track_event_background(distinct_id: str, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
    """
    后台线程提交 PostHog 事件（即发即忘）
    - 提交立刻返回，不阻塞主路径
    - 任务中自行吞掉异常，绝不影响调用方
    """
    if not is_enabled():
        logger.debug(f"PostHog disabled, skipping background event: {event} for user {distinct_id}")
        return
    if _executor is None:
        _init_executor()
    if _executor is None:
        # 无法创建线程池则降级为同步但仍吞异常
        logger.warning(f"Thread pool unavailable, falling back to sync for event: {event}")
        try:
            track_event(distinct_id, event, properties)
        except Exception as e:
            logger.error(f"❌ PostHog sync fallback failed: {event} for user {distinct_id}, error: {e}")
        return

    props = dict(properties or {})
    if "timestamp" not in props:
        props["timestamp"] = _now_iso()

    try:
        _executor.submit(_safe_capture, distinct_id, event, props)
        logger.info(f"🔄 PostHog background event queued: {event} for user {distinct_id}")
    except Exception as e:
        # 提交失败也不抛给上层
        logger.error(f"❌ PostHog background event queue failed: {event} for user {distinct_id}, error: {e}")

def _safe_capture(distinct_id: str, event: str, properties: Dict[str, Any]) -> None:
    try:
        if not is_enabled():
            logger.debug(f"PostHog disabled in background task, skipping: {event} for user {distinct_id}")
            return
        _posthog.capture(distinct_id=distinct_id, event=event, properties=properties)  # type: ignore
        logger.info(f"✅ PostHog background event sent: {event} for user {distinct_id}")
    except Exception as e:
        # 后台任务中吞掉异常，但使用INFO级别确保能看到错误
        logger.info(f"❌ PostHog background capture failed: {event} for user {distinct_id}, error: {e}")


