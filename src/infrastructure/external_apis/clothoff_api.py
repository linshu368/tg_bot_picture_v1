"""
ClothOff API 重构版 - 外部图像处理API接口
仅支持图片去衣功能
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, BinaryIO
from datetime import datetime
import aiohttp

from src.domain.services.image_service import ImageGenerationParams


class APIError(Exception):
    """API错误基类"""
    pass


class APITimeoutError(APIError):
    """API超时错误"""
    pass


class APIResponseError(APIError):
    """API响应错误"""
    pass


class ClothoffAPIClient:
    """ClothOff API客户端 - 仅支持图片去衣"""
    
    def __init__(self, 
                 api_url: str,
                 webhook_base_url: str,
                 api_key: Optional[str] = None,
                 timeout: int = 30):
        self.api_url = api_url
        self.webhook_base_url = webhook_base_url
        self.api_key = api_key
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # HTTP会话配置
        self.session_config = {
            'timeout': aiohttp.ClientTimeout(total=timeout),
            'headers': {
                'accept': 'application/json',
                'user-agent': 'TelegramBot/2.0'
            }
        }
        
        if self.api_key:
            self.session_config['headers']['x-api-key'] = self.api_key
    
    async def _create_session(self) -> aiohttp.ClientSession:
        """创建HTTP会话"""
        return aiohttp.ClientSession(**self.session_config)
    
    def _build_webhook_url(self, endpoint: str) -> str:
        """构建webhook URL"""
        return f"{self.webhook_base_url}/webhook/{endpoint}"
    
    async def generate_image(self,
                           image_data: bytes,
                           filename: str,
                           params: ImageGenerationParams,
                           task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        发送图像去衣请求
        
        Args:
            image_data: 图像文件数据
            filename: 文件名
            params: 图像生成参数
            task_id: 任务ID（可选）
            
        Returns:
            API响应结果
        """
        try:
            if not task_id:
                task_id = str(uuid.uuid4())
            
            # 构建请求数据
            webhook_url = self._build_webhook_url("image-process")
            
            # 准备表单数据
            form_data = aiohttp.FormData()
            
            # 添加图像文件
            form_data.add_field(
                'image',
                image_data,
                filename=filename,
                content_type='image/jpeg'
            )
            
            # 添加参数
            form_data.add_field('id_gen', task_id)
            form_data.add_field('webhook', webhook_url)
            form_data.add_field('body_type', params.body_type)
            form_data.add_field('breast_size', params.breast_size)
            form_data.add_field('butt_size', params.butt_size)
            form_data.add_field('cloth', params.cloth)
            
            # 添加可选参数
            if params.age:
                form_data.add_field('age', params.age)
            if params.pose:
                form_data.add_field('pose', params.pose)
            
            self.logger.info(f"发送图像去衣请求 - 任务ID: {task_id}")
            self.logger.debug(f"参数: {params.to_dict()}")
            
            # 发送请求
            async with await self._create_session() as session:
                async with session.post(self.api_url, data=form_data) as response:
                    response_text = await response.text()
                    
                    self.logger.info(f"API响应状态码: {response.status}")
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                            self.logger.info(f"任务提交成功 - 队列位置: {result.get('queue_num', 'N/A')}")
                            
                            return {
                                'success': True,
                                'task_id': task_id,
                                'queue_num': result.get('queue_num', 0),
                                'api_balance': result.get('api_balance', 0),
                                'response': result
                            }
                        except Exception as e:
                            self.logger.error(f"解析API响应失败: {e}")
                            raise APIResponseError(f"响应解析错误: {e}")
                    else:
                        self.logger.error(f"API请求失败: {response.status} - {response_text}")
                        raise APIResponseError(f"API返回错误: {response.status}")
                        
        except asyncio.TimeoutError:
            self.logger.error(f"API请求超时: {task_id}")
            raise APITimeoutError("API请求超时")
        except Exception as e:
            self.logger.error(f"图像去衣请求失败: {e}")
            raise APIError(f"请求失败: {str(e)}")
    
    async def check_balance(self) -> Dict[str, Any]:
        """检查API余额"""
        try:
            async with await self._create_session() as session:
                async with session.get(f"{self.api_url}/balance") as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            'success': True,
                            'balance': result.get('balance', 0)
                        }
                    else:
                        return {
                            'success': False,
                            'error': f"查询余额失败: {response.status}"
                        }
        except Exception as e:
            self.logger.error(f"查询余额失败: {e}")
            return {
                'success': False,
                'error': f"查询余额异常: {str(e)}"
            }
    
    async def get_queue_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务队列状态"""
        try:
            async with await self._create_session() as session:
                async with session.get(f"{self.api_url}/status/{task_id}") as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            'success': True,
                            'status': result.get('status', 'unknown'),
                            'queue_position': result.get('queue_position', -1)
                        }
                    else:
                        return {
                            'success': False,
                            'error': f"查询状态失败: {response.status}"
                        }
        except Exception as e:
            self.logger.error(f"查询任务状态失败: {e}")
            return {
                'success': False,
                'error': f"查询状态异常: {str(e)}"
            }


class ClothoffAPI:
    """ClothOff API服务 - 业务层封装，仅支持图片去衣"""
    
    def __init__(self, client: ClothoffAPIClient):
        self.client = client
        self.logger = logging.getLogger(__name__)
    
    async def submit_image_generation(self,
                                    image_data: bytes,
                                    filename: str,
                                    params: ImageGenerationParams,
                                    task_id: str) -> Dict[str, Any]:
        """
        提交图像去衣任务
        
        Args:
            image_data: 图像数据
            filename: 文件名
            params: 生成参数
            task_id: 任务ID
            
        Returns:
            提交结果
        """
        try:
            result = await self.client.generate_image(
                image_data=image_data,
                filename=filename,
                params=params,
                task_id=task_id
            )
            
            if result['success']:
                self.logger.info(f"图像去衣任务提交成功: {task_id}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'queue_position': result.get('queue_num', 0)
                }
            else:
                return {
                    'success': False,
                    'error': '任务提交失败'
                }
                
        except APITimeoutError:
            return {
                'success': False,
                'error': 'API请求超时，请稍后重试'
            }
        except APIResponseError as e:
            return {
                'success': False,
                'error': f'API响应错误: {str(e)}'
            }
        except APIError as e:
            return {
                'success': False,
                'error': f'API错误: {str(e)}'
            }
        except Exception as e:
            self.logger.error(f"提交图像去衣任务失败: {e}")
            return {
                'success': False,
                'error': '系统内部错误'
            }
    
    async def get_api_status(self) -> Dict[str, Any]:
        """获取API状态信息"""
        try:
            balance_result = await self.client.check_balance()
            
            return {
                'success': True,
                'balance': balance_result.get('balance', 0) if balance_result['success'] else 0,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"获取API状态失败: {e}")
            return {
                'success': False,
                'error': '获取状态失败'
            }


class ClothOffAPI:
    """ClothOff API类，用于容器注入 - 真实API实现，仅支持图片去衣"""
    
    def __init__(self, api_url: str, webhook_url: str, api_key: str):
        self.api_url = api_url
        self.webhook_url = webhook_url
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
    
    def generate_image(self, 
                      image_file,
                      filename: str,
                      task_id: Optional[str] = None,
                      body_type: str = "normal",
                      breast_size: str = "normal", 
                      butt_size: str = "normal",
                      cloth: str = "naked",
                      pose: Optional[str] = None,
                      age: Optional[str] = None) -> Dict[str, Any]:
        """
        发送图像去衣请求到Clothoff API
        
        Args:
            image_file: 输入图像文件（BytesIO对象）
            filename: 文件名
            task_id: 任务ID（可选，默认生成UUID）
            body_type: 体型选项 - skinny, normal, curvy, muscular
            breast_size: 胸部尺寸 - small, normal, big
            butt_size: 臀部尺寸 - small, normal, big
            cloth: 服装选项 - naked, bikini, lingerie等
            pose: 姿势选项（可选）
            age: 年龄参数（可选）
            
        Returns:
            API响应结果
        """
        try:
            import requests
            
            # 生成任务ID
            if not task_id:
                task_id = str(uuid.uuid4())
            
            # 构建图像处理webhook URL
            webhook_callback_url = f"{self.webhook_url}/webhook/image-process"
            
            # 准备表单数据
            files = {
                'image': (filename, image_file, 'image/jpeg')
            }
            
            data = {
                'id_gen': task_id,
                'webhook': webhook_callback_url,
                'body_type': body_type,
                'breast_size': breast_size,
                'butt_size': butt_size,
                'cloth': cloth
            }
            
            # 添加可选参数
            if pose:
                data['pose'] = pose
            if age:
                data['age'] = age
            
            # 准备请求头
            headers = {
                'accept': 'application/json'
            }
            
            # 如果有API密钥，添加到请求头
            if self.api_key:
                headers['x-api-key'] = self.api_key
            
            self.logger.info(f"发送Clothoff图像去衣API请求 - 任务ID: {task_id}")
            self.logger.debug(f"请求参数: {data}")
            
            # 发送请求
            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
            
            self.logger.info(f"Clothoff API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"任务提交成功 - 队列位置: {result.get('queue_num', 'N/A')}, 余额: {result.get('api_balance', 'N/A')}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'queue_num': result.get('queue_num', 0),
                    'api_balance': result.get('api_balance', 0),
                    'response': result
                }
            else:
                error_text = response.text
                self.logger.error(f"Clothoff API请求失败: {response.status_code} - {error_text}")
                return {
                    'success': False,
                    'error': f'API请求失败: {response.status_code}',
                    'response_text': error_text
                }
                
        except requests.exceptions.Timeout:
            self.logger.error(f"Clothoff API请求超时: {task_id}")
            return {
                'success': False,
                'error': 'API请求超时，请稍后重试'
            }
        except Exception as e:
            self.logger.error(f"Clothoff API调用异常: {e}")
            return {
                'success': False,
                'error': f'API调用异常: {str(e)}'
            } 