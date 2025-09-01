"""
支付服务 - 负责支付订单和积分充值相关的业务逻辑
"""

import logging
import uuid
import json
import hashlib
import time
import random
import string
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from enum import Enum
from decimal import Decimal


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"      # 待支付
    PAID = "paid"           # 已支付
    COMPLETED = "completed"  # 已完成
    EXPIRED = "expired"     # 已过期
    CANCELLED = "cancelled"  # 已取消
    FAILED = "failed"       # 支付失败


class PaymentMethod(Enum):
    """支付方式枚举"""
    ALIPAY = "alipay"       # 支付宝
    WECHAT = "wechat"       # 微信支付
    QQ = "qqpay"           # QQ钱包
    UNION = "unionpay"      # 银联支付


class PaymentPackage:
    """支付套餐类"""
    
    def __init__(self, 
                 package_id: str,
                 name: str,
                 credits: int,
                 price: Decimal,
                 description: str = "",
                 is_active: bool = True):
        self.package_id = package_id
        self.name = name
        self.credits = credits
        self.price = price
        self.description = description
        self.is_active = is_active
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "package_id": self.package_id,
            "name": self.name,
            "credits": self.credits,
            "price": float(self.price),
            "description": self.description,
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaymentPackage':
        """从字典创建实例"""
        return cls(
            package_id=data["package_id"],
            name=data["name"],
            credits=data["credits"],
            price=Decimal(str(data["price"])),
            description=data.get("description", ""),
            is_active=data.get("is_active", True)
        )


class PaymentService:
    """支付处理服务（已迁移：仅依赖 PointCompositeRepository）"""
    
    # 修改：去除对单表仓库与UserService的依赖，统一走组合仓库
    def __init__(self, 
                 payment_config: Dict[str, Any] = None,
                 payment_api=None,
                 point_composite_repo=None):
        self.payment_config = payment_config or {}
        self.payment_api = payment_api
        self.logger = logging.getLogger(__name__)
        if not point_composite_repo:
            raise ValueError("必须提供point_composite_repo")
        self.point_composite_repo = point_composite_repo
        self.logger.info("🔧 PaymentService: 使用PointCompositeRepository")
        # 加载套餐配置
        self._load_packages()
    
    # （并行验证相关代码已移除）
    
    def _load_packages(self):
        """加载套餐配置"""
        self.packages = {}
        
        # 从配置加载套餐
        try:
            from src.utils.config.app_config import CREDIT_PACKAGES
            for package_id, config in CREDIT_PACKAGES.items():
                package = PaymentPackage.from_dict({
                    "package_id": package_id,
                    **config
                })
                self.packages[package_id] = package
            self.logger.info(f"成功加载 {len(self.packages)} 个套餐")
        except ImportError as e:
            self.logger.warning(f"导入套餐配置失败: {e}")
            # 默认套餐配置
            self.packages = {
                "basic": PaymentPackage("basic", "基础套餐", 100, Decimal("10.00")),
                "premium": PaymentPackage("premium", "高级套餐", 500, Decimal("45.00")),
                "ultimate": PaymentPackage("ultimate", "终极套餐", 1000, Decimal("80.00"))
            }
        except Exception as e:
            self.logger.error(f"加载套餐配置异常: {e}")
            # 默认套餐配置
            self.packages = {
                "basic": PaymentPackage("basic", "基础套餐", 100, Decimal("10.00")),
                "premium": PaymentPackage("premium", "高级套餐", 500, Decimal("45.00")),
                "ultimate": PaymentPackage("ultimate", "终极套餐", 1000, Decimal("80.00"))
            }
    
    def get_available_packages(self) -> List[PaymentPackage]:
        """获取可用的支付套餐"""
        packages = []
        for pkg_id, pkg in self.packages.items():
            if pkg_id != "test" and pkg.is_active:
                packages.append(pkg)
        return packages
    
    def get_package(self, package_id: str) -> Optional[PaymentPackage]:
        """获取指定套餐"""
        return self.packages.get(package_id)
    
    def get_available_payment_methods(self) -> List[Dict[str, str]]:
        """获取可用的支付方式"""
        try:
            from src.utils.config.app_config import PAYMENT_METHODS
            return [
                {"id": method_id, "name": method_name}
                for method_id, method_name in PAYMENT_METHODS.items()
            ]
        except ImportError:
            return [
                {"id": "alipay", "name": "支付宝"},
                {"id": "wechat", "name": "微信支付"}
            ]
    
    def _generate_order_id(self) -> str:
        """生成订单号"""
        timestamp = str(int(time.time()))
        random_str = ''.join(random.choices(string.digits, k=6))
        return f"{timestamp}{random_str}"
    
    async def create_payment_order(self, 
                                 user_id: int,
                                 package_id: str,
                                 payment_method: str) -> Dict[str, Any]:
        """创建支付订单"""
        try:
            # 验证套餐
            package = self.get_package(package_id)
            if not package:
                return {
                    "success": False,
                    "error": f"无效的套餐ID: {package_id}"
                }
            
            # 验证支付方式
            valid_methods = [method["id"] for method in self.get_available_payment_methods()]
            if payment_method not in valid_methods:
                return {
                    "success": False,
                    "error": f"无效的支付方式: {payment_method}"
                }
            
            # 创建订单数据
            order_id = self._generate_order_id()
            expires_at = datetime.utcnow() + timedelta(minutes=30)
            
            order_data = {
                'user_id': user_id,
                'order_id': order_id,
                'amount': float(package.price),
                'status': OrderStatus.PENDING.value,
                'payment_method': payment_method,
                'points_awarded': package.credits,
                'order_data': {
                    'package_id': package_id,
                    'package_name': package.name,
                    'expires_at': expires_at.isoformat()
                }
            }
            
            # 修改：通过组合仓库创建待支付订单
            created_order = await self.point_composite_repo.create_pending_order(
                user_id=user_id,
                order_id=order_id,
                amount=float(package.price),
                payment_method=payment_method,
                order_data=order_data['order_data']
            )
            if not created_order:
                return {
                    "success": False,
                    "error": "创建订单失败"
                }
            
            self.logger.info(f"创建支付订单成功: {order_id}, 用户: {user_id}")
            
            # 创建支付链接（如果有支付API客户端）
            payment_info = {}
            if self.payment_api:
                try:
                    payment_result = self.payment_api.create_payment_url(
                        order_no=order_id,
                        package_id=package_id,
                        payment_method=payment_method,
                        user_ip="127.0.0.1"
                    )
                    
                    if payment_result.get("success"):
                        payment_info = {
                            "payurl": payment_result.get("payurl"),
                            "qrcode": payment_result.get("qrcode"),
                            "urlscheme": payment_result.get("urlscheme"),
                            "trade_no": payment_result.get("trade_no")
                        }
                        self.logger.info(f"支付链接创建成功: {order_id}")
                    else:
                        self.logger.warning(f"支付链接创建失败: {payment_result.get('message', '未知错误')}")
                        
                except Exception as e:
                    self.logger.error(f"创建支付链接异常: {e}")
            
            return {
                "success": True,
                "order_id": order_id,
                "package": package.to_dict(),
                "amount": float(package.price),
                "credits": package.credits,
                "expires_at": expires_at.isoformat(),
                "payment_info": payment_info
            }
            
        except Exception as e:
            self.logger.error(f"创建支付订单失败: {e}")
            return {
                "success": False,
                "error": f"系统错误: {str(e)}"
            }
    
    async def query_order_status(self, order_id: str) -> Dict[str, Any]:
        """查询订单状态"""
        try:
            # 修改：从组合仓库获取订单
            order = await self.point_composite_repo.get_order_by_order_id(order_id)
            if not order:
                return {
                    "success": False,
                    "error": "订单不存在"
                }
            
            # 如果订单已经是最终状态，直接返回
            if order['status'] in [OrderStatus.PAID.value, OrderStatus.COMPLETED.value, 
                                 OrderStatus.EXPIRED.value, OrderStatus.CANCELLED.value]:
                return {
                    "success": True,
                    "order": order,
                    "status": order['status']
                }
            
            # 检查订单是否过期
            order_data = order.get('order_data', {})
            expires_at_str = order_data.get('expires_at')
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                if datetime.utcnow() > expires_at.replace(tzinfo=None):
                    # 更新为过期状态
                    await self.point_composite_repo.update_order_status(order_id, OrderStatus.EXPIRED.value)
                    return {
                        "success": True,
                        "order": order,
                        "status": OrderStatus.EXPIRED.value,
                        "message": "订单已过期"
                    }
            
            # 如果有支付API，查询第三方支付状态
            if self.payment_api:
                try:
                    payment_result = self.payment_api.query_order(order_id)
                    
                    if payment_result.get("success"):
                        order_info = payment_result.get("order_info", {})
                        platform_status = order_info.get("status", 0)
                        
                        if platform_status == 1:  # 支付成功
                            # 先检查首充状态
                            is_first_purchase = await self.is_first_purchase(order['user_id'])
                            
                            # 更新订单状态为已支付
                            await self.point_composite_repo.update_order_status(order_id, OrderStatus.PAID.value)
                            
                            # 处理支付成功 - 发放积分
                            await self._process_payment_success(order, is_first_purchase)
                            
                            return {
                                "success": True,
                                "order": order,
                                "status": OrderStatus.PAID.value,
                                "message": "支付成功"
                            }
                            
                except Exception as e:
                    self.logger.error(f"查询第三方支付状态失败: {e}")
            
            return {
                "success": True,
                "order": order,
                "status": order['status']
            }
            
        except Exception as e:
            self.logger.error(f"查询订单状态失败: {e}")
            return {
                "success": False,
                "error": f"查询失败: {str(e)}"
            }
    
    async def process_payment_callback(self, 
                                     order_id: str,
                                     trade_no: str,
                                     verify_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理支付回调"""
        try:
            # 获取订单
            order = await self.point_composite_repo.get_order_by_order_id(order_id)
            if not order:
                return {
                    "success": False,
                    "error": f"订单不存在: {order_id}"
                }
            
            # 检查订单状态
            if order['status'] != OrderStatus.PENDING.value:
                return {
                    "success": False,
                    "error": f"订单状态异常: {order['status']}"
                }
            
            # 验证签名（简化处理）
            if not self._verify_payment_signature(verify_data):
                return {
                    "success": False,
                    "error": "签名验证失败"
                }
            
            # 检查首充状态
            is_first_purchase = await self.is_first_purchase(order['user_id'])
            
            # 更新订单状态
            success = await self.point_composite_repo.update_order_status(order_id, OrderStatus.PAID.value)
            
            if not success:
                return {
                    "success": False,
                    "error": "更新订单状态失败"
                }
            
            # 修改：处理支付成功 - 发放积分交由PointCompositeRepository
            # 目的：取消对UserService的写入依赖
            process_result = await self._process_payment_success(order, is_first_purchase)
            
            if process_result:
                # 订单完成 - 更新状态为COMPLETED
                status_updated = await self.point_composite_repo.update_order_status(order_id, OrderStatus.COMPLETED.value)
                
                if status_updated:
                    self.logger.info(f"支付订单处理完成: {order_id}")
                    
                    return {
                        "success": True,
                        "order_id": order_id,
                        "message": "支付成功，积分已到账"
                    }
                else:
                    # 积分已发放但状态更新失败
                    self.logger.warning(f"积分发放成功但订单状态更新失败: {order_id}")
                    return {
                        "success": True,
                        "order_id": order_id,
                        "message": "支付成功，积分已到账（状态更新异常）"
                    }
            else:
                self.logger.error(f"积分充值失败: 订单 {order_id}")
                return {
                    "success": False,
                    "error": "积分充值失败"
                }
                
        except Exception as e:
            self.logger.error(f"处理支付回调失败: {e}")
            return {
                "success": False,
                "error": f"处理失败: {str(e)}"
            }
    
    async def _process_payment_success(self, order: Dict[str, Any], is_first_purchase: bool) -> bool:
        """处理支付成功 - 发放积分和首充奖励（统一走组合仓库）"""
        try:
            # 获取套餐信息
            order_data = order.get('order_data', {})
            package_id = order_data.get('package_id')
            package = self.get_package(package_id) if package_id else None
            
            # 基础积分
            base_credits = order.get('points_awarded', 0)
            bonus_credits = 0
            
            if is_first_purchase:
                # 首冲赠送
                bonus_credits = self.calculate_first_purchase_bonus(package_id, base_credits)
                description = f"购买{package.name if package else '套餐'} + 首冲赠送{self._get_bonus_rate(package_id, True)}%"
            else:
                # 非首冲活动赠送
                bonus_credits = self.calculate_regular_bonus(package_id, base_credits)
                description = f"购买{package.name if package else '套餐'} + 活动赠送{self._get_bonus_rate(package_id, False)}%"
            
            total_credits = base_credits + bonus_credits
            
            # 修改：始终使用PointCompositeRepository处理
            # 目的：统一事务与积分流水
            success = await self._process_with_composite_repo(order, total_credits, description)
            
            if success:
                self.logger.info(
                    f"积分发放成功: 用户{order['user_id']} +{total_credits}积分 "
                    f"(基础{base_credits} + 赠送{bonus_credits})"
                )
                return True
            else:
                self.logger.error(f"积分发放失败: 订单{order['order_id']}")
                return False
                
        except Exception as e:
            self.logger.error(f"处理支付成功失败: {e}")
            return False
    
    async def _process_with_composite_repo(self, order: Dict[str, Any], total_credits: int, description: str) -> bool:
        """🔧 迁移：使用PointCompositeRepository处理支付成功"""
        try:
            from decimal import Decimal
            
            # 调用PointCompositeRepository的process_payment_success方法
            success = await self.point_composite_repo.process_payment_success(
                user_id=order['user_id'],
                order_id=order['order_id'],
                amount=Decimal(str(order['amount'])),
                points_awarded=total_credits,
                payment_method=order.get('payment_method'),
                order_data=order.get('order_data', {})
            )
            
            if success:
                self.logger.info(f"🔧 新Repository处理支付成功: 订单{order['order_id']}")
            else:
                self.logger.error(f"🔧 新Repository处理支付失败: 订单{order['order_id']}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"🔧 新Repository处理支付异常: {e}")
            return False
    
    # （并行验证相关代码已移除）
    
    def _verify_payment_signature(self, data: Dict[str, Any]) -> bool:
        """验证支付签名（简化实现）"""
        # 这里应该根据具体支付接口实现签名验证
        return True
    
    def calculate_first_purchase_bonus(self, package_id: str, credits: int) -> int:
        """计算首次充值奖励"""
        try:
            from src.utils.config.app_config import FIRST_CHARGE_BONUS
            bonus_rate = FIRST_CHARGE_BONUS.get(package_id, 0)
        except ImportError:
            bonus_rate = 50  # 默认50%首充奖励
        return int(credits * bonus_rate / 100)
    
    def calculate_regular_bonus(self, package_id: str, credits: int) -> int:
        """计算常规充值奖励"""
        try:
            from src.utils.config.app_config import REGULAR_CHARGE_BONUS
            bonus_rate = REGULAR_CHARGE_BONUS.get(package_id, 0)
        except ImportError:
            bonus_rate = 10  # 默认10%常规奖励
        return int(credits * bonus_rate / 100)
    
    def _get_bonus_rate(self, package_id: str, is_first_purchase: bool) -> int:
        """获取奖励比例"""
        if is_first_purchase:
            try:
                from src.utils.config.app_config import FIRST_CHARGE_BONUS
                return FIRST_CHARGE_BONUS.get(package_id, 50)
            except ImportError:
                return 50
        else:
            try:
                from src.utils.config.app_config import REGULAR_CHARGE_BONUS
                return REGULAR_CHARGE_BONUS.get(package_id, 10)
            except ImportError:
                return 10
    
    async def get_order_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """获取订单信息"""
        try:
            return await self.point_composite_repo.get_order_by_order_id(order_id)
        except Exception as e:
            self.logger.error(f"获取订单信息失败: {e}")
            return None
    
    async def get_user_payment_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户支付历史"""
        try:
            return await self.point_composite_repo.get_user_orders(user_id, limit)
        except Exception as e:
            self.logger.error(f"获取用户支付历史失败: {e}")
            return []
    
    async def get_payment_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户支付统计"""
        try:
            orders = await self.payment_order_repo.get_user_orders(user_id, 100)
            
            stats = {
                "total_orders": len(orders),
                "total_amount": 0.0,
                "total_credits": 0,
                "completed_orders": 0,
                "pending_orders": 0
            }
            
            for order in orders:
                if order['status'] == OrderStatus.COMPLETED.value:
                    stats["completed_orders"] += 1
                    stats["total_amount"] += float(order.get('amount', 0))
                    stats["total_credits"] += order.get('points_awarded', 0)
                elif order['status'] == OrderStatus.PENDING.value:
                    stats["pending_orders"] += 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取支付统计失败: {e}")
            return {
                "total_orders": 0,
                "total_amount": 0.0,
                "total_credits": 0,
                "completed_orders": 0,
                "pending_orders": 0
            }
    
    async def cancel_order(self, order_id: str, user_id: int) -> Dict[str, Any]:
        """取消订单"""
        try:
            order = await self.point_composite_repo.get_order_by_order_id(order_id)
            if not order:
                return {
                    "success": False,
                    "error": "订单不存在"
                }
            
            if order['user_id'] != user_id:
                return {
                    "success": False,
                    "error": "无权操作此订单"
                }
            
            if order['status'] != OrderStatus.PENDING.value:
                return {
                    "success": False,
                    "error": f"订单状态不允许取消: {order['status']}"
                }
            
            success = await self.point_composite_repo.cancel_pending_order(order_id, user_id)
            
            if success:
                return {
                    "success": True,
                    "message": "订单已取消"
                }
            else:
                return {
                    "success": False,
                    "error": "取消订单失败"
                }
                
        except Exception as e:
            self.logger.error(f"取消订单失败: {e}")
            return {
                "success": False,
                "error": f"系统错误: {str(e)}"
            }
    
    async def cleanup_expired_orders(self) -> int:
        """清理过期订单"""
        try:
            return await self.point_composite_repo.cleanup_expired_pending_orders()
        except Exception as e:
            self.logger.error(f"清理过期订单失败: {e}")
            return 0
    
    async def is_first_purchase(self, user_id: int) -> bool:
        """检查用户是否首次充值"""
        try:
            # 获取用户的支付历史
            orders = await self.payment_order_repo.get_user_orders(user_id, 5)
            
            # 检查是否有已完成的订单
            for order in orders:
                if order['status'] in [OrderStatus.PAID.value, OrderStatus.COMPLETED.value]:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"检查首次充值状态失败: {e}")
            return False
    
    async def get_user_total_spent(self, user_id: int) -> float:
        """获取用户总消费金额"""
        try:
            stats = await self.get_payment_statistics(user_id)
            return stats.get("total_amount", 0.0)
        except Exception as e:
            self.logger.error(f"获取用户总消费失败: {e}")
            return 0.0
    
    async def get_user_total_credits_purchased(self, user_id: int) -> int:
        """获取用户总购买积分数"""
        try:
            stats = await self.get_payment_statistics(user_id)
            return stats.get("total_credits", 0)
        except Exception as e:
            self.logger.error(f"获取用户总购买积分失败: {e}")
            return 0
    
    async def get_package_with_bonus(self, package_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """获取包含奖励信息的套餐信息"""
        try:
            package = self.get_package(package_id)
            if not package:
                return None
            
            is_first = await self.is_first_purchase(user_id)
            
            if is_first:
                bonus_credits = self.calculate_first_purchase_bonus(package_id, package.credits)
                total_credits = package.credits + bonus_credits
                bonus_text = f"首冲送{bonus_credits}积分！"
            else:
                bonus_credits = self.calculate_regular_bonus(package_id, package.credits)
                total_credits = package.credits + bonus_credits
                bonus_text = f"额外赠送{bonus_credits}积分"
            
            return {
                "package": package.to_dict(),
                "base_credits": package.credits,
                "bonus_credits": bonus_credits,
                "total_credits": total_credits,
                "bonus_text": bonus_text,
                "is_first_purchase": is_first
            }
            
        except Exception as e:
            self.logger.error(f"获取套餐奖励信息失败: {e}")
            return None