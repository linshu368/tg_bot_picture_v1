"""
图像处理模块
处理图像生成确认和API调用逻辑
"""

import logging
import io
import time
from typing import Dict, Any

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..user_state_manager import UserStateManager, UserStateHelper, States, DataKeys
from src.utils.config.app_config import (
    COST_QUICK_UNDRESS, COST_CUSTOM_UNDRESS, QUICK_UNDRESS_DEFAULTS
)
from src.utils.performance_monitor import get_performance_monitor


class ImageProcessingHandler:
    """图像处理处理器"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.logger = logging.getLogger(__name__)
        self.state_manager: UserStateManager = bot_instance.state_manager
        self.state_helper: UserStateHelper = bot_instance.state_helper
        
        # 服务依赖
        self.user_service = bot_instance.user_service
        self.image_service = bot_instance.image_service
        self.clothoff_api = bot_instance.clothoff_api
    
    async def process_quick_undress_confirmation(self, query, context):
        """处理确认快速脱衣"""
        user_id = query.from_user.id
        monitor = get_performance_monitor()
        
        # 开始快速去衣确认处理计时
        operation_id = f"quick_undress_confirm_{user_id}_{int(time.time())}"
        monitor.start_timer(operation_id, f"用户 {user_id} 确认快速去衣")
        
        try:
            # 获取用户信息
            monitor.checkpoint(operation_id, "get_user", "开始获取用户信息")
            user_data = await self.user_service.get_user_by_telegram_id(user_id)
            if not user_data:
                monitor.end_timer(operation_id, "用户不存在，快速结束")
                await query.edit_message_text("❌ 用户不存在")
                return
            
            # 检查积分
            monitor.checkpoint(operation_id, "check_points", "开始检查积分")
            points_balance = await self.user_service.get_user_points_balance(user_data['id'])
            if points_balance < COST_QUICK_UNDRESS:
                monitor.end_timer(operation_id, "积分不足，快速结束")
                await query.edit_message_text(f"❌ 积分不足！需要{COST_QUICK_UNDRESS}积分")
                return
            
            # 获取图片文件ID
            monitor.checkpoint(operation_id, "get_photo_id", "获取图片文件ID")
            photo_file_id = self.state_manager.get_user_data(user_id, DataKeys.PHOTO_FILE_ID)
            if not photo_file_id:
                monitor.end_timer(operation_id, "图片信息丢失，快速结束")
                await query.edit_message_text("❌ 图片信息丢失，请重新上传")
                return
            
            # 先扣除积分
            monitor.checkpoint(operation_id, "consume_points", "开始扣除积分")
            success = await self.user_service.consume_points(user_data['id'], COST_QUICK_UNDRESS, "快速脱衣")
            if not success:
                monitor.end_timer(operation_id, "积分扣除失败，快速结束")
                await query.edit_message_text("❌ 积分扣除失败，请重试")
                return
            
            # 开始处理
            monitor.checkpoint(operation_id, "show_processing", "显示处理中消息")
            await query.edit_message_text("⏳ **正在处理中...**\n\n预计需要1-3分钟，请稍候")
            
            try:
                # 获取图片数据
                monitor.checkpoint(operation_id, "download_image", "开始下载图片")
                file = await context.bot.get_file(photo_file_id)
                image_data = await file.download_as_bytearray()
                
                # 准备图片文件
                monitor.checkpoint(operation_id, "prepare_image", "准备图片文件")
                image_file = io.BytesIO(image_data)
                
                # 调用ClothOff API（使用旧版本的同步调用方式）
                monitor.checkpoint(operation_id, "call_api", "开始调用ClothOff API")
                result = self.clothoff_api.generate_image(
                    image_file=image_file,
                    filename="input.jpg",
                    body_type=QUICK_UNDRESS_DEFAULTS.get("body_type", "normal"),
                    breast_size=QUICK_UNDRESS_DEFAULTS.get("breast_size", "normal"),
                    butt_size=QUICK_UNDRESS_DEFAULTS.get("butt_size", "normal"),
                    cloth=QUICK_UNDRESS_DEFAULTS.get("cloth", "naked"),
                    age=str(QUICK_UNDRESS_DEFAULTS.get("age", 25))
                )
                
                monitor.checkpoint(operation_id, "api_response", f"API调用完成，结果: {result.get('success', False)}")
                
                if result["success"]:
                    # 创建图像生成参数用于数据库存储
                    monitor.checkpoint(operation_id, "create_params", "创建图像生成参数")
                    from src.domain.services.image_service import ImageGenerationParams
                    params = ImageGenerationParams(
                        cloth=QUICK_UNDRESS_DEFAULTS.get("cloth", "naked"),
                        body_type=QUICK_UNDRESS_DEFAULTS.get("body_type", "normal"),
                        breast_size=QUICK_UNDRESS_DEFAULTS.get("breast_size", "normal"),
                        butt_size=QUICK_UNDRESS_DEFAULTS.get("butt_size", "normal"),
                        age=QUICK_UNDRESS_DEFAULTS.get("age", 25)
                    )
                    
                    # 在数据库中创建任务记录
                    monitor.checkpoint(operation_id, "create_task", "在数据库中创建任务记录")
                    task_result = await self.image_service.create_image_task(
                        user_id=user_data['id'],
                        params=params,                                                     
                        credits_cost=COST_QUICK_UNDRESS
                    )
                    
                    if task_result['success']:
                        # 更新任务ID
                        monitor.checkpoint(operation_id, "update_task_id", "更新任务ID")
                        await self.image_service.image_task_repo.update_task_id(
                            task_result['task_id'], result['task_id']
                        )
                        
                        # 更新任务状态为处理中
                        monitor.checkpoint(operation_id, "start_processing", "更新任务状态为处理中")
                        await self.image_service.start_processing(result['task_id'])
                    
                    # 清除用户状态
                    monitor.checkpoint(operation_id, "clear_state", "清除用户状态")
                    self.state_helper.clear_user_flow(user_id)
                    
                    # 显示成功消息
                    monitor.checkpoint(operation_id, "show_success", "显示成功消息")
                    message = "👕 **快速脱衣任务已提交**\n\n"
                    message += f"📋 任务ID: `{result['task_id']}`\n"
                    message += f"📊 队列位置: {result.get('queue_num', 'N/A')}\n"
                    message += f"💰 消耗积分: {COST_QUICK_UNDRESS}\n\n"
                    message += "⏰ 预计等待时间: 1-5分钟\n"
                    message += "🔔 完成后将自动发送结果"
                    
                    await query.edit_message_text(message, parse_mode='Markdown')
                else:
                    # 生成失败，退还积分
                    monitor.checkpoint(operation_id, "refund_points", "生成失败，退还积分")
                    await self.user_service.add_points(user_data['id'], COST_QUICK_UNDRESS, "退款", "快速脱衣生成失败")
                    await query.edit_message_text(f"❌ 快速脱衣失败\n\n{result.get('error', '未知错误')}\n\n积分已退还")
                
                monitor.end_timer(operation_id, "快速去衣确认处理完成")
                
            except Exception as api_error:
                # 异常处理，退还积分
                monitor.checkpoint(operation_id, "api_exception", f"API调用异常: {str(api_error)}")
                await self.user_service.add_points(user_data['id'], COST_QUICK_UNDRESS, "退款", "快速脱衣生成异常")
                self.logger.error(f"调用图像处理API失败: {api_error}")
                await query.edit_message_text(f"❌ 快速脱衣异常\n\n{str(api_error)}\n\n积分已退还")
                monitor.end_timer(operation_id, "快速去衣确认处理异常")
            
        except Exception as e:
            monitor.end_timer(operation_id, f"快速去衣确认处理失败: {str(e)}")
            self.logger.error(f"处理确认快速脱衣失败: {e}")
            await query.edit_message_text("❌ 处理失败，请稍后重试")

    async def process_custom_undress_confirmation(self, query, context):
        """处理确认自定义脱衣"""
        user_id = query.from_user.id
        
        try:
            user_data = await self.user_service.get_user_by_telegram_id(user_id)
            if not user_data:
                await query.edit_message_text("❌ 用户不存在")
                return
            
            # 检查积分
            points_balance = await self.user_service.get_user_points_balance(user_data['id'])
            if points_balance < COST_CUSTOM_UNDRESS:
                await query.edit_message_text(f"❌ 积分不足！需要{COST_CUSTOM_UNDRESS}积分")
                return
            
            # 获取图片文件ID
            photo_file_id = self.state_manager.get_user_data(user_id, DataKeys.PHOTO_FILE_ID)
            if not photo_file_id:
                await query.edit_message_text("❌ 图片信息丢失，请重新上传")
                return
            
            # 获取用户自定义参数
            user_preferences = {}
            
            # 从各个数据键中收集用户偏好
            cloth_selection = self.state_manager.get_user_data(user_id, DataKeys.SELECTED_CLOTH)
            if cloth_selection:
                user_preferences['cloth'] = cloth_selection
            
            pose_selection = self.state_manager.get_user_data(user_id, DataKeys.SELECTED_POSE)
            if pose_selection and isinstance(pose_selection, dict):
                user_preferences['pose'] = pose_selection.get('name', '')
            
            # 获取偏好设置
            body_type = self.state_manager.get_user_data(user_id, DataKeys.BODY_TYPE)
            if body_type:
                user_preferences['body_type'] = body_type
                
            breast_size = self.state_manager.get_user_data(user_id, DataKeys.BREAST_SIZE)
            if breast_size:
                user_preferences['breast_size'] = breast_size
                
            butt_size = self.state_manager.get_user_data(user_id, DataKeys.BUTT_SIZE)
            if butt_size:
                user_preferences['butt_size'] = butt_size
                
            age = self.state_manager.get_user_data(user_id, DataKeys.AGE)
            if age:
                user_preferences['age'] = age
            
            # 如果没有任何自定义参数，使用默认参数
            if not user_preferences:
                from src.utils.config.app_config import QUICK_UNDRESS_DEFAULTS
                user_preferences = QUICK_UNDRESS_DEFAULTS.copy()
                self.logger.info(f"用户 {user_id} 没有自定义参数，使用默认参数")
            else:
                self.logger.info(f"用户 {user_id} 自定义参数: {user_preferences}")
            
            # 先扣除积分
            success = await self.user_service.consume_points(user_data['id'], COST_CUSTOM_UNDRESS, "自定义脱衣")
            if not success:
                await query.edit_message_text("❌ 积分扣除失败，请重试")
                return
            
            # 开始处理
            await query.edit_message_text("⏳ **正在处理中...**\n\n预计需要1-3分钟，请稍候")
            
            try:
                # 获取图片数据
                file = await context.bot.get_file(photo_file_id)
                image_data = await file.download_as_bytearray()
                
                # 准备图片文件
                image_file = io.BytesIO(image_data)
                
                # 准备API参数
                api_params = {
                    "image_file": image_file,
                    "filename": "input.jpg",
                    "body_type": user_preferences.get("body_type", "normal"),
                    "breast_size": user_preferences.get("breast_size", "normal"),
                    "butt_size": user_preferences.get("butt_size", "normal"),
                    "cloth": user_preferences.get("cloth", "naked"),
                    "age": str(user_preferences.get("age", 25))
                }
                
                # 如果有姿势参数，添加进去
                if "pose" in user_preferences:
                    api_params["pose"] = user_preferences["pose"]
                
                # 调用ClothOff API
                result = self.clothoff_api.generate_image(**api_params)
                
                if result["success"]:
                    # 创建图像生成参数用于数据库存储
                    from src.domain.services.image_service import ImageGenerationParams
                    params = ImageGenerationParams(
                        cloth=user_preferences.get("cloth", "naked"),
                        body_type=user_preferences.get("body_type", "normal"),
                        breast_size=user_preferences.get("breast_size", "normal"),
                        butt_size=user_preferences.get("butt_size", "normal"),
                        age=user_preferences.get("age", 25),
                        pose=user_preferences.get("pose", None)
                    )
                    
                    # 在数据库中创建任务记录
                    task_result = await self.image_service.create_image_task(
                        user_id=user_data['id'],
                        params=params,
                        credits_cost=COST_CUSTOM_UNDRESS
                    )
                    
                    if task_result['success']:
                        # 更新任务ID
                        await self.image_service.image_task_repo.update_task_id(
                            task_result['task_id'], result['task_id']
                        )
                        
                        # 更新任务状态为处理中
                        await self.image_service.start_processing(result['task_id'])
                    
                    # 清除用户状态
                    self.state_helper.clear_user_flow(user_id)
                    
                    # 显示成功消息
                    message = "🎨 **自定义脱衣任务已提交**\n\n"
                    message += f"📋 任务ID: `{result['task_id']}`\n"
                    message += f"📊 队列位置: {result.get('queue_num', 'N/A')}\n"
                    message += f"💰 消耗积分: {COST_CUSTOM_UNDRESS}\n\n"
                    message += "🎯 您的设置：\n"
                    message += f"👔 衣服：{user_preferences.get('cloth', 'naked')}\n"
                    if "pose" in user_preferences:
                        message += f"🤸 姿势：{user_preferences['pose']}\n"
                    message += f"🏃 体型：{user_preferences.get('body_type', 'normal')}\n"
                    message += f"👤 胸部：{user_preferences.get('breast_size', 'normal')}\n"
                    message += f"🍑 臀部：{user_preferences.get('butt_size', 'normal')}\n"
                    message += f"👶 年龄：{user_preferences.get('age', 25)}\n\n"
                    message += "⏰ 预计等待时间: 1-5分钟\n"
                    message += "🔔 完成后将自动发送结果"
                    
                    await query.edit_message_text(message, parse_mode='Markdown')
                else:
                    # 生成失败，退还积分
                    await self.user_service.add_points(user_data['id'], COST_CUSTOM_UNDRESS, "退款", "自定义脱衣生成失败")
                    await query.edit_message_text(f"❌ 自定义脱衣失败\n\n{result.get('error', '未知错误')}\n\n积分已退还")
                
            except Exception as api_error:
                # 异常处理，退还积分
                await self.user_service.add_points(user_data['id'], COST_CUSTOM_UNDRESS, "退款", "自定义脱衣生成异常")
                self.logger.error(f"调用图像处理API失败: {api_error}")
                await query.edit_message_text(f"❌ 自定义脱衣异常\n\n{str(api_error)}\n\n积分已退还")
            
        except Exception as e:
            self.logger.error(f"处理确认自定义脱衣失败: {e}")
            await query.edit_message_text("❌ 处理失败，请稍后重试") 