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
    
    #待删 兼容旧的database_manager名称
    #container.register_factory("database_manager", supabase_manager_factory)
    
    # 注册所有Supabase Repository（旧版）
    # def user_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_user_repository import SupabaseUserRepository
    #     return SupabaseUserRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("user_repository", user_repository_factory)
    # 
    # def point_record_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_point_record_repository import SupabasePointRecordRepository
    #     return SupabasePointRecordRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("point_record_repository", point_record_repository_factory)
    #
    # def daily_checkin_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_daily_checkin_repository import SupabaseDailyCheckinRepository
    #     return SupabaseDailyCheckinRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("daily_checkin_repository", daily_checkin_repository_factory)
    # 
    # # 🔧 修复：修正PaymentRepository的路径
    # def payment_order_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_payment_repository import SupabasePaymentOrderRepository
    #     return SupabasePaymentOrderRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("payment_order_repository", payment_order_repository_factory)
    # 
    # def image_task_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_image_task_repository import SupabaseImageTaskRepository
    #     return SupabaseImageTaskRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("image_task_repository", image_task_repository_factory)
    # 
    # # 🔧 新增：注册新的Repository（旧版会话相关）
    # def user_session_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_user_session_repository import SupabaseUserSessionRepository
    #     return SupabaseUserSessionRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("user_session_repository", user_session_repository_factory)
    # 
    # def session_record_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_session_record_repository import SupabaseSessionRecordRepository
    #     return SupabaseSessionRecordRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("session_record_repository", session_record_repository_factory)
    # 
    # def user_action_record_repository_factory(c):
    #     from src.infrastructure.database.repositories.supabase_user_action_record_repository import SupabaseUserActionRecordRepository
    #     return SupabaseUserActionRecordRepository(c.get("supabase_manager"))
    # 
    # container.register_factory("user_action_record_repository", user_action_record_repository_factory)
    
    def system_config_repository_factory(c):
        from src.infrastructure.database.repositories.supabase_system_config_repository import SupabaseSystemConfigRepository
        return SupabaseSystemConfigRepository(c.get("supabase_manager"))
    
    container.register_factory("system_config_repository", system_config_repository_factory)
    
    # 🔧 V2迁移：新增ActionCompositeRepository工厂
    def action_composite_repository_factory(c):
        """创建ActionCompositeRepository实例
        
        🔧 V2迁移：用于支持跨表操作的组合Repository
        - 封装了actions + stats的跨表事务操作
        - 提供与旧版Repository兼容的接口
        """
        from src.infrastructure.database.repositories_v2.composite.action_composite_repository import ActionCompositeRepository
        return ActionCompositeRepository(c.get("supabase_manager"))
    
    container.register_factory("action_composite_repository", action_composite_repository_factory)
    
    # 🔧 V2迁移：新增PointCompositeRepository工厂
    def point_composite_repository_factory(c):
        """创建PointCompositeRepository实例
        
        🔧 V2迁移：用于支持积分相关的跨表操作
        - 封装了wallet + points + tasks + payments的跨表事务操作
        - 提供create_task_with_payment等积分扣除方法
        """
        from src.infrastructure.database.repositories_v2.composite.point_composite_repository import PointCompositeRepository
        return PointCompositeRepository(c.get("supabase_manager"))
    
    container.register_factory("point_composite_repository", point_composite_repository_factory)
    
    # 🔧 V2迁移：新增UserCompositeRepository工厂
    def user_composite_repository_factory(c):
        """创建UserCompositeRepository实例
        
        🔧 V2迁移：用于支持用户生命周期的跨表操作
        - 封装了users + wallet + stats + points + checkins的跨表事务操作
        - 提供用户注册、签到等完整流程方法
        """
        from src.infrastructure.database.repositories_v2.composite.user_composite_repository import UserCompositeRepository
        return UserCompositeRepository(c.get("supabase_manager"))
    
    container.register_factory("user_composite_repository", user_composite_repository_factory)
    
    # 🔧 V2迁移：新增SessionCompositeRepository工厂
    def session_composite_repository_factory(c):
        """创建SessionCompositeRepository实例
        
        🔧 V2迁移：用于支持会话管理的组合Repository
        - 封装了sessions + records + stats的跨表事务操作
        - 提供与旧版Repository兼容的接口
        """
        from src.infrastructure.database.repositories_v2.composite.session_composite_repository import SessionCompositeRepository
        return SessionCompositeRepository(c.get("supabase_manager"))
    
    container.register_factory("session_composite_repository", session_composite_repository_factory)
    
    # 修改：ActionRecordService始终使用组合Repository
    # 目的：完全迁移到V2组合仓库，移除旧仓库/并行测试分支，简化注入
    def action_record_service_factory(c):
        from src.domain.services.action_record_service import ActionRecordService
        service = ActionRecordService(
            action_record_repo=c.get("action_composite_repository"),
        )
        service.logger.info("🔧 ActionRecordService: 迁移完成 - 使用组合Repository")
        return service
    
    container.register_factory("action_record_service", action_record_service_factory)
    
    # 注册外部API
    def clothoff_api_factory(c):
        from src.infrastructure.external_apis.clothoff_api import ClothOffAPI
        settings = c.get("settings")
        return ClothOffAPI(
            api_url=getattr(settings.api, 'clothoff_api_url', 'https://api.example.com'),
            webhook_url=getattr(settings.api, 'clothoff_webhook_base_url', 'http://localhost'),
            api_key=getattr(settings.api, 'clothoff_api_key', 'test_key')
        )
    
    container.register_factory("clothoff_api", clothoff_api_factory)
    
    def payment_api_factory(c):
        from src.infrastructure.external_apis.payment_api import PaymentAPI
        return PaymentAPI()
    
    container.register_factory("payment_api", payment_api_factory)
    
    # 注册所有业务服务
    # 修改：UserService始终注入UserCompositeRepository和PointCompositeRepository
    # 目的：服务层只依赖组合仓库，移除旧仓库/并行验证逻辑
    def user_service_factory(c):
        from src.domain.services.user_service import UserService
        service = UserService(
            user_composite_repo=c.get("user_composite_repository"),
            point_composite_repo=c.get("point_composite_repository"),
            credit_settings=c.get("settings").credit
        )
        service.logger.info("🔧 UserService: 迁移完成 - 使用组合Repository")
        return service
    
    container.register_factory("user_service", user_service_factory)
    
    # 修改：ImageService仅注入PointCompositeRepository
    def image_service_factory(c):
        from src.domain.services.image_service import ImageService
        service = ImageService(
            point_composite_repo=c.get("point_composite_repository")
        )
        service.logger.info("🔧 ImageService: 迁移完成 - 仅依赖PointCompositeRepository")
        return service
    
    container.register_factory("image_service", image_service_factory)
    
    # 修改：PaymentService仅注入PointCompositeRepository，不再注入旧payment_order_repository或UserService
    # 目的：统一由组合仓库处理订单与积分事务，消除Service→Service写入链路
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
    
    # 修改：SessionService始终使用SessionCompositeRepository
    # 目的：统一由组合仓库处理会话及统计，移除旧仓库/并行验证分支
    def session_service_factory(c):
        from src.domain.services.session_service import SessionService
        service = SessionService(
            session_repo=c.get("session_composite_repository"),
        )
        service.logger.info("🔧 SessionService: 迁移完成 - 使用SessionCompositeRepository")
        return service
    
    container.register_factory("session_service", session_service_factory)
    
    def system_config_service_factory(c):
        from src.domain.services.system_config_service import SystemConfigService
        return SystemConfigService(
            config_repo=c.get("system_config_repository")
        )
    
    container.register_factory("system_config_service", system_config_service_factory)
    
    # 注册Webhook处理器
    def webhook_handler_factory(c):
        from src.infrastructure.messaging.webhook_handler import WebhookHandler
        return WebhookHandler(c.get("image_service"))
    
    container.register_factory("webhook_handler", webhook_handler_factory)
    
    def webhook_processor_factory(c):
        from src.infrastructure.messaging.webhook_handler import WebhookProcessor
        return WebhookProcessor(c.get("webhook_handler"))
    
    container.register_factory("webhook_processor", webhook_processor_factory)
    
    # 注册用户状态管理器
    def user_state_manager_factory(c):
        from src.interfaces.telegram.user_state_manager import UserStateManager
        return UserStateManager()
    
    container.register_factory("user_state_manager", user_state_manager_factory)

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
    
    # 注册图片回调处理器
    def image_webhook_handler_factory(c):
        from src.infrastructure.messaging.image_webhook import ImageWebhookHandler
        return ImageWebhookHandler(
            c.get("webhook_processor")
        )
    
    container.register_factory("image_webhook_handler", image_webhook_handler_factory)
    
    # 注册Telegram接口 - 🔧 新增session_service和action_record_service依赖
    def telegram_bot_factory(c):
        from src.interfaces.telegram.bot import TelegramBot
        settings = c.get("settings")
        return TelegramBot(
            bot_token=settings.bot.token,
            user_service=c.get("user_service"),
            image_service=c.get("image_service"),
            payment_service=c.get("payment_service"),
            session_service=c.get("session_service"),  # 🔧 新增
            action_record_service=c.get("action_record_service"),  # 🔧 新增
            system_config_service=c.get("system_config_service"),  # 🔧 新增
            webhook_processor=c.get("webhook_processor"),
            clothoff_api=c.get("clothoff_api"),
            admin_user_id=getattr(settings.bot, 'admin_user_id', None)
        )
    
    container.register_factory("telegram_bot", telegram_bot_factory)
    
    return container