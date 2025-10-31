"""
应用配置常量
"""

# 积分系统配置
DEFAULT_CREDITS = 50  # 新用户默认积分
DAILY_SIGNIN_REWARD = 10  # 每日签到奖励积分
DEFAULT_USER_LEVEL = 1  # 新用户默认等级


# 支付方式配置
PAYMENT_METHODS = {
    "alipay": "支付宝",
    "wxpay": "微信支付",
    "usdt": "USDT(TRC20)"
}

# 支付配置
PAYMENT_PID = "1002"  # 商户ID
PAYMENT_KEY = "0wZnsONwLvWSvkUSRUgO0bbA4SdvbVpD"  # 商户密钥
PAYMENT_SUBMIT_URL = "https://pay.jlusdt.com/submit.php"  # 页面跳转支付
PAYMENT_API_URL = "https://pay.jlusdt.com/mapi.php"  # API接口支付
PAYMENT_NOTIFY_URL = "http://108.61.188.236:5002/payment/notify"  # 异步通知地址 - V1项目使用5002端口
PAYMENT_RETURN_URL = "http://108.61.188.236:5002/payment/return"  # 跳转通知地址 - V1项目使用5002端口

# 积分包配置（照抄原始项目）
CREDIT_PACKAGES = {
    "test": {"credits": 1, "price": "1.00", "name": "测试充值", "level": "test"},
    "bronze": {"credits": 20, "price": "15.00", "name": "普通青铜", "level": "bronze"},
    "silver": {"credits": 70, "price": "36.00", "name": "VIP白银", "level": "silver"},
    "gold": {"credits": 200, "price": "75.00", "name": "VIP黄金", "level": "gold"},
    "diamond": {"credits": 500, "price": "155.00", "name": "VIP钻石", "level": "diamond"},
    "platinum": {"credits": 1500, "price": "388.00", "name": "VIP铂金", "level": "platinum"},
    "king": {"credits": 3500, "price": "778.00", "name": "VIP王者", "level": "king"}
}

# 首冲赠送比例配置（照抄原始项目）
FIRST_CHARGE_BONUS = {
    "test": 0,      # 0% 无赠送
    "bronze": 0,    # 0% 无赠送
    "silver": 50,   # 50% 赠送
    "gold": 80,     # 80% 赠送
    "diamond": 80,  # 80% 赠送
    "platinum": 100, # 100% 赠送
    "king": 100     # 100% 赠送
}

# 非首冲活动赠送比例配置（照抄原始项目）
REGULAR_CHARGE_BONUS = {
    "test": 0,      # 0% 无赠送
    "bronze": 0,    # 0% 无赠送
    "silver": 10,   # 10% 赠送
    "gold": 15,     # 15% 赠送
    "diamond": 20,  # 20% 赠送
    "platinum": 25, # 25% 赠送
    "king": 30      # 30% 赠送
}

