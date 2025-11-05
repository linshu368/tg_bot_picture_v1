"""
配置管理模块
支持环境变量覆盖和多环境配置
"""

import os
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
    
    # Supabase配置
    supabase_url: str
    supabase_key: str
    supabase_service_key: str = ""  # 可选，用于管理员操作
    pool_size: int = 5
    timeout: int = 30

    

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
   

class ServicesSettings:
    """
    服务配置
    """
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        config_dict = config_dict or {}
       
@dataclass
class AppSettings:
    """应用主配置"""
    bot: BotSettings
    database: DatabaseSettings
    payment: PaymentSettings
    credit: CreditSettings
    services: ServicesSettings  # 🔧 V2迁移：添加服务配置
    
    # 积分包配置
    credit_packages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    first_charge_bonus: Dict[str, int] = field(default_factory=dict)
    
    # 其他配置
    max_queue_size: int = 100
    rate_limit_seconds: int = 30


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
    
   
    # 积分配置
    credit_config = CreditSettings(
        default_credits=int(os.getenv("DEFAULT_CREDITS", "50")),
        daily_signin_reward=int(os.getenv("DAILY_SIGNIN_REWARD", "10"))
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
    
    # 服务配置（目前为空，未来可扩展）
    services_config = ServicesSettings({})
    
    return AppSettings(
        bot=bot_config,
        database=database_config,
        credit=credit_config,
        payment=payment_config,
        services=services_config
    ) 


# =============================
# 文字 Bot 独立配置（与主项目隔离）
# =============================
@dataclass
class TextBotSettings:
    """文字 Bot 配置（独立于主 Bot）"""
    token: str = "8423660455:AAFd5I5Ax3-gYZEqc_ZL05owE2lCyI5E2EM"
    admin_user_id: int = 7116726082
   


@dataclass
class TextAppSettings:
    """文字 Bot 应用配置根对象"""
    text_bot: TextBotSettings


def get_text_settings() -> TextAppSettings:
    """获取文字 Bot 配置，优先使用环境变量，缺失时回退到默认值"""
    # 默认配置
    default_config = TextBotSettings()

    # 读取环境变量（当前暂未设置）
    env_token = os.getenv("TEXT_BOT_TOKEN", "").strip()
    env_admin_id = os.getenv("TEXT_BOT_ADMIN_USER_ID", "").strip()

    # 仅当提供非空值时覆盖默认值
    token = env_token if env_token else default_config.token

    admin_user_id = default_config.admin_user_id
    if env_admin_id:
        try:
            parsed = int(env_admin_id)
            if parsed > 0:
                admin_user_id = parsed
        except ValueError:
            # 无法解析则继续使用默认值
            pass

    text_bot_config = TextBotSettings(
        token=token,
        admin_user_id=admin_user_id
    )
    return TextAppSettings(text_bot=text_bot_config)