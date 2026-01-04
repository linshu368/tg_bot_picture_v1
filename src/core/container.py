"""
依赖注入容器
管理所有组件的创建和依赖关系
"""

from typing import Dict, Any, Type, TypeVar, Optional
import logging
import os

T = TypeVar('T')


class Container:
    """简单的依赖注入容器"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, callable] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_singleton(self, name: str, instance: Any):
        """注册单例服务"""
        self._singletons[name] = instance
        self.logger.debug(f"注册单例服务: {name}")
    
    def register_factory(self, name: str, factory: callable):
        """注册工厂方法"""
        self._factories[name] = factory
        self.logger.debug(f"注册工厂服务: {name}")
    
    def get(self, name: str) -> Any:
        """获取服务实例"""
        # 先检查单例
        if name in self._singletons:
            return self._singletons[name]
        
        # 检查工厂
        if name in self._factories:
            instance = self._factories[name](self)
            # 如果是单例，缓存起来
            self._singletons[name] = instance
            return instance
        
        raise ValueError(f"服务未注册: {name}")
    
    def has(self, name: str) -> bool:
        """检查服务是否已注册"""
        return name in self._singletons or name in self._factories


def initialize_global_services(container: Container):
    """
    初始化全局服务实例
    将容器创建的实例注入到全局变量中，确保向后兼容
    
    Args:
        container: 已配置好的容器实例
    """
    # 导入模块并替换全局实例
    # 注意：必须直接导入模块文件，不能从 __init__.py 导入
    import sys
    import importlib
    
    # 确保直接从模块文件导入
    session_service_module = importlib.import_module("src.domain.services.session_service_base")
    role_service_module = importlib.import_module("src.domain.services.role_service")
    snapshot_service_module = importlib.import_module("src.domain.services.snapshot_service")
    stream_message_service_module = importlib.import_module("src.core.services.stream_message_service")
    message_service_module = importlib.import_module("src.domain.services.message_service")
    ai_completion_port_module = importlib.import_module("src.domain.services.ai_completion_port")
    user_processing_state_module = importlib.import_module("src.core.services.user_processing_state")
    
    # 替换全局实例
    session_service_module.session_service = container.get("session_service")
    role_service_module.role_service = container.get("role_service")
    snapshot_service_module.snapshot_service = container.get("snapshot_service")
    stream_message_service_module.stream_message_service = container.get("stream_message_service")
    message_service_module.message_service = container.get("message_service")
    ai_completion_port_module.ai_completion_port = container.get("ai_completion_port")
    user_processing_state_module.user_processing_state = container.get("user_processing_state")
    
    logging.getLogger(__name__).info("✅ 全局服务实例已初始化（包含message_service、ai_completion_port和user_processing_state）")


def setup_container(settings) -> Container:
    """设置依赖注入容器"""
    container = Container()
    
    # 注册配置
    container.register_singleton("settings", settings)
    
    # 注册数据库相关 - 支持Supabase (注册为单例确保实例唯一性)
    def supabase_manager_factory(c):
        from src.infrastructure.repositories_v2.supabase_manager import SupabaseManager
        return SupabaseManager(c.get("settings").database)
    
    container.register_factory("supabase_manager", supabase_manager_factory)
    
    # 注册 Repository 层
    def role_repository_factory(c):
        from src.infrastructure.repositories_v2.supabase_role_repository import SupabaseRoleRepository
        return SupabaseRoleRepository(c.get("supabase_manager"))
    
    container.register_factory("role_repository", role_repository_factory)
    
    def snapshot_repository_factory(c):
        from src.infrastructure.repositories_v2.supabase_snapshot_repository import SupabaseSnapshotRepository
        return SupabaseSnapshotRepository(c.get("supabase_manager"))
    
    container.register_factory("snapshot_repository", snapshot_repository_factory)
    
    def message_repository_factory(c):
        from src.infrastructure.repositories_v2.supabase_message_repository import SupabaseMessageRepository
        return SupabaseMessageRepository(c.get("supabase_manager"))
    
    container.register_factory("message_repository", message_repository_factory)
    
    # 共享 Redis 存储（Upstash REST）单例 - 提前注册，供下游服务获取
    def redis_store_factory(c):
        try:
            import os
            from src.infrastructure.redis.upstash_session_store import UpstashSessionStore
            upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
            upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
            if upstash_url and upstash_token:
                return UpstashSessionStore(rest_url=upstash_url, token=upstash_token)
        except Exception:
            pass
        return None
    container.register_factory("redis_store", redis_store_factory)
    
    # 注册 Service 层
    def session_service_factory(c):
        from src.domain.services.session_service_base import SessionService
        # 共享 Redis 存储（如可用）
        redis_store = None
        try:
            redis_store = c.get("redis_store")
        except Exception:
            redis_store = None
        return SessionService(redis_store=redis_store)
    
    container.register_factory("session_service", session_service_factory)
    
    def role_service_factory(c):
        from src.domain.services.role_service import RoleService
        return RoleService(c.get("role_repository"))
    
    container.register_factory("role_service", role_service_factory)
    
    def snapshot_service_factory(c):
        from src.domain.services.snapshot_service import SnapshotService
        return SnapshotService(
            snapshot_repository=c.get("snapshot_repository"),
            message_service=c.get("message_service"),
            session_service=c.get("session_service"),
            role_service=c.get("role_service")
        )
    
    container.register_factory("snapshot_service", snapshot_service_factory)
    
    # 注册应用核心服务
    def stream_message_service_factory(c):
        from src.core.services.stream_message_service import StreamMessageService
        return StreamMessageService(role_service=c.get("role_service"))
    
    container.register_factory("stream_message_service", stream_message_service_factory)
    
    # 🆕 注册用户处理状态管理器
    def user_processing_state_factory(c):
        from src.core.services.user_processing_state import user_processing_state
        return user_processing_state
    
    container.register_factory("user_processing_state", user_processing_state_factory)
    
    # 注册消息服务
    def message_service_factory(c):
        from src.domain.services.message_service import MessageService
        # 优先从环境变量创建 Upstash REST 适配器（不强依赖）
        try:
            redis_store = c.get("redis_store")
        except Exception:
            redis_store = None
        return MessageService(
            message_repository=c.get("message_repository"),
            session_service=c.get("session_service"),
            redis_store=redis_store
        )
    
    
    container.register_factory("message_service", message_service_factory)
    
    # 注册AI调用器（Gemini、Grok 与 Novel）
    def gemini_caller_factory(c):
        from demo.gemini_async import AsyncGeminiCaller
        return AsyncGeminiCaller()
    container.register_factory("gemini_caller", gemini_caller_factory)

    # --- DeepSeek V1/V2 Instance (Official/Default) ---
    def deepseek_caller_1_factory(c):
        from demo.deepseek_async import AsyncDeepseekCaller
        # 优先读取 _1 变量，回退读取不带后缀的旧变量
        api_key = os.getenv("DEEPSEEK_API_KEY_1") or os.getenv("DEEPSEEK_API_KEY")
        api_url = os.getenv("DEEPSEEK_API_URL_1") or os.getenv("DEEPSEEK_API_URL")
        return AsyncDeepseekCaller(api_key=api_key, api_url=api_url)
    container.register_factory("deepseek_caller_1", deepseek_caller_1_factory)

    # --- DeepSeek V3 Instance (SiliconFlow) ---
    def deepseek_caller_3_factory(c):
        from demo.deepseek_async import AsyncDeepseekCaller
        # 优先读取 _3 变量，否则使用硬编码的 SiliconFlow 默认值
        api_key = os.getenv("DEEPSEEK_API_KEY_3") or "sk-mztgmqtkmhfgbdgkgbejivwswyspwzjzuadgaracjwmzkegr"
        api_url = os.getenv("DEEPSEEK_API_URL_3") or "https://api.siliconflow.cn/v1/chat/completions"
        return AsyncDeepseekCaller(api_key=api_key, api_url=api_url)
    container.register_factory("deepseek_caller_3", deepseek_caller_3_factory)

    def grok_caller_factory(c):
        from demo.grok_async import AsyncGrokCaller
        return AsyncGrokCaller()
    container.register_factory("grok_caller", grok_caller_factory)

    def novel_caller_factory(c):
        from demo.novel_async import AsyncNovelCaller
        return AsyncNovelCaller()
    container.register_factory("novel_caller", novel_caller_factory)
    
    # 注册AI完成端口服务
    def ai_completion_port_factory(c):
        from src.domain.services.ai_completion_port import AICompletionPort
        return AICompletionPort(
            gemini_caller=c.get("gemini_caller"),
            grok_caller=c.get("grok_caller"),
            novel_caller=c.get("novel_caller"),
            deepseek_caller_1=c.get("deepseek_caller_1"),
            deepseek_caller_3=c.get("deepseek_caller_3")
        )
    
    container.register_factory("ai_completion_port", ai_completion_port_factory)
    
    # 返回配置好的容器
    return container
