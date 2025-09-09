"""
图片处理回调处理模块 - 处理图片处理API的异步回调通知
"""

import logging
from flask import Flask, request, jsonify
from typing import Dict, Any
import asyncio
from threading import Thread
import time
from datetime import datetime

from src.infrastructure.messaging.webhook_handler import WebhookHandler, WebhookProcessor
from src.utils.performance_monitor import get_performance_monitor


class ImageWebhookHandler:
    """图片处理Webhook处理器 - 支持用户提供的完整端点列表"""
    
    def __init__(self, webhook_processor: WebhookProcessor):
        self.webhook_processor = webhook_processor
        self.app = Flask(__name__)
        self.logger = logging.getLogger(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """设置路由 - 支持用户提供的完整端点列表"""
        
        # 图片处理回调端点
        @self.app.route('/webhook/image-process', methods=['POST'])
        def image_process_callback():
            return self.handle_image_process_callback()
        
        # 视频动画回调端点  
        @self.app.route('/webhook/video-process', methods=['POST'])
        def video_process_callback():
            return self.handle_video_process_callback()
        
        # 人脸交换回调端点
        @self.app.route('/webhook/faceswap-process', methods=['POST'])
        def faceswap_process_callback():
            return self.handle_faceswap_process_callback()
        
        # 健康检查端点
        @self.app.route('/webhook/health', methods=['GET'])
        def webhook_health():
            return jsonify({
                "status": "ok", 
                "service": "image-webhook",
                "timestamp": datetime.now().isoformat()
            })
        
        # 信息端点
        @self.app.route('/webhook/info', methods=['GET'])
        def webhook_info():
            return jsonify({
                "service": "image-webhook",
                "version": "2.0",
                "supported_endpoints": [
                    "/webhook/image-process",
                    "/webhook/video-process", 
                    "/webhook/faceswap-process",
                    "/webhook/health",
                    "/webhook/info",
                    "/"
                ],
                "supported_methods": {
                    "image-process": "POST (multipart/form-data)",
                    "video-process": "POST (application/json or multipart/form-data)",
                    "faceswap-process": "POST (application/json or multipart/form-data)"
                }
            })
        
        # 首页端点
        @self.app.route('/', methods=['GET'])
        def webhook_home():
            return jsonify({
                "message": "图片处理Webhook服务",
                "status": "running",
                "endpoints": ["/webhook/info", "/webhook/health"]
            })
    
    def handle_image_process_callback(self) -> str:
        """处理图片处理回调 - multipart/form-data"""
        monitor = get_performance_monitor()
        operation_id = f"webhook_image_{int(time.time())}"
        monitor.start_timer(operation_id, "收到图片处理webhook回调")
        
        try:
            # 获取表单数据和文件
            monitor.checkpoint(operation_id, "parse_request", "解析请求数据")
            callback_data = request.form.to_dict()
            files = request.files.to_dict() if request.files else {}
            
            self.logger.info(f"收到图片处理回调: 数据={callback_data}, 文件数={len(files)}")
            
            # 验证基础字段
            monitor.checkpoint(operation_id, "validate_data", "验证回调数据")
            if 'id_gen' not in callback_data:
                monitor.end_timer(operation_id, "缺少id_gen字段，快速结束")
                self.logger.error("图片处理回调缺少id_gen字段")
                return "fail"
            
            # 异步处理回调
            monitor.checkpoint(operation_id, "async_process", "开始异步处理回调")
            self.process_callback_async("image", callback_data, files)
            
            monitor.end_timer(operation_id, "图片处理webhook回调处理完成")
            return "success"
                
        except Exception as e:
            monitor.end_timer(operation_id, f"图片处理webhook回调异常: {str(e)}")
            self.logger.error(f"处理图片处理回调异常: {e}")
            return "fail"
    
    def handle_video_process_callback(self) -> str:
        """处理视频动画回调 - application/json 或 multipart/form-data"""
        try:
            callback_data = {}
            files = {}
            
            # 处理不同的内容类型
            if request.is_json:
                callback_data = request.get_json() or {}
            else:
                callback_data = request.form.to_dict()
                files = request.files.to_dict() if request.files else {}
            
            self.logger.info(f"收到视频处理回调: 数据={callback_data}, 文件数={len(files)}")
            
            # 验证任务ID（支持多个可能的字段名）
            task_id = (callback_data.get('idGeneration') or 
                      callback_data.get('id_gen') or 
                      callback_data.get('task_id'))
            
            if not task_id:
                self.logger.error("视频处理回调缺少任务ID")
                return "fail"
            
            # 异步处理回调
            self.process_callback_async("video", callback_data, files)
            
            return "success"
                
        except Exception as e:
            self.logger.error(f"处理视频处理回调异常: {e}")
            return "fail"
    
    def handle_faceswap_process_callback(self) -> str:
        """处理人脸交换回调 - application/json 或 multipart/form-data"""
        try:
            callback_data = {}
            files = {}
            
            # 处理不同的内容类型
            if request.is_json:
                callback_data = request.get_json() or {}
            else:
                callback_data = request.form.to_dict()
                files = request.files.to_dict() if request.files else {}
            
            self.logger.info(f"收到人脸交换回调: 数据={callback_data}, 文件数={len(files)}")
            
            # 验证任务ID（支持多个可能的字段名）
            task_id = (callback_data.get('idGeneration') or 
                      callback_data.get('id_gen') or 
                      callback_data.get('task_id'))
            
            if not task_id:
                self.logger.error("人脸交换回调缺少任务ID")
                return "fail"
            
            # 异步处理回调
            self.process_callback_async("faceswap", callback_data, files)
            
            return "success"
                
        except Exception as e:
            self.logger.error(f"处理人脸交换回调异常: {e}")
            return "fail"
    
    def process_callback_async(self, callback_type: str, callback_data: Dict[str, Any], files: Dict[str, Any]):
        """异步处理回调"""
        def process():
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._process_callback(callback_type, callback_data, files))
            except Exception as e:
                self.logger.error(f"异步处理{callback_type}回调失败: {e}")
            finally:
                try:
                    loop.close()
                except:
                    pass
        
        Thread(target=process, daemon=True).start()
    
    async def _process_callback(self, callback_type: str, callback_data: Dict[str, Any], files: Dict[str, Any]):
        """处理回调逻辑"""
        try:
            # 使用WebhookProcessor处理回调
            result = await self.webhook_processor.process_callback(
                callback_data=callback_data,
                callback_type=callback_type,
                files=files
            )
            
            task_id = (callback_data.get('idGeneration') or 
                      callback_data.get('id_gen') or 
                      callback_data.get('task_id', 'unknown'))
            
            if result['success']:
                self.logger.info(f"{callback_type}回调处理成功: {task_id}")
            else:
                self.logger.error(f"{callback_type}回调处理失败: {task_id}, 错误: {result.get('error')}")
                
        except Exception as e:
            self.logger.error(f"处理{callback_type}回调逻辑失败: {e}")
    
    def run(self, host='0.0.0.0', port=5003, debug=False):
        """运行图片Webhook服务器"""
        self.logger.info(f"启动图片处理回调服务器: {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)