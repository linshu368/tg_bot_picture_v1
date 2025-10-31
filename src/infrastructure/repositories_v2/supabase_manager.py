"""
Supabase数据库管理器
负责Supabase连接管理和基础操作
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from src.utils.config.settings import DatabaseSettings


class SupabaseManager:
    """Supabase数据库管理器"""
    
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self._client: Optional[Client] = None
        
    async def initialize(self):
        """初始化Supabase客户端"""
        try:
            self.logger.info("初始化Supabase连接")
            
            if not self.settings.supabase_url or not self.settings.supabase_key:
                raise ValueError("Supabase URL和Key不能为空")
            
            # 创建Supabase客户端
            self._client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_key
            )
            
            # 测试连接
            await self._test_connection()
            
            self.logger.info("Supabase连接初始化完成")
            
        except Exception as e:
            self.logger.error(f"Supabase初始化失败: {e}")
            raise
    
    async def close(self):
        """关闭连接（Supabase客户端无需显式关闭）"""
        self.logger.info("Supabase连接已释放")
    
    def get_client(self) -> Client:
        """获取Supabase客户端"""
        self.logger.info(f"[SupabaseManager] 开始 get_client()")
        if not self._client:
            self.logger.error(f"[SupabaseManager] 客户端未初始化")
            raise RuntimeError("Supabase客户端未初始化")
        self.logger.info(f"[SupabaseManager] 返回客户端实例")
        return self._client
    
    def get_beijing_time(self, dt: datetime = None) -> datetime:
        """获取北京时间"""
        if dt is None:
            dt = datetime.utcnow()
        beijing_time = dt.replace(tzinfo=timezone.utc).astimezone(
            timezone(timedelta(hours=8))
        )
        return beijing_time
    
    async def _test_connection(self):
        """测试Supabase连接"""
        try:
            # 尝试查询一个简单的系统表来测试连接
            # 使用 rpc 调用一个简单的函数来测试连接
            result = self._client.rpc('version').execute()
            self.logger.info("Supabase连接测试成功")
        except Exception as e:
            # 如果 rpc 不可用，尝试简单的表查询
            try:
                # 尝试查询一个不存在的表，如果连接正常会返回表不存在的错误
                result = self._client.table('test_connection_table').select('*').limit(1).execute()
            except Exception as e2:
                # 如果错误信息包含表不存在，说明连接是正常的
                if "does not exist" in str(e2).lower() or "not found" in str(e2).lower():
                    self.logger.info("Supabase连接测试成功")
                else:
                    self.logger.error(f"Supabase连接测试失败: {e2}")
                    raise e2
    
    #待注释
    async def create_tables(self):
        """创建数据库表结构（通过SQL执行）"""
        try:
            # 注意：在实际使用中，表结构应该通过Supabase控制台或迁移脚本创建
            # 这里只是为了演示如何执行SQL
            sql_statements = [
                self._get_users_table_sql(),
                self._get_point_records_table_sql(),
                self._get_daily_checkins_table_sql(),
                self._get_user_sessions_table_sql(),
                self._get_payment_orders_table_sql(),
                self._get_system_config_table_sql(),
                self._get_session_records_table_sql(),
                self._get_user_action_records_table_sql()
            ]
            
            for sql in sql_statements:
                # 注意：实际项目中建议通过Supabase Dashboard或CLI创建表
                self.logger.info(f"表结构SQL（请手动执行）:\n{sql}")
            
            self.logger.info("请在Supabase控制台手动创建上述表结构")
            
        except Exception as e:
            self.logger.error(f"获取表结构失败: {e}")
            raise
    
    def _get_users_table_sql(self) -> str:
        """用户表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            uid TEXT UNIQUE NOT NULL,
            points INTEGER DEFAULT 50,
            level INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            session_count INTEGER DEFAULT 0,
            total_points_spent INTEGER DEFAULT 0,
            total_paid_amount DECIMAL DEFAULT 0.0,
            first_add BOOLEAN DEFAULT false,
            utm_source TEXT DEFAULT '000',
            first_active_time TIMESTAMPTZ,
            last_active_time TIMESTAMPTZ,
            total_messages_sent INTEGER DEFAULT 0
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_users_uid ON users(uid);
        CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
        """
    
    def _get_point_records_table_sql(self) -> str:
        """积分记录表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS point_records (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            points_change INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            points_balance INTEGER DEFAULT 0
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_point_records_user_id ON point_records(user_id);
        CREATE INDEX IF NOT EXISTS idx_point_records_created_at ON point_records(created_at);
        CREATE INDEX IF NOT EXISTS idx_point_records_action_type ON point_records(action_type);
        """
    
    def _get_daily_checkins_table_sql(self) -> str:
        """每日签到记录表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS daily_checkins (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            checkin_date DATE NOT NULL,
            points_earned INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, checkin_date)
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_daily_checkins_user_id ON daily_checkins(user_id);
        CREATE INDEX IF NOT EXISTS idx_daily_checkins_date ON daily_checkins(checkin_date);
        """
    
    def _get_user_sessions_table_sql(self) -> str:
        """用户会话表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id TEXT UNIQUE NOT NULL,
            current_action TEXT,
            session_data JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
        """
    
    def _get_payment_orders_table_sql(self) -> str:
        """支付订单表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS payment_orders (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            order_id TEXT UNIQUE NOT NULL,
            amount DECIMAL NOT NULL,
            status TEXT DEFAULT 'pending',
            payment_method TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            paid_at TIMESTAMPTZ,
            points_awarded INTEGER DEFAULT 0,
            order_data JSONB DEFAULT '{}'
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id ON payment_orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_payment_orders_order_id ON payment_orders(order_id);
        CREATE INDEX IF NOT EXISTS idx_payment_orders_status ON payment_orders(status);
        CREATE INDEX IF NOT EXISTS idx_payment_orders_created_at ON payment_orders(created_at);
        """
    
    def _get_system_config_table_sql(self) -> str:
        """系统配置表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS system_config (
            id BIGSERIAL PRIMARY KEY,
            config_key TEXT UNIQUE NOT NULL,
            config_value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(config_key);
        """
    
    def _get_session_records_table_sql(self) -> str:
        """会话记录表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS session_records (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            message_count_user INTEGER DEFAULT 0,
            duration_sec INTEGER,
            summary TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_session_records_user_id ON session_records(user_id);
        CREATE INDEX IF NOT EXISTS idx_session_records_session_id ON session_records(session_id);
        CREATE INDEX IF NOT EXISTS idx_session_records_started_at ON session_records(started_at);
        """
    
    def _get_user_action_records_table_sql(self) -> str:
        """用户行为记录表SQL"""
        return """
        CREATE TABLE IF NOT EXISTS user_action_records (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_time TIMESTAMPTZ NOT NULL,
            parameters JSONB DEFAULT '{}',
            message_context TEXT,
            status TEXT DEFAULT 'success',
            points_cost INTEGER DEFAULT 0,
            result_url TEXT,
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_user_action_records_user_id ON user_action_records(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_action_records_session_id ON user_action_records(session_id);
        CREATE INDEX IF NOT EXISTS idx_user_action_records_action_type ON user_action_records(action_type);
        CREATE INDEX IF NOT EXISTS idx_user_action_records_action_time ON user_action_records(action_time);
        """ 