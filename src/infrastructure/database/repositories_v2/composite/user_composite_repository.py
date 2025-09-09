"""
用户组合Repository V2
负责用户相关的跨表操作 - 保持与旧版UserRepository接口兼容

主要职责：
1. 用户注册（users + wallet + stats + points）
2. 签到奖励（checkins + wallet + points）
3. 用户信息聚合查询
4. 保持与service层的接口兼容性
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from contextlib import asynccontextmanager

from src.infrastructure.database.repositories_v2.single.user_repository_v2 import UserRepositoryV2
from src.infrastructure.database.repositories_v2.single.user_wallet_repository_v2 import UserWalletRepositoryV2
from src.infrastructure.database.repositories_v2.single.user_activity_stats_repository_v2 import UserActivityStatsRepositoryV2
from src.infrastructure.database.repositories_v2.single.point_record_repository_v2 import PointRecordRepositoryV2
from src.infrastructure.database.repositories_v2.single.daily_checkin_repository_v2 import DailyCheckinRepositoryV2

from src.utils.config.app_config import DEFAULT_CREDITS, DAILY_SIGNIN_REWARD, DEFAULT_USER_LEVEL


class UserCompositeRepository:
    """用户组合Repository V2版本
    
    封装用户相关的跨表事务操作，对外提供与旧版UserRepository兼容的接口
    """
    
    def __init__(self, supabase_manager: Any):
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        
        # 初始化各个单表Repository
        self.user_repo = UserRepositoryV2(supabase_manager)
        self.wallet_repo = UserWalletRepositoryV2(supabase_manager)
        self.stats_repo = UserActivityStatsRepositoryV2(supabase_manager)
        self.point_repo = PointRecordRepositoryV2(supabase_manager)
        self.checkin_repo = DailyCheckinRepositoryV2(supabase_manager)
    
    def get_client(self) -> Any:
        """获取Supabase客户端"""
        return self.supabase_manager.get_client()
    
    @asynccontextmanager
    async def _transaction(self):
        """简单的事务管理上下文（后续可扩展为真正的DB事务）"""
        rollback_actions: List[Any] = []
        self.logger.debug("事务开始")
        try:
            yield rollback_actions
            self.logger.debug("事务成功完成")
        except Exception as e:
            self.logger.warning(f"事务异常，开始回滚: {e}")
            for action in reversed(rollback_actions):
                try:
                    await action()
                    self.logger.debug("回滚操作成功")
                except Exception as rollback_error:
                    self.logger.error(f"回滚操作失败: {rollback_error}")
            raise e
    
    def _standardize_error_response(self, success: bool = False, message: str = "", data: Any = None) -> Dict[str, Any]:
        """标准化错误响应格式"""
        return {
            'success': success,
            'message': message,
            'data': data
        }
    
    # ==================== 保持兼容的核心接口 ====================
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户（完整注册流程）"""
        async with self._transaction() as rollback_actions:
            self.logger.info(f"开始用户注册流程: telegram_id={data.get('telegram_id')}")
            try:
                # 1. 创建用户基础信息
                user = await self.user_repo.create(data)
                user_id = user['id']
                rollback_actions.append(lambda: self.user_repo.delete(user_id))
                
                # 2/3. 串行初始化钱包与统计（减少并发连接数）
                default_points = data.get('default_credits', DEFAULT_CREDITS)
                current_time = datetime.utcnow().isoformat()
                wallet_data = {
                    'user_id': user_id,
                    'points': default_points,
                    'first_add': False,
                    'total_paid_amount': 0.0,
                    'total_points_spent': 0,
                    'level': DEFAULT_USER_LEVEL
                }
                stats_data = {
                    'user_id': user_id,
                    'session_count': 0,
                    'total_messages_sent': 0,
                    'first_active_time': current_time,
                    'last_active_time': current_time
                }
                # 改为串行操作，减少并发连接数
                wallet = await self.wallet_repo.create(wallet_data)
                stats = await self.stats_repo.create(stats_data)
                rollback_actions.append(lambda: self.wallet_repo.delete_by_user_id(user_id))
                rollback_actions.append(lambda: self.stats_repo.delete_by_user_id(user_id))
                
                # 4. 积分流水（与上一步无强依赖，可并发触发，但不阻塞返回）
                if default_points > 0:
                    async def _background_registration_points():
                        try:
                            point_record_data = {
                                'user_id': user_id,
                                'points_change': default_points,
                                'action_type': 'registration',
                                'description': '新用户注册奖励',
                                'points_balance': default_points,
                                'related_event_id': str(uuid.uuid4())
                            }
                            await self.point_repo.create(point_record_data)
                        except Exception as bg_err:
                            self.logger.error(f"注册积分流水记录失败(后台): {bg_err}")
                    try:
                        asyncio.create_task(_background_registration_points())
                    except Exception as schedule_err:
                        self.logger.error(f"调度注册积分流水后台任务失败: {schedule_err}")
                
                user_result = {
                    **user,
                    'points': wallet['points'],
                    'level': wallet['level'],
                    'session_count': 0,
                    'total_messages_sent': 0
                }
                
                self.logger.info(f"用户注册成功: user_id={user_id}, uid={user['uid']}")
                return user_result
            
            except Exception as e:
                self.logger.error(f"创建用户失败: {e}")
                return self._standardize_error_response(message="用户创建失败")
    
    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户完整信息（聚合多表数据）"""
        try:
            # 串行获取各表数据（减少并发连接数）
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                return None
            
            wallet = await self.wallet_repo.get_by_user_id(user_id)
            stats = await self.stats_repo.get_by_user_id(user_id)
            
            # 聚合数据，单表Repository已处理字段映射
            return {
                **user,
                **(wallet or {}),  # 钱包数据（包含points字段）
                **(stats or {}),   # 统计数据（包含session_count等）
            }
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            return None
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """根据Telegram ID获取用户完整信息"""
        try:
            user = await self.user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return None
            return await self.get_by_id(user['id'])
        except Exception as e:
            self.logger.error(f"根据Telegram ID获取用户失败: {e}")
            return None
    
    async def get_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """根据UID获取用户完整信息"""
        try:
            user = await self.user_repo.get_by_uid(uid)
            if not user:
                return None
            return await self.get_by_id(user['id'])
        except Exception as e:
            self.logger.error(f"根据UID获取用户失败: {e}")
            return None
    
    async def update(self, user_id: int, data: Dict[str, Any]) -> bool:
        """更新用户信息（智能分发到对应的表）"""
        try:
            success = True
            
            # 用户基础信息字段
            user_fields = {'username', 'first_name', 'last_name', 'is_active', 'utm_source'}
            user_data = {k: v for k, v in data.items() if k in user_fields}
            if user_data:
                success &= await self.user_repo.update(user_id, user_data)
            
            # 钱包相关字段
            wallet_fields = {'points', 'level', 'first_add', 'total_paid_amount', 'total_points_spent'}
            wallet_data = {k: v for k, v in data.items() if k in wallet_fields}
            if wallet_data:
                success &= await self.wallet_repo.update_by_user_id(user_id, wallet_data)
            
            return success
        except Exception as e:
            self.logger.error(f"更新用户信息失败: {e}")
            return False
    
    async def delete(self, user_id: int) -> bool:
        try:
            return await self.user_repo.update(user_id, {'is_active': False})
        except Exception as e:
            self.logger.error(f"删除用户失败: {e}")
            return False
    
    # ==================== 兼容旧版的业务方法 ====================
    
    async def update_telegram_id(self, uid: str, telegram_id: int) -> bool:
        try:
            user = await self.user_repo.get_by_uid(uid)
            if not user:
                return False
            return await self.user_repo.update(user['id'], {'telegram_id': telegram_id})
        except Exception as e:
            self.logger.error(f"更新Telegram ID失败: {e}")
            return False
    
    async def daily_checkin(self, user_id: int) -> Dict[str, Any]:
        """用户每日签到（超优化版：最小化同步操作）"""
        today = date.today()
        try:
            # 1. 快速检查是否已签到（仅此操作同步）
            existing = await self.checkin_repo.get_by_user_id_and_date(user_id, today)
            if existing:
                return self._standardize_error_response(False, "今日已签到")

            # 2. 立即返回成功结果，所有数据库操作移到后台
            # 这样可以实现真正的快速响应
            result = self._standardize_error_response(True, "签到成功", {
                'user_id': user_id,
                'points_awarded': DAILY_SIGNIN_REWARD,
                'total_points': 0  # 临时值，后台会更新
            })

            # 3. 后台执行所有数据库操作
            async def _background_checkin_operations():
                try:
                    async with self._transaction() as rollback_actions:
                        # 创建签到记录
                        checkin = await self.checkin_repo.create({
                            'user_id': user_id,
                            'checkin_date': today.isoformat(),
                            'points_earned': DAILY_SIGNIN_REWARD
                        })
                        rollback_actions.append(lambda: self.checkin_repo.delete(checkin['id']))

                        # 增加钱包积分
                        success = await self.wallet_repo.add_points(user_id, DAILY_SIGNIN_REWARD)
                        if not success:
                            raise Exception("增加钱包积分失败")

                        # 获取更新后的钱包信息
                        wallet = await self.wallet_repo.get_by_user_id(user_id)
                        if not wallet:
                            raise Exception("获取更新后的钱包信息失败")

                        # 创建积分流水记录
                        await self.point_repo.create({
                            'user_id': user_id,
                            'points_change': DAILY_SIGNIN_REWARD,
                            'action_type': 'daily_checkin',
                            'description': '每日签到奖励',
                            'points_balance': wallet['points'],
                            'related_event_id': str(uuid.uuid4())
                        })

                        self.logger.info(f"每日签到后台操作完成: user_id={user_id}, points={DAILY_SIGNIN_REWARD}")
                        
                except Exception as bg_err:
                    self.logger.error(f"每日签到后台操作失败: {bg_err}")

            # 启动后台任务
            try:
                asyncio.create_task(_background_checkin_operations())
            except Exception as schedule_err:
                self.logger.error(f"调度每日签到后台任务失败: {schedule_err}")

            # 立即返回结果
            return result
            
        except Exception as e:
            self.logger.error(f"用户签到失败: {e}")
            return self._standardize_error_response(False, "签到失败")

    
    async def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户完整档案信息"""
        try:
            user = await self.get_by_id(user_id)
            if not user:
                return None
            # 可拓展聚合更多统计信息
            return user
        except Exception as e:
            self.logger.error(f"获取用户档案失败: {e}")
            return None

    
    # ==================== 查询方法 ====================
    
    async def find_many(self, limit: int = None, offset: int = None, **conditions) -> List[Dict[str, Any]]:
        """查询多个用户（聚合查询，包含钱包和统计信息）"""
        try:
            # 先获取基础用户信息
            users = await self.user_repo.find_many(limit=limit, **conditions)
            
            # 批量获取钱包和统计信息（优化性能）
            user_ids = [user['id'] for user in users]
            if not user_ids:
                return []
            
            # 并行获取所有用户的钱包和统计信息
            wallets = {}
            stats = {}
            
            # 这里可以进一步优化为批量查询
            for user_id in user_ids:
                wallet = await self.wallet_repo.get_by_user_id(user_id)
                stat = await self.stats_repo.get_by_user_id(user_id)
                if wallet:
                    wallets[user_id] = wallet
                if stat:
                    stats[user_id] = stat
            
            # 聚合数据
            enriched_users = []
            for user in users:
                user_id = user['id']
                enriched_user = {
                    **user,
                    **(wallets.get(user_id, {})),  # 钱包数据（已映射字段）
                    **(stats.get(user_id, {})),    # 统计数据（已映射字段）
                }
                enriched_users.append(enriched_user)
            
            return enriched_users
        except Exception as e:
            self.logger.error(f"查询用户失败: {e}")
            return []
    
    async def find_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """查找单个用户（与旧版UserRepository接口完全一致）"""
        try:
            # 先获取基础用户信息
            user = await self.user_repo.find_one(**conditions)
            if not user:
                return None
            
            # 聚合钱包和统计信息
            user_id = user['id']
            wallet = await self.wallet_repo.get_by_user_id(user_id)
            stats = await self.stats_repo.get_by_user_id(user_id)
            
            return {
                **user,
                **(wallet or {}),  # 钱包数据（已映射字段）
                **(stats or {}),   # 统计数据（已映射字段）
            }
        except Exception as e:
            self.logger.error(f"查找用户失败: {e}")
            return None
    
    async def exists(self, **conditions) -> bool:
        """检查用户是否存在"""
        try:
            return await self.user_repo.exists(**conditions)
        except Exception as e:
            self.logger.error(f"检查用户存在失败: {e}")
            return False 