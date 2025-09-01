"""
应用配置常量
仅支持图片去衣功能
"""

# 积分系统配置
DEFAULT_CREDITS = 50  # 新用户默认积分
DAILY_SIGNIN_REWARD = 10  # 每日签到奖励积分
DEFAULT_USER_LEVEL = 1  # 新用户默认等级

# UID系统配置
UID_PREFIX = "u_"  # 身份码前缀
UID_LENGTH = 8     # 身份码长度

# 操作消耗积分配置 - 仅图片去衣功能
COST_QUICK_UNDRESS = 10  # 快速去衣消耗积分
COST_CUSTOM_UNDRESS = 10  # 自定义去衣消耗积分

# 人脸交换功能消耗积分配置（暂时保留，但不提供实际功能）
COST_FACESWAP_PHOTO = 15  # 人脸交换图片消耗积分
COST_FACESWAP_VIDEO = 20  # 人脸交换视频消耗积分

# 快速去衣默认参数
QUICK_UNDRESS_DEFAULTS = {
    "cloth": "naked",
    "body_type": "normal",
    "breast_size": "normal",
    "butt_size": "normal",
    "age": "25"
}

# 自定义去衣选项配置
CLOTH_OPTIONS = [
    "naked", "bikini", "lingerie", "sport wear", "bdsm", "latex",
    "teacher", "schoolgirl", "bikini leopard", "naked cum",
    "naked tatoo", "witch", "sexy witch", "sexy maid"
]

# 姿势选项（分页显示，每页10个）
POSE_OPTIONS = [
    "Blowjob", "Doggy Style", "Cumshot", "Cumshot POV", "Shower Room", "Shibari", "Ahegao", "Ahegao cum",
    "Holding tits", "Missionary POV", "Cowgirl POV", "Anal Fuck", "Legs up presenting", "Spreading legs",
    "Tit Fuck", "TGirl", "Tits On Glass", "Christmas", "Winter 1", "Winter 2", "Winter 3", "Winter 4",
    "Winter 5", "Winter 6", "Winter 7", "Winter 8", "Winter 9", "Bikini 1", "Bikini 2", "Bikini 3", "Bikini 4",
    "Bikini 5", "Bikini 6", "Bikini 8", "Bikini 9", "Lingerie 1", "Lingerie 2", "Lingerie 3", "Lingerie 4",
    "Lingerie 5", "Lingerie 6", "Lingerie 7", "Lingerie 8", "Lingerie 9", "BDSM 1", "BDSM 2", "BDSM 3",
    "BDSM 4", "BDSM 5", "BDSM 6", "BDSM 7", "BDSM 8", "BDSM 9", "Shows tits", "Missionary bouquet",
    "Exhibitionism 1", "Exhibitionism 2", "Exhibitionism 3", "Exhibitionism 4", "Exhibitionism 5",
    "Exhibitionism 6", "Exhibitionism 7", "Exhibitionism 8", "Exhibitionism 9",
    "Interracial Collection 1", "Interracial Collection 2", "Interracial Collection 3",
    "Interracial Collection 4", "Interracial Collection 5", "Interracial Collection 6",
    "Interracial Collection 7", "Interracial Collection 8", "Interracial Collection 9",
    "Wet girl 1", "Wet girl 2", "Wet girl 3", "Wet girl 4", "Wet girl 5", "Wet girl 6", "Wet girl 7", "Wet girl 8",
    "Wet girl 9", "Spring Collection 1", "Spring Collection 2", "Spring Collection 3", "Spring Collection 4",
    "Spring Collection 5", "Spring Collection 6", "Spring Collection 7", "Spring Collection 8", "Spring Collection 9",
    "Lace Delicacy 1", "Lace Delicacy 2", "Lace Delicacy 3", "Lace Delicacy 4", "Lace Delicacy 5", "Lace Delicacy 6",
    "Lace Delicacy 7", "Lace Delicacy 8", "Bonus Collection 1", "Bonus Collection 2", "Bonus Collection 3",
    "Bonus Collection 4"
]

# 用户偏好选项
BODY_TYPE_OPTIONS = ["skinny", "normal", "curvy", "muscular"]
BREAST_SIZE_OPTIONS = ["small", "normal", "big"]
BUTT_SIZE_OPTIONS = ["small", "normal", "big"]
AGE_OPTIONS = ["18", "20", "22", "25", "28", "30", "35", "40"]

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

# 分页配置
ITEMS_PER_PAGE = 8  # 每页显示项目数
CLOTH_PER_PAGE = 6  # 衣服选项每页显示数
POSE_PER_PAGE = 10  # 姿势选项每页显示数 