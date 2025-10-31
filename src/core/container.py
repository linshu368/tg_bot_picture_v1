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


def setup_container(settings) -> Container:
    """设置依赖注入容器"""
    container = Container()
    
    # 注册配置
    container.register_singleton("settings", settings)
    
    # 注册数据库相关 - 支持Supabase (注册为单例确保实例唯一性)
    def supabase_manager_factory(c):
        from src.infrastructure.database.supabase_manager import SupabaseManager
        return SupabaseManager(c.get("settings").database)
    
    container.register_factory("supabase_manager", supabase_manager_factory)
    

    
    def payment_api_factory(c):
        from src.infrastructure.external_apis.payment_api import PaymentAPI
        return PaymentAPI()
    
    container.register_factory("payment_api", payment_api_factory)
    

    def payment_service_factory(c):
        from src.domain.services.payment_service import PaymentService
        service = PaymentService(
            payment_config=c.get("settings").payment.__dict__ if hasattr(c.get("settings"), 'payment') else {},
            payment_api=c.get("payment_api"),
            point_composite_repo=c.get("point_composite_repository")
        )
        service.logger.info("🔧 PaymentService: 迁移完成 - 仅依赖PointCompositeRepository")
        return service
    
    container.register_factory("payment_service", payment_service_factory)

    # 注册支付回调处理器
    def payment_webhook_handler_factory(c):
        from src.infrastructure.messaging.payment_webhook import PaymentWebhookHandler
        return PaymentWebhookHandler(
            c.get("payment_service"),
            c.get("user_service"),
            c.get("telegram_bot"),
            c.get("payment_api")
        )
    
    container.register_factory("payment_webhook_handler", payment_webhook_handler_factory)
   