"""
Supabase快照仓库
负责快照数据的增删改查操作
"""

import logging
from typing import List, Dict, Any, Optional


class SupabaseSnapshotRepository:
    """
    基于Supabase的快照仓库
    
    数据表：
    - snapshots: 存储快照数据
    - users: 存储用户与快照的关联关系
    """
    
    def __init__(self, supabase_manager):
        """
        初始化快照仓库
        
        Args:
            supabase_manager: Supabase管理器实例
        """
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        self.snapshots_table = "snapshots"
        self.users_table = "users"
    
    def insert(self, snapshot: Dict[str, Any]) -> bool:
        """
        保存快照到Supabase
        
        Args:
            snapshot: 快照数据字典，包含：
                - snapshot_id: 快照ID
                - user_id: 用户ID
                - role_id: 角色ID
                - name: 快照名称
                - model: 模型
                - system_prompt: 系统提示词
                - messages: 消息列表（JSONB）
                - created_at: 创建时间
        
        Returns:
            是否保存成功
        """
        try:
            user_id = snapshot.get("user_id")
            snapshot_id = snapshot.get("snapshot_id")
            
            if not user_id or not snapshot_id:
                self.logger.error("❌ 快照数据缺少必要字段: user_id 或 snapshot_id")
                return False
            
            client = self.supabase_manager.get_client()
            
            # 1) 插入快照数据到 snapshots 表
            snapshot_response = client.table(self.snapshots_table).insert(snapshot).execute()
            
            if not snapshot_response.data:
                self.logger.error(f"❌ 插入快照失败: snapshot_id={snapshot_id}")
                return False
            
            # 2) 更新 users 表的 snapshot_ids 数组
            # 先查询用户是否存在
            user_response = client.table(self.users_table).select("user_id, snapshot_ids").eq("user_id", user_id).execute()
            
            if user_response.data and len(user_response.data) > 0:
                # 用户存在，更新 snapshot_ids 数组
                existing_snapshot_ids = user_response.data[0].get("snapshot_ids", [])
                if snapshot_id not in existing_snapshot_ids:
                    existing_snapshot_ids.append(snapshot_id)
                    client.table(self.users_table).update({
                        "snapshot_ids": existing_snapshot_ids
                    }).eq("user_id", user_id).execute()
            else:
                # 用户不存在，创建新用户记录
                client.table(self.users_table).insert({
                    "user_id": user_id,
                    "snapshot_ids": [snapshot_id],
                    "created_at": snapshot.get("created_at")
                }).execute()
            
            self.logger.info(f"✅ 保存快照成功: snapshot_id={snapshot_id}, user_id={user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 保存快照失败: error={str(e)}")
            return False
    
    def list_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有快照
        
        Args:
            user_id: 用户ID
            
        Returns:
            快照列表
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 直接从 snapshots 表查询该用户的所有快照
            response = client.table(self.snapshots_table).select("*").eq("user_id", user_id).execute()
            
            if response.data:
                self.logger.info(f"✅ 获取用户快照成功: user_id={user_id}, 共 {len(response.data)} 个快照")
                return response.data
            else:
                self.logger.debug(f"ℹ️ 用户暂无快照: user_id={user_id}")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ 获取用户快照失败: user_id={user_id}, error={str(e)}")
            return []
    
    def get(self, user_id: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        获取特定快照（校验归属）
        
        Args:
            user_id: 用户ID
            snapshot_id: 快照ID
            
        Returns:
            快照数据，如果不存在或无权访问则返回None
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 查询快照并校验归属
            response = client.table(self.snapshots_table).select("*").eq("snapshot_id", snapshot_id).eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                self.logger.debug(f"✅ 获取快照成功: snapshot_id={snapshot_id}, user_id={user_id}")
                return response.data[0]
            else:
                self.logger.warning(f"⚠️ 快照不存在或无权访问: snapshot_id={snapshot_id}, user_id={user_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 获取快照失败: snapshot_id={snapshot_id}, error={str(e)}")
            return None
    
    def get_by_id(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        根据快照ID获取快照（不校验归属）
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            快照数据，如果不存在则返回None
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 查询快照
            response = client.table(self.snapshots_table).select("*").eq("snapshot_id", snapshot_id).execute()
            
            if response.data and len(response.data) > 0:
                self.logger.debug(f"✅ 获取快照成功: snapshot_id={snapshot_id}")
                return response.data[0]
            else:
                self.logger.warning(f"⚠️ 快照不存在: snapshot_id={snapshot_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 获取快照失败: snapshot_id={snapshot_id}, error={str(e)}")
            return None
    
    def delete(self, user_id: str, snapshot_id: str) -> bool:
        """
        删除快照
        
        Args:
            user_id: 用户ID
            snapshot_id: 快照ID
            
        Returns:
            是否删除成功
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 1) 先验证快照归属
            snapshot = self.get(user_id, snapshot_id)
            if not snapshot:
                self.logger.warning(f"⚠️ 快照不存在或无权删除: snapshot_id={snapshot_id}, user_id={user_id}")
                return False
            
            # 2) 从 snapshots 表删除快照
            delete_response = client.table(self.snapshots_table).delete().eq("snapshot_id", snapshot_id).eq("user_id", user_id).execute()
            
            if not delete_response.data:
                self.logger.error(f"❌ 删除快照失败: snapshot_id={snapshot_id}")
                return False
            
            # 3) 更新 users 表，从 snapshot_ids 数组中移除该快照ID
            user_response = client.table(self.users_table).select("snapshot_ids").eq("user_id", user_id).execute()
            
            if user_response.data and len(user_response.data) > 0:
                snapshot_ids = user_response.data[0].get("snapshot_ids", [])
                if snapshot_id in snapshot_ids:
                    snapshot_ids.remove(snapshot_id)
                    client.table(self.users_table).update({
                        "snapshot_ids": snapshot_ids
                    }).eq("user_id", user_id).execute()
            
            self.logger.info(f"✅ 删除快照成功: snapshot_id={snapshot_id}, user_id={user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 删除快照失败: snapshot_id={snapshot_id}, error={str(e)}")
            return False

