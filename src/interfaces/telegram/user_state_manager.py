"""
用户状态管理器 - 简化版本
只保留基本的状态存储和切换功能
"""

import logging
from typing import Dict, Any, Optional


class UserStateManager:
    """简化的用户状态管理器"""
    
    def __init__(self):
        self.states: Dict[int, str] = {}  # 用户ID -> 当前状态
        self.data: Dict[int, Dict[str, Any]] = {}  # 用户ID -> 数据
        self.logger = logging.getLogger(__name__)
    
    def get_current_state(self, user_id: int) -> str:
        """获取用户当前状态"""
        return self.states.get(user_id, States.IDLE)
    
    def update_user_state(self, user_id: int, state: str):
        """更新用户状态"""
        self.states[user_id] = state
        self.logger.debug(f"用户 {user_id} 状态更新为: {state}")
    
    def reset_user_state(self, user_id: int):
        """重置用户状态"""
        self.states.pop(user_id, None)
        self.data.pop(user_id, None)
        self.logger.debug(f"重置用户 {user_id} 状态")
    
    def set_user_data(self, user_id: int, key: str, value: Any):
        """设置用户数据"""
        if user_id not in self.data:
            self.data[user_id] = {}
        self.data[user_id][key] = value
    
    def get_user_data(self, user_id: int, key: str, default: Any = None) -> Any:
        """获取用户数据"""
        return self.data.get(user_id, {}).get(key, default)
    
    def set_user_expiry(self, user_id: int, minutes: int):
        """设置过期时间 - 简化版本，只是占位符"""
        # 简化：不实际处理过期，依赖用户交互清除状态
        pass


class UserStateHelper:
    """状态辅助工具"""
    
    def __init__(self, state_manager: UserStateManager):
        self.state_manager = state_manager
    
    def clear_user_flow(self, user_id: int):
        """清除用户流程"""
        self.state_manager.reset_user_state(user_id)
    
    def start_quick_undress_flow(self, user_id: int):
        """开始快速去衣流程"""
        self.state_manager.update_user_state(user_id, States.QUICK_UNDRESS_WAITING_PHOTO)
    
    def start_custom_undress_flow(self, user_id: int):
        """开始自定义去衣流程"""
        self.state_manager.update_user_state(user_id, States.CUSTOM_UNDRESS_WAITING_PHOTO)
    
    def set_photo_uploaded(self, user_id: int, file_id: str):
        """设置图片已上传"""
        self.state_manager.set_user_data(user_id, DataKeys.PHOTO_FILE_ID, file_id)
        self.state_manager.update_user_state(user_id, States.PHOTO_UPLOADED)
    
    def get_generation_params(self, user_id: int) -> Dict[str, Any]:
        """获取生成参数"""
        return self.state_manager.get_user_data(user_id, DataKeys.GENERATION_PARAMS, {})
    
    def set_generation_params(self, user_id: int, params: Dict[str, Any]):
        """设置生成参数"""
        self.state_manager.set_user_data(user_id, DataKeys.GENERATION_PARAMS, params)
    
    def set_cloth_selection(self, user_id: int, cloth_type: str):
        """设置服装选择"""
        self.state_manager.set_user_data(user_id, DataKeys.SELECTED_CLOTH, cloth_type)
    
    def get_cloth_selection(self, user_id: int) -> str:
        """获取服装选择"""
        return self.state_manager.get_user_data(user_id, DataKeys.SELECTED_CLOTH, "")
    
    def set_pose_selection(self, user_id: int, pose_index: int, pose_name: str):
        """设置姿势选择"""
        pose_data = {
            'index': pose_index,
            'name': pose_name
        }
        self.state_manager.set_user_data(user_id, DataKeys.SELECTED_POSE, pose_data)
    
    def get_pose_selection(self, user_id: int) -> Dict[str, Any]:
        """获取姿势选择"""
        return self.state_manager.get_user_data(user_id, DataKeys.SELECTED_POSE, {})
    
    def set_preferences(self, user_id: int, preferences: Dict[str, Any]):
        """设置用户偏好设置"""
        self.state_manager.set_user_data(user_id, DataKeys.PREFERENCES, preferences)
    
    def get_preferences(self, user_id: int) -> Dict[str, Any]:
        """获取用户偏好设置"""
        return self.state_manager.get_user_data(user_id, DataKeys.PREFERENCES, {})
    
    def set_user_preference(self, user_id: int, pref_type: str, value: str):
        """设置单个用户偏好"""
        self.state_manager.set_user_data(user_id, pref_type, value)
    
    def get_user_preference(self, user_id: int, pref_type: str, default: str = ""):
        """获取单个用户偏好"""
        return self.state_manager.get_user_data(user_id, pref_type, default)


# 状态常量
class States:
    """状态常量"""
    IDLE = "idle"
    
    # 图片上传相关
    PHOTO_UPLOADED = "photo_uploaded"
    WAITING_PHOTO = "waiting_photo"
    
    # 快速脱衣
    QUICK_UNDRESS_WAITING_PHOTO = "quick_undress_waiting_photo"
    QUICK_UNDRESS_CONFIRM = "quick_undress_confirm"
    
    # 自定义脱衣
    CUSTOM_UNDRESS_MENU = "custom_undress_menu"
    CUSTOM_UNDRESS_WAITING_PHOTO = "waiting_photo_for_custom_undress"
    CUSTOM_UNDRESS_CONFIRM = "custom_undress_confirm"
    
    # UID输入
    WAITING_UID_INPUT = "waiting_uid"


# 数据键常量
class DataKeys:
    """数据键常量"""
    PHOTO_FILE_ID = "photo_file_id"
    GENERATION_PARAMS = "generation_params"
    SELECTED_CLOTH = "selected_cloth"
    SELECTED_POSE = "selected_pose"
    PREFERENCES = "preferences"
    
    # 新增的偏好设置键
    BODY_TYPE = "body_type"
    BREAST_SIZE = "breast_size"
    BUTT_SIZE = "butt_size"
    AGE = "age" 