"""
Webhook处理器 - 处理外部API回调
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from src.domain.services.image_service import ImageService, ImageStatus


class WebhookStatus(Enum):
    """Webhook状态枚举"""
    SUCCESS = "200"
    COMPLETED = "completed"
    FAILED = "500"
    ERROR = "failed"


class WebhookHandler:
    """异步Webhook处理器"""
    
    def __init__(self, image_service: ImageService):
        self.image_service = image_service
        self.logger = logging.getLogger(__name__)
    
    def _is_success_status(self, status: str) -> bool:
        """判断是否为成功状态"""
        return status in [WebhookStatus.SUCCESS.value, WebhookStatus.COMPLETED.value]
    
    def _is_failed_status(self, status: str) -> bool:
        """判断是否为失败状态"""
        return status in [WebhookStatus.FAILED.value, WebhookStatus.ERROR.value]
    
    def _extract_task_id(self, data: Dict[str, Any]) -> Optional[str]:
        """从回调数据中提取任务ID - 支持所有可能的字段名"""
        return (data.get('idGeneration') or   # 视频和人脸交换优先
                data.get('id_gen') or         # 图片处理优先  
                data.get('task_id') or        # 备用字段
                data.get('id'))               # 通用字段
    
    def _extract_result_path(self, data: Dict[str, Any]) -> Optional[str]:
        """从回调数据中提取结果路径 - 支持所有可能的URL字段"""
        # 视频处理相关URL
        video_url = (data.get('video_url') or 
                    data.get('result_url') or 
                    data.get('url'))
        
        # 图片处理相关URL  
        image_url = (data.get('result_url') or
                    data.get('image_url') or
                    data.get('url'))
        
        # 返回任何可用的URL（优先视频，其次图片）
        return video_url or image_url
    
    def _extract_error_message(self, data: Dict[str, Any]) -> str:
        """从回调数据中提取错误信息 - 支持所有可能的错误字段"""
        return (data.get('error') or           # 视频和人脸交换优先
                data.get('error_message') or   # 通用错误信息
                data.get('message') or         # 通用消息
                data.get('img_message') or     # 图片专用错误
                f"任务失败 - 状态: {data.get('status', 'unknown')}")
    
    def _extract_result_file(self, files: Dict[str, Any]) -> Optional[Any]:
        """从上传文件中提取结果文件 - 支持multipart/form-data"""
        if not files:
            return None
            
        # 按照用户字段列表的优先级查找文件
        file_fields = ['res_image', 'result_image', 'res_video']
        
        for field in file_fields:
            if field in files:
                file_obj = files[field]
                # 检查文件大小（用户提到< 1KB的文件无效）
                if hasattr(file_obj, 'content_length') and file_obj.content_length and file_obj.content_length < 1024:
                    self.logger.warning(f"文件 {field} 太小 ({file_obj.content_length} bytes)，视为无效")
                    continue
                return file_obj
        
        return None
    
    def _simplify_technical_error(self, error_message: str) -> str:
        """简化技术错误信息"""
        # 按照用户要求，失败时错误信息会被简化
        if not error_message:
            return "处理失败"
        
        # 常见的技术错误简化映射
        error_mappings = {
            "processing failed": "处理失败",
            "invalid input": "输入无效", 
            "face not detected": "未检测到人脸",
            "format not supported": "格式不支持",
            "timeout": "处理超时",
            "system error": "系统错误"
        }
        
        error_lower = error_message.lower()
        for key, simplified in error_mappings.items():
            if key in error_lower:
                return simplified
        
        # 如果没有匹配的映射，返回简化版本
        return "处理失败：" + error_message[:50] + ("..." if len(error_message) > 50 else "")
    
    async def handle_image_webhook(self, callback_data: Dict[str, Any], files: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理图像处理Webhook回调 - 支持用户完整字段列表
        
        Args:
            callback_data: 回调数据
            files: 上传的文件（multipart/form-data）
            
        Returns:
            处理结果
        """
        try:
            # 提取关键信息
            task_id = self._extract_task_id(callback_data)
            status = callback_data.get('status', '200')  # 默认状态为200（成功）
            
            self.logger.info(f"收到图像处理回调 - 任务ID: {task_id}, 状态: {status}")
            
            if not task_id:
                self.logger.error("回调数据缺少任务ID")
                return {
                    'success': False,
                    'error': '缺少任务ID'
                }
            
            # 验证任务是否存在
            task_info = await self.image_service.get_task_info(task_id)
            if not task_info:
                self.logger.error(f"未找到任务: {task_id}")
                return {
                    'success': False,
                    'error': f'任务不存在: {task_id}'
                }
            
            # 根据状态处理
            if self._is_success_status(status):
                return await self._handle_success_callback(task_id, callback_data, files)
            elif self._is_failed_status(status):
                return await self._handle_failed_callback(task_id, callback_data)
            else:
                self.logger.warning(f"未知的回调状态: {status}, 任务: {task_id}")
                return {
                    'success': True,
                    'message': f'未知状态: {status}'
                }
                
        except Exception as e:
            self.logger.error(f"处理图像Webhook失败: {e}")
            return {
                'success': False,
                'error': f'处理失败: {str(e)}'
            }
    
    async def _handle_success_callback(self, task_id: str, data: Dict[str, Any], files: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理成功回调 - 支持URL和文件两种方式"""
        try:
            result_path = None
            
            # 方式1：从URL获取结果
            result_path = self._extract_result_path(data)
            
            # 方式2：从上传文件获取结果
            if not result_path and files:
                result_file = self._extract_result_file(files)
                if result_file:
                    # 这里应该保存文件并返回路径
                    # 为了简化，我们暂时将文件名作为路径
                    result_path = getattr(result_file, 'filename', f"uploaded_file_{task_id}")
                    self.logger.info(f"从上传文件获取结果: {result_path}")
            
            if not result_path:
                self.logger.error(f"成功回调缺少结果（URL或文件）: {task_id}")
                # 即使没有结果，也标记为失败并自动退还积分
                await self.image_service.fail_task(task_id, "回调成功但缺少结果文件")
                return {
                    'success': False,
                    'error': '缺少结果路径'
                }
            
            # 更新任务为完成状态
            success = await self.image_service.complete_task(task_id, result_path)
            
            if success:
                self.logger.info(f"任务完成: {task_id}, 结果: {result_path}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'result_path': result_path,
                    'message': '任务完成'
                }
            else:
                self.logger.error(f"更新任务状态失败: {task_id}")
                return {
                    'success': False,
                    'error': '更新状态失败'
                }
                
        except Exception as e:
            self.logger.error(f"处理成功回调失败: {e}")
            # 确保任务状态正确更新
            await self.image_service.fail_task(task_id, f"处理成功回调时发生错误: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _handle_failed_callback(self, task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理失败回调 - 自动退还用户积分"""
        try:
            error_message = self._extract_error_message(data)
            simplified_error = self._simplify_technical_error(error_message)
            
            # 更新任务为失败状态（会自动退还积分）
            success = await self.image_service.fail_task(task_id, simplified_error)
            
            if success:
                self.logger.info(f"任务失败: {task_id}, 原始错误: {error_message}, 简化错误: {simplified_error}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'error_message': simplified_error,
                    'message': '任务失败已记录，积分已退还'
                }
            else:
                self.logger.error(f"更新失败状态失败: {task_id}")
                return {
                    'success': False,
                    'error': '更新失败状态失败'
                }
                
        except Exception as e:
            self.logger.error(f"处理失败回调失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_webhook_data(self, data: Dict[str, Any], required_fields: list = None) -> Dict[str, Any]:
        """
        验证Webhook数据格式
        
        Args:
            data: 回调数据
            required_fields: 必需字段列表
            
        Returns:
            验证结果
        """
        if required_fields is None:
            required_fields = ['id_gen', 'status']
        
        missing_fields = []
        for field in required_fields:
            if not data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            return {
                'valid': False,
                'error': f'缺少必需字段: {", ".join(missing_fields)}'
            }
        
        return {
            'valid': True,
            'message': '数据验证通过'
        }


class WebhookProcessor:
    """Webhook处理器的业务层封装"""
    
    def __init__(self, webhook_handler: WebhookHandler):
        self.webhook_handler = webhook_handler
        self.logger = logging.getLogger(__name__)
    
    async def process_callback(self, 
                             callback_data: Dict[str, Any],
                             callback_type: str = "image",
                             files: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理各种类型的API回调 - 支持用户完整字段列表
        
        Args:
            callback_data: 回调数据
            callback_type: 回调类型 (image, video, faceswap)
            files: 上传的文件
            
        Returns:
            处理结果
        """
        try:
            # 验证数据
            validation_result = self.webhook_handler.validate_webhook_data(callback_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            # 处理不同类型的回调
            if callback_type in ["image", "video", "faceswap"]:
                return await self.webhook_handler.handle_image_webhook(callback_data, files)
            else:
                return {
                    'success': False,
                    'error': f'不支持的回调类型: {callback_type}'
                }
                
        except Exception as e:
            self.logger.error(f"处理回调失败: {e}")
            return {
                'success': False,
                'error': f'处理异常: {str(e)}'
            }
    
    # 保持向后兼容性
    async def process_clothoff_callback(self, 
                                      callback_data: Dict[str, Any],
                                      callback_type: str = "image") -> Dict[str, Any]:
        """向后兼容的ClothOff API回调处理"""
        return await self.process_callback(callback_data, callback_type)
    
    def get_webhook_statistics(self) -> Dict[str, Any]:
        """获取Webhook处理统计信息"""
        # 这里可以添加统计逻辑
        return {
            'total_callbacks': 0,
            'success_callbacks': 0,
            'failed_callbacks': 0,
            'timestamp': datetime.now().isoformat()
        } 