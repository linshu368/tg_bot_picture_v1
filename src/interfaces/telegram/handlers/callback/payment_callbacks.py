"""
支付回调处理器
处理购买积分、订单查询等支付相关回调
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from datetime import datetime

from .base_callback_handler import BaseCallbackHandler, robust_callback_handler


class PaymentCallbackHandler(BaseCallbackHandler):
    """支付回调处理器"""
    
    def get_callback_handlers(self):
        """返回支付回调处理方法映射"""
        return {
            "buy_credits": self.handle_buy_credits_callback,
            "select_package": self.handle_package_selection,
            "buy_package": self.handle_package_purchase,
            "check_order": self.handle_check_order_callback,
            "cancel_order": self.handle_cancel_order_callback,
            "back_to_buy": self.handle_back_to_buy,
            "cancel_buy": self.handle_cancel_buy,
        }
    
    def _generate_credit_purchase_message(self, is_first_purchase: bool, payment_method: str = None) -> str:
        """生成统一的充值文案"""
        method_prefix = f" - {payment_method}" if payment_method else ""
        
        if is_first_purchase:
            return f"""👏 首次充值，充得越多，送得越狠！{method_prefix}

🔥 等级提升档位一览 👇（首充专属福利，自动发放）

🧪【测试充值】 1积分 → ¥1（无首充赠送）
🥉【普通青铜】 40积分 → ¥18（首充赠送 +100%）
🥈【VIP白银】 105积分 → ¥36（首充赠送 +50%）
🥇【VIP黄金】 360积分 → ¥75（首充赠送 +80%）
💎【VIP钻石】 900积分 → ¥155（首充赠送 +80%）
🏆【VIP铂金】 3000积分 → ¥388（首充赠送 +100%）
👑【VIP王者】 7000积分 → ¥778（首充赠送 +100%）

📸 首次充值【VIP铂金】平均仅 ¥0.13 / 张
📸 首次充值【VIP王者】更低至 ¥0.11 / 张！

📌 充值后立即到账，等级&积分**永久有效**
🎁 首充奖励无须手动领取，系统自动发放！

🔒 所有账户信息与充值记录，都会与你的【身份码】绑定保存。
**无论何时何地，凭码即可找回，安全无忧** ✅

请选择充值套餐："""
        else:
            return f"""🔁 限时加赠积分 · 回馈老用户{method_prefix}

不管你之前充过多少，现在继续充，还有福利！

💳 档位加赠如下（今日限时生效）：

🧪【测试充值】 1积分 → ¥1（无赠送）
🥉【普通青铜】 20积分 → ¥15（无赠送）
🥈【VIP白银】 77积分 → ¥36（额外赠送 +10%）
🥇【VIP黄金】 230积分 → ¥75（额外赠送 +15%）
💎【VIP钻石】 600积分 → ¥155（额外赠送 +20%）
🏆【VIP铂金】 1875积分 → ¥388（额外赠送 +25%）
👑【VIP王者】 4550积分 → ¥778（额外赠送 +30%）

💡 每次充值都更划算，越充越省

⏳ 本轮充值加赠为限时活动，随时可能下架！

👉🏻 立即充值，享受更多实惠 🔥

🔒 所有账户信息与充值记录，都会与你的【身份码】绑定保存。
**无论何时何地，凭码即可找回，安全无忧** ✅

请选择充值套餐："""

    def _create_package_selection_keyboard(self, return_callback: str = "back_to_profile"):
        """创建统一的套餐选择键盘"""
        from src.utils.config.app_config import CREDIT_PACKAGES
        keyboard = []
        for package_id, package_info in CREDIT_PACKAGES.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{package_info['name']} - ¥{package_info['price']}",
                    callback_data=f"select_package_{package_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 返回个人中心", callback_data=return_callback)
        ])
        return InlineKeyboardMarkup(keyboard)
    
    @robust_callback_handler
    async def handle_buy_credits_callback(self, query, context):
        """处理购买积分回调 - 显示套餐列表"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在，请先使用 /start")
            return
        
        # 检查是否首次充值
        is_first_purchase = await self.payment_service.is_first_purchase(user_data['id'])
        
        # 使用统一的详细文案生成函数
        message = self._generate_credit_purchase_message(is_first_purchase)
        
        # 创建套餐选择按钮
        from src.utils.config.app_config import CREDIT_PACKAGES
        keyboard = []
        for package_id, package_info in CREDIT_PACKAGES.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{package_info['name']} - ¥{package_info['price']}",
                    callback_data=f"select_package_{package_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 返回个人中心", callback_data="back_to_profile")])
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_package_selection(self, query, context, package_id: str):
        """处理套餐选择回调 - 显示支付方式选择"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在")
            return
        
        from src.utils.config.app_config import CREDIT_PACKAGES
        
        if package_id not in CREDIT_PACKAGES:
            await self._safe_edit_message(query, "❌ 无效的套餐选择")
            return
        
        package_info = CREDIT_PACKAGES[package_id]
        
        message = f"📦 **已选择套餐：{package_info['name']}**\n\n"
        message += f"💰 价格：¥{package_info['price']}\n"
        message += f"💎 积分：{package_info['credits']}\n\n"
        message += "请选择支付方式："
        
        # 创建支付方式选择按钮，callback_data包含套餐ID
        from src.utils.config.app_config import PAYMENT_METHODS
        keyboard = []
        for method_id, method_name in PAYMENT_METHODS.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"💳 {method_name}",
                    callback_data=f"buy_package_{method_id}_{package_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 返回套餐选择", callback_data="buy_credits")])
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_package_purchase(self, query, context, method_id: str, package_id: str):
        """处理套餐购买回调 - 创建订单和支付链接"""
        user_id = query.from_user.id
        
        user_data = await self._safe_get_user(user_id)
        if not user_data:
            await self._safe_edit_message(query, "❌ 用户不存在")
            return
        
        from src.utils.config.app_config import PAYMENT_METHODS, CREDIT_PACKAGES
        
        if method_id not in PAYMENT_METHODS or package_id not in CREDIT_PACKAGES:
            await self._safe_edit_message(query, "❌ 无效的支付方式或套餐")
            return
        
        # 创建支付订单
        try:
            result = await self.payment_service.create_payment_order(
                user_id=user_data['id'],
                package_id=package_id,
                payment_method=method_id
            )
            
            if result['success']:
                method_name = PAYMENT_METHODS[method_id]
                package_info = CREDIT_PACKAGES[package_id]
                payment_info = result.get('payment_info', {})
                
                # 添加调试日志
                self.logger.info(f"支付信息调试 - 方式: {method_name}, 返回数据: {payment_info}")
                
                # 构建支付信息消息
                message = f"💳 **支付信息**\n\n"
                message += f"📦 套餐：{package_info['name']}\n"
                message += f"💰 金额：¥{package_info['price']}\n"
                message += f"💳 支付方式：{method_name}\n"
                message += f"🆔 订单号：`{result['order_id']}`\n"
                message += f"⏰ 订单有效期：30分钟\n\n"
                
                # 创建按钮
                keyboard = []
                
                # 根据支付信息创建相应的支付按钮
                if payment_info.get("payurl"):
                    # 有支付跳转链接
                    keyboard.append([
                        InlineKeyboardButton("💳 前往支付", url=payment_info["payurl"])
                    ])
                    message += "点击下方按钮前往支付页面"
                elif payment_info.get("qrcode"):
                    # 有二维码链接
                    keyboard.append([
                        InlineKeyboardButton("📱 打开支付应用", url=payment_info["qrcode"])
                    ])
                    message += f"请使用{method_name}扫描二维码支付：\n`{payment_info['qrcode']}`"
                elif payment_info.get("urlscheme"):
                    # 有小程序跳转链接
                    keyboard.append([
                        InlineKeyboardButton("📱 打开小程序", url=payment_info["urlscheme"])
                    ])
                    message += "点击下方按钮打开小程序支付"
                else:
                    # 没有支付链接，显示开发中信息
                    message += "💡 支付功能开发中，请联系客服完成充值"
                
                # 添加查询订单状态按钮
                keyboard.append([
                    InlineKeyboardButton("🔍 查询订单状态", callback_data=f"check_order_{result['order_id']}")
                ])
                
                # 添加取消订单按钮
                keyboard.append([
                    InlineKeyboardButton("❌ 取消订单", callback_data=f"cancel_order_{result['order_id']}")
                ])
                
                # 添加返回按钮
                keyboard.append([
                    InlineKeyboardButton("🔙 返回充值", callback_data="buy_credits")
                ])
                
                await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
                
                # 发送订单创建成功的提示
                await query.answer("订单创建成功！请在30分钟内完成支付")
                
            else:
                await self._safe_edit_message(query, f"❌ 订单创建失败：{result.get('error', '未知错误')}")
                
        except Exception as e:
            self.logger.error(f"创建支付订单失败: {e}")
            await self._safe_edit_message(query, "❌ 系统错误，请稍后重试")
    
    @robust_callback_handler
    async def handle_check_order_callback(self, query, context, order_no: str):
        """处理查询订单状态回调"""
        try:
            # 获取订单信息
            order = await self.payment_service.payment_order_repo.get_by_order_id(order_no)
            if not order:
                await query.answer("订单不存在")
                return

            # 如果订单已经是完成状态，直接显示完成信息
            if order['status'] == "completed":
                await query.answer("订单已完成，积分已到账")
                
                # 更新消息显示完成状态
                user = await self.user_service.get_user_by_id(order['user_id'])
                from src.utils.config.app_config import CREDIT_PACKAGES
                # 从 order_data JSON 字段中获取 package_id
                order_data = order.get('order_data', {})
                package_id = order_data.get('package_id', 'test')
                package_info = CREDIT_PACKAGES.get(package_id, {})

                message = "✅ **订单已完成**\n\n"
                message += f"📦 商品：{package_info.get('name', '未知')}\n"
                message += f"💰 金额：¥{order['amount']}\n"
                message += f"🎁 积分：+{order['points_awarded']}\n"
                message += f"📋 订单号：`{order_no}`\n\n"
                
                if user:
                    points_balance = await self.user_service.get_user_points_balance(user['id'])
                    message += f"💎 当前积分：{points_balance}\n"
                
                message += "感谢您的支持！"

                await self._safe_edit_message(query, message)
                return

            # 查询支付平台订单状态
            if self.payment_service.payment_api:
                payment_result = self.payment_service.payment_api.query_order(out_trade_no=order_no)
            else:
                # 如果没有支付API，模拟查询结果
                payment_result = {
                    "success": True,
                    "order_info": {
                        "status": 1,  # 假设支付成功
                        "trade_no": f"test_trade_{order_no}"
                    }
                }

            if payment_result["success"]:
                order_info = payment_result["order_info"]
                platform_status = order_info.get("status", 0)

                if platform_status == 1:  # 支付成功
                    # 处理支付成功 - 只在订单状态不是paid或completed时处理
                    if order['status'] not in ["paid", "completed"]:
                        success = await self._process_payment_success_like_original(
                            order_no, order_info.get("trade_no", ""), order
                        )
                        
                        if not success:
                            await query.answer("处理支付失败，请联系客服")
                            return

                    await query.answer("支付成功！积分已到账")

                    # 更新消息显示 - 照抄原始项目格式
                    user = await self.user_service.get_user_by_id(order['user_id'])
                    from src.utils.config.app_config import CREDIT_PACKAGES
                    # 从 order_data JSON 字段中获取 package_id
                    order_data = order.get('order_data', {})
                    package_id = order_data.get('package_id', 'test')
                    package_info = CREDIT_PACKAGES.get(package_id, {})

                    message = "✅ **支付成功**\n\n"
                    message += f"📦 商品：{package_info.get('name', '未知')}\n"
                    message += f"💰 金额：¥{order['amount']}\n"
                    message += f"🎁 积分：+{order['points_awarded']}\n"
                    message += f"📋 订单号：`{order_no}`\n\n"
                    
                    if user:
                        points_balance = await self.user_service.get_user_points_balance(user['id'])
                        message += f"💎 当前积分：{points_balance}\n"
                    
                    message += "感谢您的支持！"

                    await self._safe_edit_message(query, message)
                else:
                    await query.answer("订单还未支付，请完成支付")
            else:
                await query.answer("查询订单状态失败")
                
        except Exception as e:
            self.logger.error(f"查询订单状态失败: {e}")
            await query.answer("查询失败，请稍后重试")

    async def _process_payment_success_like_original(self, order_no: str, trade_no: str, order):
        """照抄原始项目的process_payment_success逻辑"""
        try:
            # 更新订单状态为已支付（中间状态）
            await self.payment_service.payment_order_repo.update_by_order_id(
                order_no, {
                    'status': 'paid',
                    'paid_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }
            )

            # 获取积分包信息
            from src.utils.config.app_config import CREDIT_PACKAGES, FIRST_CHARGE_BONUS, REGULAR_CHARGE_BONUS
            # 从 order_data JSON 字段中获取 package_id
            order_data = order.get('order_data', {})
            package_id = order_data.get('package_id', 'test')
            package_info = CREDIT_PACKAGES.get(package_id)
            if not package_info:
                self.logger.error(f"无效的积分包类型: {package_id}")
                return False

            # 检查用户首冲状态
            user_id = order['user_id']
            is_first_add = await self.payment_service.is_first_purchase(user_id)

            # 计算应发放的积分 - 照抄原始逻辑
            base_credits = order['points_awarded']
            bonus_credits = 0

            if is_first_add:
                # 首冲赠送
                bonus_rate = FIRST_CHARGE_BONUS.get(package_id, 0)
                bonus_credits = int(base_credits * bonus_rate / 100)
                description = f"购买{package_info['name']} + 首冲赠送{bonus_rate}%"
            else:
                # 非首冲活动赠送
                bonus_rate = REGULAR_CHARGE_BONUS.get(package_id, 0)
                bonus_credits = int(base_credits * bonus_rate / 100)
                description = f"购买{package_info['name']} + 活动赠送{bonus_rate}%"

            total_credits = base_credits + bonus_credits

            # 发放积分
            success = await self.user_service.add_points(user_id, total_credits, "充值", description)

            if success:
                # 积分发放成功后，更新订单状态为已完成
                await self.payment_service.payment_order_repo.update_by_order_id(
                    order_no, {
                        'status': 'completed',
                        'updated_at': datetime.utcnow().isoformat()
                    }
                )
                
                self.logger.info(
                    f"积分发放成功并完成订单: 用户{user_id} +{total_credits}积分 (基础{base_credits} + 赠送{bonus_credits}) 订单{order_no}"
                )
                return True
            else:
                self.logger.error(f"积分发放失败: {order_no}")
                return False

        except Exception as e:
            self.logger.error(f"处理支付成功失败: {e}")
            return False
    
    @robust_callback_handler  
    async def handle_cancel_order_callback(self, query, context, order_no: str):
        """处理取消订单回调"""
        message = "❌ **订单取消**\n\n"
        message += f"📋 订单号：`{order_no}`\n\n"
        message += "如需帮助，请联系客服"
        
        keyboard = [
            [InlineKeyboardButton("🔙 返回充值", callback_data="buy_credits")],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="back_to_main")]
        ]
        
        await self._safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
    
    @robust_callback_handler
    async def handle_back_to_buy(self, query, context):
        """返回充值页面"""
        await self.handle_buy_credits_callback(query, context)
    
    @robust_callback_handler
    async def handle_cancel_buy(self, query, context):
        """取消购买"""
        await self._safe_edit_message(query, "❌ 已取消购买") 