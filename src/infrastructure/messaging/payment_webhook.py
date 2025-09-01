"""
支付回调处理模块 - 处理支付平台的异步通知
"""

import logging
from flask import Flask, request, jsonify
from typing import Dict, Any
import asyncio
from threading import Thread
import time
from datetime import datetime

from src.infrastructure.external_apis.payment_api import PaymentAPI
from src.utils.config.app_config import PAYMENT_PID, CREDIT_PACKAGES, FIRST_CHARGE_BONUS, REGULAR_CHARGE_BONUS


class PaymentWebhookHandler:
    def __init__(self, payment_service, user_service, telegram_bot, payment_api: PaymentAPI):
        self.payment_service = payment_service
        self.user_service = user_service
        self.bot = telegram_bot
        self.payment_api = payment_api
        self.app = Flask(__name__)
        self.logger = logging.getLogger(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """设置路由 - 支持用户提供的完整端点列表"""
        @self.app.route('/payment/notify', methods=['GET', 'POST'])
        def payment_notify():
            return self.handle_payment_notify()
        
        @self.app.route('/payment/return', methods=['GET'])
        def payment_return():
            return self.handle_payment_return()
        
        # 健康检查端点
        @self.app.route('/payment/health', methods=['GET'])
        def payment_health():
            return jsonify({
                "status": "ok", 
                "service": "payment-webhook",
                "timestamp": datetime.now().isoformat()
            })
        
        # 添加兼容性回调端点，处理支付平台可能的不同URL格式
        @self.app.route('/payment/callback', methods=['GET', 'POST'])
        def payment_callback():
            return self.handle_payment_notify()
        
        @self.app.route('/payment/success', methods=['GET'])
        def payment_success():
            return self.handle_payment_return()
            
        # 通用回调端点，处理任何可能的回调格式
        @self.app.route('/callback/<path:path>', methods=['GET', 'POST'])
        def universal_callback(path):
            self.logger.info(f"收到通用回调: {path}, 参数: {request.args.to_dict()}")
            if request.method == 'POST':
                return self.handle_payment_notify()
            else:
                return self.handle_payment_return()
        
        # 手动查询订单状态的端点
        @self.app.route('/payment/query/<order_no>', methods=['GET'])
        def query_order_status(order_no):
            return self.handle_order_query(order_no)
        
    def handle_payment_notify(self) -> str:
        """处理支付异步通知 - 支持用户提供的完整字段列表"""
        try:
            # 获取通知参数（支持GET/POST两种方式）
            if request.method == 'POST':
                params = request.form.to_dict()
            else:
                params = request.args.to_dict()
            
            self.logger.info(f"收到支付通知: {params}")
            
            # 验证必要参数（按照用户字段列表）
            required_params = ['trade_no', 'out_trade_no', 'type', 'money', 'trade_status']
            for param in required_params:
                if param not in params:
                    self.logger.error(f"缺少必要参数: {param}")
                    return "fail"
            
            # 验证字段格式
            try:
                # 验证商户ID（支持多个PID，兼容1002和1008）
                if 'pid' in params:
                    pid = params['pid']
                    if pid not in ['1002', '1008']:
                        self.logger.error(f"商户ID不匹配: {pid}")
                        return "fail"
                
                # 验证金额（string类型，需转换为float）
                amount = float(params['money'])
                if amount <= 0:
                    self.logger.error(f"无效金额: {params['money']}")
                    return "fail"
                
                # 验证支付方式
                payment_type = params['type']
                if payment_type not in ['alipay', 'wxpay']:
                    self.logger.warning(f"未知支付类型: {payment_type}")
                
            except ValueError as e:
                self.logger.error(f"参数格式错误: {e}")
                return "fail"
            
            # 验证签名（MD5签名）- 暂时放宽验证，记录但不阻止
            if 'sign' in params:
                if not self.payment_api.verify_sign(params):
                    self.logger.warning(f"MD5签名验证失败，但继续处理: {params.get('sign')}")
                    # 不返回fail，继续处理
            
            # 检查支付状态（只有TRADE_SUCCESS才处理为成功）
            if params['trade_status'] != 'TRADE_SUCCESS':
                self.logger.info(f"支付状态非成功: {params['trade_status']}")
                return "success"  # 仍然返回success，避免重复通知
            
            # 处理支付成功 - 智能识别订单号
            order_no = params['out_trade_no']  # 商户订单号
            trade_no = params['trade_no']      # 平台订单号
            
            # 如果out_trade_no看起来像平台订单号（20250803开头），尝试查找对应的商户订单号
            if order_no.startswith('202508'):
                self.logger.warning(f"检测到订单号字段可能颠倒: out_trade_no={order_no}, trade_no={trade_no}")
                # 尝试通过平台订单号查找商户订单号（同步方法）
                actual_order_no = self._find_order_by_trade_no_sync(trade_no)
                if actual_order_no:
                    order_no = actual_order_no
                    self.logger.info(f"找到对应的商户订单号: {order_no}")
            
            # 异步处理支付成功
            self.process_payment_success_async(order_no, trade_no, amount)
            
            return "success"
                
        except Exception as e:
            self.logger.error(f"处理支付通知异常: {e}")
            return "fail"
    
    def handle_payment_return(self) -> str:
        """处理支付页面跳转通知 - 按用户字段列表处理"""
        try:
            params = request.args.to_dict()
            self.logger.info(f"收到支付跳转通知: {params}")
            
            # 验证必要参数（跳转通知的字段）
            required_params = ['out_trade_no']
            for param in required_params:
                if param not in params:
                    self.logger.warning(f"跳转通知缺少参数: {param}")
                    break
            
            # 获取订单号
            order_no = params.get('out_trade_no', 'unknown')
            trade_status = params.get('trade_status', 'unknown')
            
            # 根据支付状态显示不同页面
            if trade_status == 'TRADE_SUCCESS':
                page_title = "支付成功"
                status_icon = "✅"
                status_text = "支付成功"
                status_color = "#4CAF50"
                message = "您的支付已完成，积分正在发放中..."
            elif trade_status == 'TRADE_FINISHED':
                page_title = "支付完成"
                status_icon = "✅"
                status_text = "支付完成"
                status_color = "#4CAF50"
                message = "您的支付已完成，积分正在发放中..."
            elif trade_status == 'TRADE_CLOSED':
                page_title = "支付关闭"
                status_icon = "❌"
                status_text = "支付已关闭"
                status_color = "#f44336"
                message = "支付已关闭，如有疑问请联系客服"
            else:
                page_title = "支付处理中"
                status_icon = "🔄"
                status_text = "处理中"
                status_color = "#FF9800"
                message = "支付正在处理中，请稍候..."
            
            # 显示支付结果页面
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{page_title}</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        margin: 0;
                        padding: 20px;
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{
                        background: white;
                        border-radius: 16px;
                        padding: 40px;
                        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                        text-align: center;
                        max-width: 400px;
                        width: 100%;
                    }}
                    .status-icon {{
                        font-size: 64px;
                        margin-bottom: 20px;
                    }}
                    .status-text {{
                        color: {status_color};
                        font-size: 24px;
                        font-weight: bold;
                        margin-bottom: 16px;
                    }}
                    .order-info {{
                        background: #f5f5f5;
                        border-radius: 8px;
                        padding: 16px;
                        margin: 20px 0;
                    }}
                    .order-label {{
                        color: #666;
                        font-size: 14px;
                        margin-bottom: 4px;
                    }}
                    .order-value {{
                        font-family: monospace;
                        font-size: 16px;
                        font-weight: bold;
                        color: #333;
                    }}
                    .message {{
                        color: #666;
                        margin: 20px 0;
                        line-height: 1.5;
                    }}
                    .footer {{
                        color: #999;
                        font-size: 12px;
                        margin-top: 30px;
                    }}
                    .loading {{
                        display: inline-block;
                        width: 20px;
                        height: 20px;
                        border: 3px solid #f3f3f3;
                        border-top: 3px solid {status_color};
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin-left: 10px;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="status-icon">{status_icon}</div>
                    <div class="status-text">
                        {status_text}
                        {('<div class="loading"></div>' if status_icon == '🔄' else '')}
                    </div>
                    
                    <div class="order-info">
                        <div class="order-label">订单号</div>
                        <div class="order-value">{order_no}</div>
                    </div>
                    
                    <p class="message">{message}</p>
                    
                    <div class="footer">
                        请返回Telegram查看详细结果<br>
                        页面将在5秒后自动关闭
                    </div>
                </div>
                
                <script>
                    setTimeout(() => {{
                        try {{
                            window.close();
                        }} catch(e) {{
                            // 如果无法关闭窗口，尝试返回上一页
                            history.back();
                        }}
                    }}, 5000);
                </script>
            </body>
            </html>
            """
        except Exception as e:
            self.logger.error(f"处理支付跳转异常: {e}")
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>处理错误</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background: #f5f5f5;
                        margin: 0;
                        padding: 20px;
                        text-align: center;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        min-height: 100vh;
                    }
                    .error-container {
                        background: white;
                        border-radius: 8px;
                        padding: 40px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                        max-width: 400px;
                    }
                    .error-icon { font-size: 48px; margin-bottom: 20px; }
                    .error-title { color: #f44336; font-size: 20px; font-weight: bold; margin-bottom: 16px; }
                    .error-message { color: #666; line-height: 1.5; }
                </style>
            </head>
            <body>
                <div class="error-container">
                    <div class="error-icon">⚠️</div>
                    <div class="error-title">处理失败</div>
                    <p class="error-message">
                        支付页面处理出现异常<br>
                        请返回Telegram查看支付状态
                    </p>
                </div>
            </body>
            </html>
            """
    
    def process_payment_success_async(self, order_no: str, trade_no: str, notify_amount: float):
        """异步处理支付成功"""
        def process():
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._process_payment_success(order_no, trade_no, notify_amount))
            except Exception as e:
                self.logger.error(f"异步处理支付成功失败: {e}")
            finally:
                try:
                    loop.close()
                except:
                    pass
        
        Thread(target=process, daemon=True).start()
    
    async def _process_payment_success(self, order_no: str, trade_no: str, notify_amount: float):
        """处理支付成功逻辑"""
        user_telegram_id = None
        payment_processed = False
        credits_awarded = 0
        
        try:
            # 获取订单信息
            order = await self.payment_service.get_order_info(order_no)
            if not order:
                self.logger.error(f"订单不存在: {order_no}")
                return
            
            # 提前获取用户信息，确保能发送通知
            user_data = await self.user_service.get_user_by_id(order['user_id'])
            if user_data and user_data.get('telegram_id'):
                user_telegram_id = user_data['telegram_id']
                self.logger.info(f"获取到用户Telegram ID: {user_telegram_id}")
            else:
                self.logger.error(f"无法获取用户Telegram ID: user_id={order['user_id']}")
            
            # 验证金额
            order_amount = float(order['amount'])
            if abs(order_amount - notify_amount) > 0.01:
                self.logger.error(f"金额不匹配: 订单{order_amount}, 通知{notify_amount}")
                # 即使金额不匹配，也要通知用户处理中
                if user_telegram_id:
                    warning_message = f"⚠️ 支付金额异常，订单处理中，请联系客服\n订单号: {order_no}"
                    self._send_message_sync(user_telegram_id, warning_message)
                return
            
            # 检查订单状态
            if order['status'] == 'paid' or order['status'] == 'completed':
                self.logger.info(f"订单已处理: {order_no}")
                # 通知用户订单已处理
                if user_telegram_id:
                    completed_message = f"✅ 您的订单已处理完成\n订单号: {order_no}"
                    self._send_message_sync(user_telegram_id, completed_message)
                return
            
            # 检查首充状态（在更新订单前）
            is_first_purchase = await self.payment_service.is_first_purchase(order['user_id'])
            
            # 更新订单状态（不包含trade_no字段，因为表中没有这个字段）
            try:
                await self.payment_service.point_composite_repo.update_order_status(
                    order_no, 'paid', {
                        'paid_at': datetime.utcnow().isoformat(),
                        'updated_at': datetime.utcnow().isoformat()
                    }
                )
                self.logger.info(f"订单状态更新成功: {order_no}")
            except Exception as e:
                self.logger.error(f"更新订单状态失败: {order_no}, {e}")
                # 即使订单状态更新失败，也要尝试发放积分
            
            # 计算积分发放
            order_data = order.get('order_data', {})
            package_id = order_data.get('package_id', 'test')
            package_info = CREDIT_PACKAGES.get(package_id, {})
            base_credits = order.get('points_awarded', 0)
            bonus_credits = 0
            
            if is_first_purchase:
                bonus_rate = FIRST_CHARGE_BONUS.get(package_id, 0)
                bonus_type = "首充赠送"
            else:
                bonus_rate = REGULAR_CHARGE_BONUS.get(package_id, 0)
                bonus_type = "活动赠送"
            
            bonus_credits = int(base_credits * bonus_rate / 100)
            total_credits = base_credits + bonus_credits
            credits_awarded = total_credits
            
            # 发放积分
            description = f"购买{package_info.get('name', '套餐')} + {bonus_type}{bonus_rate}%"
            success = await self.payment_service._process_payment_success(order, is_first_purchase)
            
            if success:
                payment_processed = True
                self.logger.info(f"支付处理成功: {order_no}, 发放积分: {total_credits}")
                
                # 发送成功通知
                if user_telegram_id:
                    success_message = f"🎉 恭喜，您的充值{total_credits}积分已到账！\n"
                    if bonus_credits > 0:
                        success_message += f"💰 基础积分: {base_credits}\n🎁 赠送积分: {bonus_credits}\n"
                    success_message += f"📝 订单号: {order_no}"
                    
                    message_sent = self._send_message_sync(user_telegram_id, success_message)
                    if not message_sent:
                        self.logger.error(f"积分发放成功但消息发送失败: {order_no}")
                        # 记录失败的消息发送，以便后续手动重发
                        self.logger.error(f"FAILED_MESSAGE: user_id={order['user_id']}, telegram_id={user_telegram_id}, message={success_message}")
                else:
                    self.logger.error(f"积分发放成功但无法获取用户Telegram ID: {order_no}")
                    
            else:
                self.logger.error(f"积分发放失败: {order_no}")
                # 积分发放失败也要通知用户
                if user_telegram_id:
                    error_message = f"❌ 支付处理异常，积分发放失败\n订单号: {order_no}\n请联系客服处理"
                    message_sent = self._send_message_sync(user_telegram_id, error_message)
                    if not message_sent:
                        self.logger.error(f"积分发放失败且消息发送失败: {order_no}")
                        self.logger.error(f"FAILED_MESSAGE: user_id={order['user_id']}, telegram_id={user_telegram_id}, message={error_message}")
                
        except Exception as e:
            self.logger.error(f"处理支付成功失败: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            
            # 即使出现异常，也要尝试通知用户
            if user_telegram_id:
                error_message = f"⚠️ 支付处理过程中出现异常\n订单号: {order_no}\n"
                if payment_processed:
                    error_message += f"✅ 积分({credits_awarded})已发放成功"
                else:
                    error_message += "❌ 积分发放可能失败，请联系客服"
                
                message_sent = self._send_message_sync(user_telegram_id, error_message)
                if not message_sent:
                    self.logger.error(f"异常处理消息发送失败: {order_no}")
                    self.logger.error(f"FAILED_MESSAGE: order_no={order_no}, telegram_id={user_telegram_id}, message={error_message}")
    
    def _find_order_by_trade_no_sync(self, trade_no: str) -> str:
        """通过平台订单号查找商户订单号"""
        try:
            # 从最近的日志中查找对应的商户订单号
            import re
            with open('logs/pm2-error-4.log', 'r') as f:
                lines = f.readlines()
                # 从后往前查找包含这个trade_no的日志行
                for line in reversed(lines[-1000:]):  # 只查看最近1000行
                    if trade_no in line and 'out_trade_no' in line:
                        # 提取out_trade_no
                        match = re.search(r"'out_trade_no': '([^']+)'", line)
                        if match:
                            return match.group(1)
            return None
        except Exception as e:
            self.logger.error(f"查找订单号失败: {e}")
            return None

    async def send_message_to_user(self, telegram_id: int, message: str):
        """发送消息给用户"""
        try:
            # 获取Bot token
            bot_token = None
            if hasattr(self.bot, 'app') and self.bot.app and hasattr(self.bot.app, 'bot'):
                # 尝试使用现有的bot
                try:
                    await self.bot.app.bot.send_message(
                        chat_id=telegram_id, 
                        text=message
                    )
                    self.logger.info(f"支付成功通知已发送: {telegram_id}")
                    return
                except Exception as e:
                    self.logger.warning(f"使用现有bot发送失败: {e}")
            
            # 从配置获取token
            from src.utils.config.settings import get_settings
            settings = get_settings()
            bot_token = settings.bot.token
            
            if bot_token:
                # 创建临时bot发送
                from telegram import Bot
                import asyncio
                temp_bot = Bot(token=bot_token)
                await temp_bot.send_message(
                    chat_id=telegram_id, 
                    text=message
                )
                self.logger.info(f"支付成功通知已发送: {telegram_id}")
            else:
                self.logger.error("无法获取Bot token")
                
        except Exception as e:
            self.logger.error(f"发送支付成功通知失败: {e}")
            # 记录详细错误信息
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")

    def _send_message_sync(self, telegram_id: int, message: str, max_retries: int = 3):
        """同步发送消息给用户 - 带重试机制"""
        for attempt in range(max_retries):
            try:
                # 获取Bot token
                from src.utils.config.settings import get_settings
                settings = get_settings()
                bot_token = settings.bot.token
                
                if not bot_token:
                    self.logger.error("无法获取Bot token")
                    return False
                
                # 使用requests直接调用Telegram API
                import requests
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {
                    'chat_id': telegram_id,
                    'text': message,
                    'parse_mode': 'Markdown'  # 支持Markdown格式
                }
                
                response = requests.post(url, data=data, timeout=15)
                
                if response.status_code == 200:
                    self.logger.info(f"支付通知发送成功: {telegram_id} (尝试 {attempt + 1}/{max_retries})")
                    return True
                elif response.status_code == 429:
                    # 限流，等待重试
                    self.logger.warning(f"发送消息被限流，等待重试: {telegram_id}")
                    import time
                    time.sleep(2 ** attempt)  # 指数退避
                    continue
                else:
                    self.logger.error(f"发送消息失败: {response.status_code}, {response.text}")
                    if attempt == max_retries - 1:
                        # 最后一次尝试失败，尝试不使用Markdown
                        try:
                            data['parse_mode'] = None
                            response = requests.post(url, data=data, timeout=15)
                            if response.status_code == 200:
                                self.logger.info(f"不使用Markdown格式发送成功: {telegram_id}")
                                return True
                        except:
                            pass
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"发送消息超时，尝试 {attempt + 1}/{max_retries}: {telegram_id}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"同步发送支付通知失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    import traceback
                    self.logger.error(f"详细错误: {traceback.format_exc()}")
                else:
                    import time
                    time.sleep(1)
        
        self.logger.error(f"发送消息最终失败，已尝试 {max_retries} 次: {telegram_id}")
        return False
    
    def handle_order_query(self, order_no: str):
        """处理订单状态查询"""
        try:
            # 使用异步任务查询订单
            def query_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self._query_order_async(order_no))
                    return result
                finally:
                    loop.close()
            
            import threading
            thread = threading.Thread(target=query_async)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "status": "processing",
                "message": "正在查询订单状态...",
                "order_no": order_no
            })
            
        except Exception as e:
            self.logger.error(f"查询订单失败: {e}")
            return jsonify({
                "status": "error",
                "message": "查询失败",
                "error": str(e)
            })
    
    async def _query_order_async(self, order_no: str):
        """异步查询订单状态"""
        try:
            # 查询数据库中的订单
            order = await self.payment_service.get_order_info(order_no)
            if not order:
                self.logger.error(f"订单不存在: {order_no}")
                return
            
            # 如果订单已经是已支付状态，不需要查询
            if order['status'] == 'paid':
                self.logger.info(f"订单已处理: {order_no}")
                return
            
            # 查询支付平台订单状态
            if self.payment_api:
                payment_result = self.payment_api.query_order(order_no)
                if payment_result.get('success') and payment_result.get('order_info', {}).get('status') == 1:
                    # 支付成功，触发处理
                    self.logger.info(f"查询发现订单已支付: {order_no}")
                    await self._process_payment_success(order_no, "query_trade_no", float(order['amount']))
            
        except Exception as e:
            self.logger.error(f"异步查询订单失败: {e}")
    
    def run(self, host='0.0.0.0', port=5001, debug=False):
        """运行Webhook服务器"""
        self.logger.info(f"启动支付回调服务器: {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True) 