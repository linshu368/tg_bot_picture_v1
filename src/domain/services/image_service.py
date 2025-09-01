"""
图像服务 - 负责图像处理相关的业务逻辑
修改：已迁移为完全依赖 PointCompositeRepository，不再涉及任何单表repo逻辑
"""

import logging
import uuid
import json
from typing import Dict, Any, Optional, BinaryIO, List
from datetime import datetime
from enum import Enum

# 迁移说明：服务层完全依赖组合仓库（PointCompositeRepository）


class ImageStatus(Enum):
    """图像任务状态枚举"""
    PENDING = "pending"      # 待处理（与数据库字段对应）
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败


class BodyType(Enum):
    """体型选项"""
    SKINNY = "skinny"
    NORMAL = "normal" 
    CURVY = "curvy"
    MUSCULAR = "muscular"


class BreastSize(Enum):
    """胸部尺寸"""
    SMALL = "small"
    NORMAL = "normal"
    BIG = "big"


class ButtSize(Enum):
    """臀部尺寸"""
    SMALL = "small"
    NORMAL = "normal"
    BIG = "big"


class ClothType(Enum):
    """服装类型"""
    NAKED = "naked"
    BIKINI = "bikini"
    LINGERIE = "lingerie"


class ImageGenerationParams:
    """图像生成参数类"""
    
    def __init__(self, 
                 body_type: str = "normal",
                 breast_size: str = "normal", 
                 butt_size: str = "normal",
                 cloth: str = "naked",
                 age: Optional[str] = None,
                 pose: Optional[str] = None):
        self.body_type = body_type
        self.breast_size = breast_size
        self.butt_size = butt_size
        self.cloth = cloth
        self.age = age
        self.pose = pose
    
    def validate(self) -> List[str]:
        """验证参数有效性"""
        errors = []
        
        # 验证体型
        if self.body_type not in [e.value for e in BodyType]:
            errors.append(f"无效的体型选项: {self.body_type}")
        
        # 验证胸部尺寸
        if self.breast_size not in [e.value for e in BreastSize]:
            errors.append(f"无效的胸部尺寸: {self.breast_size}")
        
        # 验证臀部尺寸
        if self.butt_size not in [e.value for e in ButtSize]:
            errors.append(f"无效的臀部尺寸: {self.butt_size}")
        
        # 验证服装类型
        if self.cloth not in [e.value for e in ClothType]:
            errors.append(f"无效的服装类型: {self.cloth}")
        
        # 验证年龄
        if self.age is not None:
            try:
                age_int = int(self.age)
                if age_int < 18 or age_int > 80:
                    errors.append("年龄必须在18-80之间")
            except ValueError:
                errors.append("年龄必须是数字")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "body_type": self.body_type,
            "breast_size": self.breast_size,
            "butt_size": self.butt_size,
            "cloth": self.cloth,
            "age": self.age,
            "pose": self.pose
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageGenerationParams':
        """从字典创建实例"""
        return cls(
            body_type=data.get("body_type", "normal"),
            breast_size=data.get("breast_size", "normal"),
            butt_size=data.get("butt_size", "normal"),
            cloth=data.get("cloth", "naked"),
            age=data.get("age"),
            pose=data.get("pose")
        )


class ImageService:
    """图像处理服务（仅依赖PointCompositeRepository）"""
    
    # 修改：构造仅接收组合仓库
    def __init__(self, point_composite_repo=None):
        """
        初始化图像服务
        
        Args:
            point_composite_repo: 组合仓库
        """
        self.logger = logging.getLogger(__name__)
        if not point_composite_repo:
            raise ValueError("必须提供point_composite_repo")
        self.point_composite_repo = point_composite_repo
        self.logger.info("🔧 ImageService: 使用PointCompositeRepository（完全迁移）")
    
    # 并行验证与统计相关代码已移除
    
    async def validate_image_params(self, params: ImageGenerationParams) -> List[str]:
        """验证图像生成参数"""
        return params.validate()
    
    async def calculate_cost(self, params: ImageGenerationParams) -> int:
        """计算图像生成成本"""
        # 基础成本
        base_cost = 10
        
        # 根据参数调整成本
        cost = base_cost
        
        # 特殊体型增加成本
        if params.body_type in ["muscular", "curvy"]:
            cost += 2
        
        # 特殊服装增加成本
        if params.cloth in ["bikini", "lingerie"]:
            cost += 3
        
        # 指定姿势增加成本
        if params.pose:
            cost += 5
        
        return cost
    
    async def create_image_task(self, 
                              user_id: int,
                              params: ImageGenerationParams,
                              credits_cost: Optional[int] = None) -> Dict[str, Any]:
        """创建图像生成任务
        
        修改：优先使用 PointCompositeRepository 执行任务创建+积分扣除
        回退：若未配置组合仓库，则仅创建任务记录，不扣积分
        """
        try:
            # 验证参数
            errors = await self.validate_image_params(params)
            if errors:
                return {
                    "success": False,
                    "error": f"参数验证失败: {', '.join(errors)}"
                }
            
            # 计算成本
            if credits_cost is None:
                credits_cost = await self.calculate_cost(params)

            # 生成任务ID
            task_id = str(uuid.uuid4())    
            
            # 准备任务数据
            task_data = {
                'user_id': user_id,
                'task_id': task_id,
                'task_type': 'undress',  # 默认任务类型
                'status': ImageStatus.PENDING.value,  # 使用数据库对应的status
                'points_cost': credits_cost,
                'api_response': {
                    'params': params.to_dict()  # 将参数保存在api_response中
                }
            }
            
            # 修改：若配置了组合仓库，走“任务+扣积分”的原子流程
            if self.point_composite_repo:
                created = await self.point_composite_repo.create_task_with_payment(
                    user_id=user_id,
                    task_type=task_data['task_type'],
                    task_data={
                        'task_id': task_id,
                        'status': task_data['status'],
                        'api_response': task_data['api_response']
                    },
                    points_cost=credits_cost
                )
                if created:
                    self.logger.info(f"创建图像任务(组合仓库)成功: {task_id}, 用户: {user_id}")
                    return {
                        "success": True,
                        "task_id": task_id,
                        "credits_cost": credits_cost,
                        "status": ImageStatus.PENDING.value
                    }
                else:
                    return {"success": False, "error": "创建任务或扣除积分失败"}

            # 不应到达：若组合仓库不可用已提前返回错误
            return {"success": False, "error": "PointCompositeRepository未配置"}
            
        except Exception as e:
            self.logger.error(f"创建图像任务失败: {e}")
            return {
                "success": False,
                "error": f"系统错误: {str(e)}"
            }
    
    async def create_image_task_with_payment(self, 
                                           user_id: int,
                                           params: ImageGenerationParams,
                                           credits_cost: Optional[int] = None) -> Dict[str, Any]:
        """创建图像任务并扣除积分（Migrated模式专用）
        
        修改：统一依赖 PointCompositeRepository；若未配置则返回错误
        """
        try:
            # 验证参数
            errors = await self.validate_image_params(params)
            if errors:
                return {
                    "success": False,
                    "error": f"参数验证失败: {', '.join(errors)}"
                }
            
            # 计算成本
            if credits_cost is None:
                credits_cost = await self.calculate_cost(params)
            
            # 生成任务ID
            task_id = str(uuid.uuid4())
            
            # 准备任务数据
            task_data = {
                'task_id': task_id,
                'status': ImageStatus.PENDING.value,
                'api_response': {
                    'params': params.to_dict()
                }
            }
            
            if not self.point_composite_repo:
                return {"success": False, "error": "PointCompositeRepository未配置"}

            created_task = await self.point_composite_repo.create_task_with_payment(
                user_id=user_id,
                task_type='undress',
                task_data=task_data,
                points_cost=credits_cost  # 🔧 传入正确的积分成本，保持业务逻辑一致性
            )
            
            if created_task:
                self.logger.info(f"创建图像任务(含积分扣除)成功: {task_id}, 用户: {user_id}")
                return {
                    "success": True,
                    "task_id": task_id,
                    "credits_cost": credits_cost,
                    "status": ImageStatus.PENDING.value
                }
            else:
                return {
                    "success": False,
                    "error": "创建任务或扣除积分失败"
                }
                
        except Exception as e:
            self.logger.error(f"创建图像任务(含积分扣除)失败: {e}")
            return {
                "success": False,
                "error": f"系统错误: {str(e)}"
            }
    
    async def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        try:
            task_data = await self.point_composite_repo.get_task_by_id(task_id)
            
            if task_data:
                # 转换为标准格式
                return {
                    'id': task_data['id'],
                    'user_id': task_data['user_id'],
                    'task_id': task_data['task_id'],
                    'status': task_data['status'],
                    'credits_cost': task_data.get('points_cost', 0),
                    'result_path': task_data.get('output_image_url'),
                    'error_message': task_data.get('error_message'),
                    'created_at': task_data['created_at'],
                    'updated_at': task_data['updated_at'],
                    'params': self._extract_params_from_api_response(task_data.get('api_response', {}))
                }
            return None
            
        except Exception as e:
            self.logger.error(f"获取任务信息失败: {e}")
            return None
    
    def _extract_params_from_api_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """从api_response中提取参数"""
        try:
            return api_response.get('params', {})
        except Exception:
            return {}
    
    async def update_task_status(self, 
                               task_id: str, 
                               status: str,
                               result_path: Optional[str] = None,
                               error_message: Optional[str] = None) -> bool:
        """更新任务状态"""
        try:
            # 验证状态
            valid_statuses = [s.value for s in ImageStatus]
            if status not in valid_statuses:
                self.logger.error(f"无效的任务状态: {status}")
                return False
            
            # 准备更新数据
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if result_path:
                update_data['output_image_url'] = result_path
            
            if error_message:
                update_data['error_message'] = error_message
            
            if status == ImageStatus.COMPLETED.value:
                update_data['completed_at'] = datetime.utcnow().isoformat()
            
            success = await self.point_composite_repo.update_task_status(task_id, status, result_path, error_message)
            
            if success:
                self.logger.info(f"更新任务状态成功: {task_id} -> {status}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"更新任务状态失败: {e}")
            return False
    
    async def complete_task(self, task_id: str, result_path: str) -> bool:
        """完成任务"""
        return await self.update_task_status(
            task_id, ImageStatus.COMPLETED.value, result_path
        )
    
    async def fail_task(self, task_id: str, error_message: str) -> bool:
        """任务失败"""
        return await self.update_task_status(
            task_id, ImageStatus.FAILED.value, None, error_message
        )
    
    async def start_processing(self, task_id: str) -> bool:
        """开始处理任务"""
        return await self.update_task_status(
            task_id, ImageStatus.PROCESSING.value
        )
    
    async def get_user_task_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户任务历史"""
        try:
            tasks_data = await self.point_composite_repo.get_user_tasks(user_id, limit)
            
            # 转换为兼容格式
            tasks = []
            for task_data in tasks_data:
                task = {
                    'id': task_data['id'],
                    'user_id': task_data['user_id'],
                    'task_id': task_data['task_id'],
                    'status': task_data['status'],
                    'credits_cost': task_data.get('points_cost', 0),
                    'result_path': task_data.get('output_image_url'),
                    'error_message': task_data.get('error_message'),
                    'created_at': task_data['created_at'],
                    'updated_at': task_data['updated_at'],
                    'params': self._extract_params_from_api_response(task_data.get('api_response', {}))
                }
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            self.logger.error(f"获取用户任务历史失败: {e}")
            return []
    
    async def get_task_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户任务统计"""
        try:
            tasks = await self.point_composite_repo.get_user_tasks(user_id, 100)
            
            stats = {
                "total_tasks": len(tasks),
                "completed_tasks": 0,
                "failed_tasks": 0,
                "pending_tasks": 0,
                "processing_tasks": 0,
                "total_credits_spent": 0
            }
            
            for task in tasks:
                if task['status'] == ImageStatus.COMPLETED.value:
                    stats["completed_tasks"] += 1
                elif task['status'] == ImageStatus.FAILED.value:
                    stats["failed_tasks"] += 1
                elif task['status'] == ImageStatus.PENDING.value:
                    stats["pending_tasks"] += 1
                elif task['status'] == ImageStatus.PROCESSING.value:
                    stats["processing_tasks"] += 1
                
                stats["total_credits_spent"] += task.get('points_cost', 0)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取任务统计失败: {e}")
            return {
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "pending_tasks": 0,
                "processing_tasks": 0,
                "total_credits_spent": 0
            }
    
    async def get_pending_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取待处理的任务"""
        try:
            return await self.point_composite_repo.get_tasks_by_status(ImageStatus.PENDING.value, limit)
        except Exception as e:
            self.logger.error(f"获取待处理任务失败: {e}")
            return []
    
    async def get_processing_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取处理中的任务"""
        try:
            return await self.point_composite_repo.get_tasks_by_status(ImageStatus.PROCESSING.value, limit)
        except Exception as e:
            self.logger.error(f"获取处理中任务失败: {e}")
            return []
    
    async def get_recent_tasks(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的任务"""
        try:
            return await self.point_composite_repo.get_recent_tasks(hours, limit)
        except Exception as e:
            self.logger.error(f"获取最近任务失败: {e}")
            return []
    
    async def get_system_task_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取系统任务统计"""
        try:
            return await self.point_composite_repo.get_task_statistics(days)
        except Exception as e:
            self.logger.error(f"获取系统任务统计失败: {e}")
            return {
                'total': 0, 'completed': 0, 'failed': 0, 'pending': 0, 'processing': 0,
                'success_rate': 0.0, 'avg_processing_time': 0
            }
    
    async def cleanup_old_tasks(self, days: int = 30) -> int:
        """清理旧任务"""
        try:
            return await self.point_composite_repo.cleanup_old_tasks(days)
        except Exception as e:
            self.logger.error(f"清理旧任务失败: {e}")
            return 0
    
    async def update_task_webhook(self, task_id: str, webhook_url: str) -> bool:
        """更新任务的Webhook URL"""
        try:
            return await self.point_composite_repo.update_task_webhook(task_id, webhook_url)
        except Exception as e:
            self.logger.error(f"更新任务Webhook失败: {e}")
            return False
    
    async def update_task_input_image(self, task_id: str, input_image_url: str) -> bool:
        """更新任务的输入图像URL"""
        try:
            return await self.point_composite_repo.update_task_input_image(task_id, input_image_url)
        except Exception as e:
            self.logger.error(f"更新任务输入图像失败: {e}")
            return False
    
    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据task_id获取任务（别名方法）"""
        return await self.get_task_info(task_id)
    
    async def batch_update_task_status(self, task_ids: List[str], status: str) -> int:
        """批量更新任务状态"""
        try:
            success_count = 0
            for task_id in task_ids:
                if await self.update_task_status(task_id, status):
                    success_count += 1
            
            self.logger.info(f"批量更新任务状态: {success_count}/{len(task_ids)} 成功")
            return success_count
            
        except Exception as e:
            self.logger.error(f"批量更新任务状态失败: {e}")
            return 0
    
    # 便捷的业务方法
    async def create_undress_task(self, user_id: int, input_image_url: str, 
                                 webhook_url: str = None) -> Dict[str, Any]:
        """创建脱衣任务（简化接口）"""
        try:
            # 使用组合仓库创建任务并扣除默认积分
            params = ImageGenerationParams()
            created = await self.create_image_task_with_payment(
                user_id=user_id,
                params=params,
                credits_cost=10
            )
            if created.get("success"):
                return created
            return {"success": False, "error": created.get("error", "创建任务失败")}
                
        except Exception as e:
            self.logger.error(f"创建脱衣任务失败: {e}")
            return {
                "success": False,
                "error": f"系统错误: {str(e)}"
            }
    
    async def process_webhook_callback(self, task_id: str, callback_data: Dict[str, Any]) -> bool:
        """处理Webhook回调"""
        try:
            # 解析回调数据
            status = callback_data.get('status')
            output_url = callback_data.get('output_image_url')
            error_message = callback_data.get('error_message')
            
            if status == 'success' and output_url:
                return await self.complete_task(task_id, output_url)
            elif status == 'failed' or error_message:
                return await self.fail_task(task_id, error_message or "处理失败")
            else:
                self.logger.warning(f"未知的回调状态: {status}")
                return False
                
        except Exception as e:
            self.logger.error(f"处理Webhook回调失败: {e}")
            return False