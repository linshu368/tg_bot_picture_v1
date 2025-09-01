"""
支付API客户端 - 处理第三方支付接口调用
"""

import hashlib
import requests
import json
import time
import random
import string
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode

from src.utils.config.app_config import (
    PAYMENT_PID, PAYMENT_KEY, PAYMENT_SUBMIT_URL, PAYMENT_API_URL,
    PAYMENT_NOTIFY_URL, PAYMENT_RETURN_URL, CREDIT_PACKAGES
)


class PaymentAPI:
    """支付API客户端"""
    
    def __init__(self):
        self.pid = PAYMENT_PID
        self.key = PAYMENT_KEY
        self.submit_url = PAYMENT_SUBMIT_URL
        self.api_url = PAYMENT_API_URL
        self.notify_url = PAYMENT_NOTIFY_URL
        self.return_url = PAYMENT_RETURN_URL
        self.logger = logging.getLogger(__name__)
        
    def generate_order_no(self) -> str:
        """生成订单号"""
        timestamp = str(int(time.time()))
        random_str = ''.join(random.choices(string.digits, k=6))
        return f"{timestamp}{random_str}"
    
    def md5_sign(self, params: Dict[str, Any]) -> str:
        """
        MD5签名算法
        1. 将参数按ASCII码从小到大排序
        2. 拼接成URL键值对格式
        3. 与商户密钥拼接后MD5加密
        """
        # 过滤空值和签名相关参数
        filtered_params = {}
        for key, value in params.items():
            if key not in ['sign', 'sign_type'] and value is not None and value != '':
                filtered_params[key] = str(value)
        
        # 按ASCII码排序
        sorted_params = sorted(filtered_params.items())
        
        # 拼接成URL键值对格式
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # 与商户密钥拼接
        sign_string = query_string + self.key
        
        # MD5加密并转为小写
        return hashlib.md5(sign_string.encode('utf-8')).hexdigest().lower()
    
    def verify_sign(self, params: Dict[str, Any]) -> bool:
        """验证签名"""
        if 'sign' not in params:
            return False
        
        received_sign = params['sign']
        calculated_sign = self.md5_sign(params)
        
        return received_sign == calculated_sign
    
    def create_payment_url(self, order_no: str, package_id: str, 
                          payment_method: str = "alipay", user_ip: str = "127.0.0.1") -> Dict[str, Any]:
        """
        创建支付链接
        使用API接口支付，返回支付二维码或跳转链接
        """
        if package_id not in CREDIT_PACKAGES:
            return {"success": False, "message": "无效的积分包类型"}
        
        package_info = CREDIT_PACKAGES[package_id]
        
        # 构建请求参数
        params = {
            "pid": self.pid,
            "type": payment_method,
            "out_trade_no": order_no,
            "notify_url": self.notify_url,
            "return_url": self.return_url,
            "name": package_info["name"],
            "money": package_info["price"],
            "clientip": user_ip,
            "device": "mobile",
            "param": package_id,  # 业务扩展参数，用于标识积分包类型
            "sign_type": "MD5"
        }
        
        # 生成签名
        params["sign"] = self.md5_sign(params)
        
        # 添加调试日志
        self.logger.info(f"支付请求参数: {params}")
        self.logger.info(f"请求URL: {self.api_url}")
        
        try:
            # 发送POST请求
            response = requests.post(self.api_url, data=params, timeout=30)
            response.raise_for_status()
            
            # 记录响应
            self.logger.info(f"支付接口响应状态: {response.status_code}")
            self.logger.info(f"支付接口响应内容: {response.text}")
            
            result = response.json()
            
            # 添加详细调试日志
            self.logger.info(f"支付接口详细响应 - 支付方式: {payment_method}")
            self.logger.info(f"响应结果: {result}")
            
            if result.get("code") == 1:
                return {
                    "success": True,
                    "trade_no": result.get("trade_no"),
                    "payurl": result.get("payurl"),
                    "qrcode": result.get("qrcode"),
                    "urlscheme": result.get("urlscheme")
                }
            else:
                self.logger.error(f"支付接口返回错误: {result}")
                return {
                    "success": False,
                    "message": result.get("msg", "支付接口调用失败")
                }
                
        except requests.RequestException as e:
            self.logger.error(f"支付接口请求失败: {e}")
            return {"success": False, "message": "网络请求失败"}
        except json.JSONDecodeError as e:
            self.logger.error(f"支付接口响应解析失败: {e}")
            return {"success": False, "message": "响应格式错误"}
        except Exception as e:
            self.logger.error(f"创建支付链接失败: {e}")
            return {"success": False, "message": "系统错误"}
    
    def query_order(self, out_trade_no: str) -> Dict[str, Any]:
        """查询订单状态"""
        params = {
            "pid": self.pid,
            "out_trade_no": out_trade_no,
            "sign_type": "MD5"
        }
        
        # 生成签名
        params["sign"] = self.md5_sign(params)
        
        try:
            response = requests.post(f"{self.api_url}/query", data=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("code") == 1:
                return {
                    "success": True,
                    "order_info": result.get("data", {})
                }
            else:
                return {
                    "success": False,
                    "message": result.get("msg", "查询失败")
                }
                
        except Exception as e:
            self.logger.error(f"查询订单状态失败: {e}")
            return {"success": False, "message": "查询失败"} 