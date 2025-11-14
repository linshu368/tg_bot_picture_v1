"""
依赖注入容器
管理所有组件的创建和依赖关系
"""

from typing import Dict, Any, Type, TypeVar, Optional
import logging

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
    
    # # 注册 Point 组合仓库（MVP：JSON 实现）
    # def point_composite_repository_factory(c):
    #     from src.infrastructure.repositories_v2.point_repository_json import JSONPointRepository
    #     # 可按需从 settings 中读取目录，默认 data/payments
    #     return JSONPointRepository(base_dir="data/payments")
    
    # container.register_factory("point_composite_repository", point_composite_repository_factory)
    
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
    
    # 注册 Service 层
    def session_service_factory(c):
        from src.domain.services.session_service_base import SessionService
        return SessionService()
    
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
        return MessageService(
            message_repository=c.get("message_repository"),
            session_service=c.get("session_service")
        )
    
    container.register_factory("message_service", message_service_factory)
    
    # 注册AI调用器（Grok 与 Novel）
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
            grok_caller=c.get("grok_caller"),
            novel_caller=c.get("novel_caller")
        )
    
    container.register_factory("ai_completion_port", ai_completion_port_factory)
    
    # def payment_api_factory(c):
    #     from src.infrastructure.external_apis.payment_api import PaymentAPI
    #     return PaymentAPI()
    
    # container.register_factory("payment_api", payment_api_factory)
    

    # def payment_service_factory(c):
    #     from src.domain.services.payment_service import PaymentService
    #     service = PaymentService(
    #         payment_config=c.get("settings").payment.__dict__ if hasattr(c.get("settings"), 'payment') else {},
    #         payment_api=c.get("payment_api"),
    #         point_composite_repo=c.get("point_composite_repository")
    #     )
    #     service.logger.info("🔧 PaymentService: 迁移完成 - 仅依赖PointCompositeRepository")
    #     return service
    
    # container.register_factory("payment_service", payment_service_factory)

    # # 注册支付回调处理器
    # def payment_webhook_handler_factory(c):
    #     from src.infrastructure.messaging.payment_webhook import PaymentWebhookHandler
    #     return PaymentWebhookHandler(
    #         c.get("payment_service"),
    #         c.get("user_service"),
    #         c.get("telegram_bot"),
    #         c.get("payment_api")
    #     )
    
    # container.register_factory("payment_webhook_handler", payment_webhook_handler_factory)
    
    # 返回配置好的容器
    return container