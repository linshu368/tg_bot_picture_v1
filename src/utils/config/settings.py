"""
配置管理模块
支持环境变量覆盖和多环境配置
"""

import os
import logging
from typing import Dict, Any
from dataclasses import dataclass, field

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    # 加载.env文件
    if os.path.exists('.env'):
        load_dotenv('.env')
    else:
        load_dotenv()
except ImportError:
    # 如果没有安装python-dotenv，忽略
    pass


@dataclass
class BotSettings:
    """Bot基础配置"""
    token: str
    admin_user_id: int
    webhook_url: str = ""
    

@dataclass 
class DatabaseSettings:
    """数据库配置 - 迁移到Supabase"""
    # SQLite配置（保留作为备份）
    # path: str = "data/telegram_bot.db"
    # pool_size: int = 5
    # timeout: int = 30
    
    # Supabase配置
    supabase_url: str
    supabase_key: str
    supabase_service_key: str = ""  # 可选，用于管理员操作
    pool_size: int = 5
    timeout: int = 30


@dataclass
class ApiSettings:
    """外部API配置"""
    clothoff_api_url: str
    clothoff_video_api_url: str
    clothoff_api_key: str
    clothoff_webhook_base_url: str
    

@dataclass
class PaymentSettings:
    """支付配置"""
    payment_pid: str
    payment_key: str
    submit_url: str
    api_url: str
    notify_url: str
    return_url: str
    

@dataclass
class CreditSettings:
    """积分系统配置"""
    default_credits: int = 30
    daily_signin_reward: int = 4
    cost_image_generation: int = 5
    cost_video_generation: int = 10
    cost_faceswap_photo: int = 8
    cost_faceswap_video: int = 15
    cost_quick_undress: int = 10
    cost_custom_undress: int = 10


class ServicesSettings:
    """服务配置
    
    🔧 V2迁移：支持服务迁移的配置控制
    """
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        config_dict = config_dict or {}
        
        # 🔧 ActionRecordService迁移模式配置
        # stable: 稳定模式，使用旧Repository
        # parallel_test: 并行测试模式，主用旧Repository，验证新Repository  
        # migrated: 迁移完成，使用新Repository
        self.action_record_migration_mode = config_dict.get('action_record_migration_mode', 'stable')
        
        # 🔧 SessionService迁移模式配置
        # stable: 稳定模式，使用旧Repository (分离的session_repo + session_record_repo)
        # parallel_test: 并行测试模式，主用旧Repository，验证新SessionCompositeRepository  
        # migrated: 迁移完成，使用新SessionCompositeRepository
        self.session_service_migration_mode = config_dict.get('session_service_migration_mode', 'stable')
        
        # 🔧 ImageService迁移模式配置
        # stable: 稳定模式，使用ImageTaskRepository，积分在外部处理
        # parallel_test: 并行测试模式，主用ImageTaskRepository，验证PointCompositeRepository
        # migrated: 迁移完成，create_image_task使用PointCompositeRepository
        self.image_service_migration_mode = config_dict.get('image_service_migration_mode', 'stable')
        
        # 🔧 PaymentService迁移模式配置
        # stable: 稳定模式，使用PaymentOrderRepository，积分通过UserService处理
        # parallel_test: 并行测试模式，主用PaymentOrderRepository，验证PointCompositeRepository
        # migrated: 迁移完成，支付成功处理使用PointCompositeRepository
        self.payment_service_migration_mode = config_dict.get('payment_service_migration_mode', 'stable')
        
        # 🔧 UserService迁移模式配置
        # stable: 稳定模式，使用分离的user_repo + point_repo + daily_checkin_repo
        # parallel_test: 并行测试模式，主用旧Repository，验证UserCompositeRepository
        # migrated: 迁移完成，使用UserCompositeRepository + PointCompositeRepository
        self.user_service_migration_mode = config_dict.get('user_service_migration_mode', 'stable')


@dataclass
class AppSettings:
    """应用主配置"""
    bot: BotSettings
    database: DatabaseSettings
    api: ApiSettings
    payment: PaymentSettings
    credit: CreditSettings
    services: ServicesSettings  # 🔧 V2迁移：添加服务配置
    
    # 积分包配置
    credit_packages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    first_charge_bonus: Dict[str, int] = field(default_factory=dict)
    
    # 其他配置
    max_queue_size: int = 100
    rate_limit_seconds: int = 30
    image_processing_timeout: int = 300


def get_settings() -> AppSettings:
    """获取应用配置，支持环境变量覆盖"""
    
    # Bot配置
    bot_config = BotSettings(
        token=os.getenv("BOT_TOKEN", "8434459931:AAGjvRnY4PJEGf1OVjA1bxprLZHF4P85qdc"),
        admin_user_id=int(os.getenv("ADMIN_USER_ID", "6176157969")),
        webhook_url=os.getenv("WEBHOOK_URL", "")
    )
    
    # 数据库配置
    database_config = DatabaseSettings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
        timeout=int(os.getenv("DATABASE_TIMEOUT", "30"))
    )
    
    # API配置
    api_config = ApiSettings(
        clothoff_api_url=os.getenv("CLOTHOFF_API_URL", "https://public-api.clothoff.net/undress"),
        clothoff_video_api_url=os.getenv("CLOTHOFF_VIDEO_API_URL", "https://pub-api.clothoff.net/api/videoGenerations/animate"),
        clothoff_api_key=os.getenv("CLOTHOFF_API_KEY", "d1eda76ff2c9f5c7f3827f82f76479ff339f7526"),
        clothoff_webhook_base_url=os.getenv("CLOTHOFF_WEBHOOK_BASE_URL", "http://108.61.188.236")
    )
    
    # 积分配置
    credit_config = CreditSettings(
        default_credits=int(os.getenv("DEFAULT_CREDITS", "50")),
        daily_signin_reward=int(os.getenv("DAILY_SIGNIN_REWARD", "10")),
        cost_image_generation=int(os.getenv("COST_IMAGE_GENERATION", "15")),
        cost_video_generation=int(os.getenv("COST_VIDEO_GENERATION", "20"))
    )
    
    # 支付配置
    payment_config = PaymentSettings(
        payment_pid=os.getenv("PAYMENT_PID", ""),
        payment_key=os.getenv("PAYMENT_KEY", ""),
        submit_url=os.getenv("PAYMENT_SUBMIT_URL", ""),
        api_url=os.getenv("PAYMENT_API_URL", ""),
        notify_url=os.getenv("PAYMENT_NOTIFY_URL", ""),
        return_url=os.getenv("PAYMENT_RETURN_URL", "")
    )
    
    # 🔧 V2迁移：服务配置
    services_config = ServicesSettings({
        'action_record_migration_mode': os.getenv("ACTION_RECORD_MIGRATION_MODE", "stable"),
        'session_service_migration_mode': os.getenv("SESSION_SERVICE_MIGRATION_MODE", "stable"),
        'image_service_migration_mode': os.getenv("IMAGE_SERVICE_MIGRATION_MODE", "stable"),
        'payment_service_migration_mode': os.getenv("PAYMENT_SERVICE_MIGRATION_MODE", "stable"),
        'user_service_migration_mode': os.getenv("USER_SERVICE_MIGRATION_MODE", "stable")
    })
    
    return AppSettings(
        bot=bot_config,
        database=database_config,
        api=api_config,
        credit=credit_config,
        payment=payment_config,
        services=services_config  # 🔧 V2迁移：添加服务配置
    ) 


# =============================
# 文字 Bot 独立配置（与主项目隔离）
# =============================
@dataclass
class TextBotSettings:
    """文字 Bot 配置（独立于主 Bot）"""
    token: str = ""
    admin_user_id: int = 7116726082
    bot_username: str = ""
    role_channel_url: str = "https://t.me/ai_role_list"
    environment: str = "dev"  # dev | staging | prod
   


@dataclass
class TextAppSettings:
    """文字 Bot 应用配置根对象"""
    text_bot: TextBotSettings


def get_text_settings() -> TextAppSettings:
    """获取文字 Bot 配置，优先使用环境变量，缺失时回退到默认值"""
    # 默认配置
    default_config = TextBotSettings()

    # 读取环境变量（系统变量优先，其次 .env，最后默认值）
    env = os.getenv("ENV", default_config.environment).strip() or default_config.environment
    env_token = os.getenv("TEXT_BOT_TOKEN", default_config.token).strip()
    env_admin_id = os.getenv("TEXT_BOT_ADMIN_USER_ID", str(default_config.admin_user_id)).strip()
    env_bot_username = os.getenv("BOT_USERNAME", default_config.bot_username).strip()
    env_role_channel_url = os.getenv("ROLE_CHANNEL_URL", default_config.role_channel_url).strip()

    # 规范化与解析
    token = env_token
    try:
        parsed_admin_id = int(env_admin_id) if env_admin_id else default_config.admin_user_id
        admin_user_id = parsed_admin_id if parsed_admin_id > 0 else default_config.admin_user_id
    except ValueError:
        logging.warning("TEXT_BOT_ADMIN_USER_ID 无法解析为整数，使用默认值")
        admin_user_id = default_config.admin_user_id

    bot_username = env_bot_username
    role_channel_url = env_role_channel_url
    if role_channel_url and not role_channel_url.startswith("https://t.me/"):
        logging.warning(f"ROLE_CHANNEL_URL 非 t.me 链接：{role_channel_url}，使用默认值")
        role_channel_url = default_config.role_channel_url

    # 环境强校验（prod 更严格）
    if env == "prod":
        if not token:
            raise ValueError("TEXT_BOT_TOKEN 未配置（prod 必填）")
        if not bot_username:
            raise ValueError("BOT_USERNAME 未配置（prod 建议必填）")
        if not role_channel_url or not role_channel_url.startswith("https://t.me/"):
            raise ValueError("ROLE_CHANNEL_URL 非法（prod 必填且需以 https://t.me/ 开头）")
    else:
        if not token:
            logging.warning("TEXT_BOT_TOKEN 未配置（非 prod 环境将无法连接 Bot）")
        if not bot_username:
            logging.info("BOT_USERNAME 未配置（可选）")
        if role_channel_url == default_config.role_channel_url:
            logging.info(f"ROLE_CHANNEL_URL 使用默认值：{role_channel_url}")

    text_bot_config = TextBotSettings(
        token=token or default_config.token,
        admin_user_id=admin_user_id,
        bot_username=bot_username or default_config.bot_username,
        role_channel_url=role_channel_url or default_config.role_channel_url,
        environment=env
    )
    return TextAppSettings(text_bot=text_bot_config)