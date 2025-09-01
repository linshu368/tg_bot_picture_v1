"""
用户服务
负责用户管理和积分系统的核心业务逻辑

🔧 已迁移：服务仅依赖组合Repository（UserCompositeRepository/PointCompositeRepository）
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.utils.config.settings import CreditSettings


class UserService:
    """用户业务服务
    
    🔧 已迁移：仅依赖组合Repository
    """
    
    # 修改：精简构造参数，仅保留组合仓库
    # 目的：服务层与V2组合Repository完全适配，移除旧仓库/回退/并行验证
    def __init__(self, user_composite_repo=None, point_composite_repo=None,
                 credit_settings: CreditSettings = None):
        """
        初始化用户服务
        
        修改：仅支持组合Repository注入
        目的：统一跨表事务到组合仓库，实现最小Service层逻辑
        """
        self.credit_settings = credit_settings
        self.logger = logging.getLogger(__name__)
        
        # 修改：仅设置组合仓库
        # 目的：统一data access入口
        if not (user_composite_repo and point_composite_repo):
            raise ValueError("必须提供user_composite_repo和point_composite_repo")
        self.user_repo = user_composite_repo
        self.point_repo = point_composite_repo
        self.logger.info("🔧 使用组合Repository（已迁移）")
    
    
    async def register_user(self, telegram_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None) -> Optional[Dict[str, Any]]:
        """用户注册"""
        try:
            # 检查用户是否已存在
            existing_user = await self.user_repo.get_by_telegram_id(telegram_id)
            if existing_user:
                self.logger.info(f"用户已存在: {telegram_id}")
                return existing_user
            
            # 创建新用户
            user_data = {
                'telegram_id': telegram_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            }
            
            # 修改：统一走组合Repository注册（含默认积分发放）
            # 目的：将跨表逻辑下沉到UserCompositeRepository，保持对外返回不变
            user_data['default_credits'] = self.credit_settings.default_credits
            user = await self.user_repo.create(user_data)
            self.logger.info(f"用户注册成功（组合Repository）: {telegram_id}, uid: {user['uid']}")
            
            return user
            
        except Exception as e:
            self.logger.error(f"用户注册失败: {e}")
            return None
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """通过Telegram ID获取用户"""
        try:
            return await self.user_repo.get_by_telegram_id(telegram_id)
        except Exception as e:
            self.logger.error(f"通过Telegram ID获取用户失败: {e}")
            return None
    
    async def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """通过UID获取用户"""
        try:
            return await self.user_repo.get_by_uid(uid)
        except Exception as e:
            self.logger.error(f"通过UID获取用户失败: {e}")
            return None
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """通过用户ID获取用户"""
        try:
            return await self.user_repo.get_by_id(user_id)
        except Exception as e:
            self.logger.error(f"通过用户ID获取用户失败: {e}")
            return None
    
    async def bind_user_to_uid(self, telegram_id: int, uid: str) -> bool:
        """将Telegram账号绑定到指定UID（完整的账号恢复逻辑）"""
        try:
            # 1. 检查目标UID是否存在
            target_user = await self.user_repo.get_by_uid(uid)
            if not target_user:
                self.logger.warning(f"目标UID不存在: {uid}")
                return False
            
            # 2. 检查新telegram_id是否已有用户记录
            existing_user = await self.user_repo.get_by_telegram_id(telegram_id)
            
            if existing_user:
                if existing_user['uid'] == uid:
                    # 如果已经是同一个用户，直接返回成功
                    self.logger.info(f"用户 {telegram_id} 已绑定到 UID {uid}")
                    return True
                else:
                    # 如果是不同的用户，需要处理冲突
                    self.logger.info(f"检测到telegram_id {telegram_id} 已有用户记录，UID: {existing_user['uid']}")
                    
                    # 选择策略：删除新用户记录，保留目标UID的所有信息
                    # 这样可以确保用户完全继承目标UID的积分、等级、历史记录等
                    await self._handle_user_conflict(existing_user, target_user, telegram_id, uid)
            
            # 3. 更新目标用户的telegram_id
            result = await self.user_repo.update_telegram_id(uid, telegram_id)
            if result:
                self.logger.info(f"成功绑定用户 {telegram_id} 到 UID {uid}")
                # 更新用户的基本信息（用新的Telegram信息）
                await self._update_user_telegram_info(uid, telegram_id)
                return True
            else:
                self.logger.error(f"绑定用户失败: {telegram_id} -> {uid}")
                return False
                
        except Exception as e:
            self.logger.error(f"绑定用户到UID失败: {e}")
            return False
    
    async def _handle_user_conflict(self, existing_user: Dict[str, Any], target_user: Dict[str, Any], 
                                   telegram_id: int, uid: str):
        """处理用户冲突：保留目标UID的所有信息，删除冲突的用户记录"""
        try:
            existing_user_id = existing_user['id']
            
            # 如果现有用户有积分，记录一下（通常新注册用户积分很少，可以忽略）
            if existing_user['points'] > 0:
                self.logger.warning(f"删除用户记录时发现积分: {existing_user['points']}, user_id: {existing_user_id}")
            
            # 修改：删除冲突的用户记录（委托组合仓库执行，期望内部处理关联数据）
            # 目的：不再直接操作底层表，由组合仓库保证一致性
            await self.user_repo.delete(existing_user_id)
            
            # 修改：组合仓库模式下跳过手工清理相关表
            # 目的：由组合仓库在事务中完成级联或一致性处理
            
            self.logger.info(f"已删除冲突的用户记录: user_id={existing_user_id}, telegram_id={telegram_id}")
            
        except Exception as e:
            self.logger.error(f"处理用户冲突失败: {e}")
            raise
    
    async def _cleanup_user_related_data(self, user_id: int):
        """（组合仓库模式）相关数据清理由组合仓库内部处理，这里不再直接操作表"""
        self.logger.info(f"跳过手工清理用户相关数据（由组合仓库处理）：user_id={user_id}")
    
    async def _update_user_telegram_info(self, uid: str, telegram_id: int):
        """更新用户的Telegram信息（可选：从新的Telegram账号获取最新信息）"""
        try:
            # 这里可以选择是否更新用户的Telegram相关信息
            # 比如username, first_name, last_name等
            # 目前只更新最后活跃时间
            user = await self.user_repo.get_by_uid(uid)
            if user:
                await self.user_repo.update_last_active(user['id'])
                
        except Exception as e:
            self.logger.error(f"更新用户Telegram信息失败: {e}")
    
    async def add_points(self, user_id: int, points: int, action_type: str, 
                        description: str = None) -> bool:
        """增加用户积分"""
        try:
            # 修改：统一由PointCompositeRepository处理
            # 目的：由仓库封装余额计算与记录写入
            result = await self.point_repo.add_points(
                user_id, points, action_type, description
            )
            if result:
                self.logger.info(f"用户积分增加成功（组合Repository）: user_id={user_id}, points={points}")
            return result
                
        except Exception as e:
            self.logger.error(f"增加积分失败: {e}")
            return False
    
    async def consume_points(self, user_id: int, points: int, action_type: str,
                           description: str = None) -> bool:
        """消耗用户积分"""
        try:
            # 修改：统一由PointCompositeRepository处理
            # 目的：由仓库封装余额校验、扣减与记录写入
            result = await self.point_repo.subtract_points(
                user_id, points, action_type, description
            )
            if result:
                self.logger.info(f"用户积分消耗成功（组合Repository）: user_id={user_id}, points={points}")
            else:
                self.logger.warning(f"用户积分消耗失败（组合Repository）: user_id={user_id}, points={points}")
            return result
                
        except Exception as e:
            self.logger.error(f"消耗积分失败: {e}")
            return False
    
    async def check_points_sufficient(self, user_id: int, required_points: int) -> bool:
        """检查用户积分是否足够"""
        try:
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                return False
            return user['points'] >= required_points
        except Exception as e:
            self.logger.error(f"检查积分失败: {e}")
            return False
    
    async def get_user_points_balance(self, user_id: int) -> int:
        """获取用户积分余额"""
        try:
            user = await self.user_repo.get_by_id(user_id)
            return user['points'] if user else 0
        except Exception as e:
            self.logger.error(f"获取积分余额失败: {e}")
            return 0
    
    async def get_user_points_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户积分历史记录"""
        try:
            return await self.point_repo.get_user_records(user_id, limit)
        except Exception as e:
            self.logger.error(f"获取积分历史失败: {e}")
            return []
    
    async def daily_checkin(self, user_id: int) -> Dict[str, Any]:
        """每日签到"""
        try:
            # 修改：统一由UserCompositeRepository处理签到
            # 目的：由仓库内处理幂等与积分发放，Service做轻量适配
            result = await self.user_repo.daily_checkin(user_id)
            if result.get('success'):
                points_earned = result.get('data', {}).get('points_awarded', 0)
                return {
                    'success': True,
                    'message': result.get('message', '签到成功'),
                    'points_earned': points_earned
                }
            else:
                return {
                    'success': False,
                    'message': result.get('message', '签到失败'),
                    'points_earned': 0
                }
                
        except Exception as e:
            self.logger.error(f"签到失败: {e}")
            return {
                'success': False,
                'message': '签到失败，请稍后重试',
                'points_earned': 0
            }
    # （旧的签到辅助方法已移除）
    
    async def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户统计信息"""
        try:
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                return {}
            
            # 获取积分统计
            total_earned = await self.point_repo.get_user_total_earned(user_id)
            total_spent = await self.point_repo.get_user_total_spent(user_id)
            
            return {
                'user_id': user_id,
                'telegram_id': user['telegram_id'],
                'uid': user['uid'],
                'level': user['level'],
                'current_points': user['points'],
                'total_earned': total_earned,
                'total_spent': total_spent,
                'session_count': user.get('session_count', 0),
                'total_messages_sent': user.get('total_messages_sent', 0),
                'created_at': user['created_at'],
                'last_active_time': user.get('last_active_time')
            }
            
        except Exception as e:
            self.logger.error(f"获取用户统计失败: {e}")
            return {}
    
    async def update_user_activity(self, user_id: int):
        """更新用户活动状态"""
        try:
            await self.user_repo.update_last_active(user_id)
            await self.user_repo.increment_message_count(user_id)
        except Exception as e:
            self.logger.error(f"更新用户活动失败: {e}") 