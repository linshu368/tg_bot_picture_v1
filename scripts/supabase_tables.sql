-- Supabase数据库表结构创建脚本
-- 请在Supabase控制台的SQL编辑器中执行此脚本

-- 1. 用户表
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

-- 创建用户表索引
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_uid ON users(uid);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- 2. 积分记录表
CREATE TABLE IF NOT EXISTS point_records (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    points_change INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    points_balance INTEGER DEFAULT 0
);

-- 创建积分记录表索引
CREATE INDEX IF NOT EXISTS idx_point_records_user_id ON point_records(user_id);
CREATE INDEX IF NOT EXISTS idx_point_records_created_at ON point_records(created_at);
CREATE INDEX IF NOT EXISTS idx_point_records_action_type ON point_records(action_type);

-- 3. 每日签到记录表
CREATE TABLE IF NOT EXISTS daily_checkins (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    checkin_date DATE NOT NULL,
    points_earned INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, checkin_date)
);

-- 创建每日签到表索引
CREATE INDEX IF NOT EXISTS idx_daily_checkins_user_id ON daily_checkins(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_checkins_date ON daily_checkins(checkin_date);

-- 4. 用户会话表
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

-- 创建用户会话表索引
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

-- 5. 支付订单表
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

-- 创建支付订单表索引
CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id ON payment_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_order_id ON payment_orders(order_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_status ON payment_orders(status);
CREATE INDEX IF NOT EXISTS idx_payment_orders_created_at ON payment_orders(created_at);

-- 6. 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id BIGSERIAL PRIMARY KEY,
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建系统配置表索引
CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(config_key);

-- 7. 会话记录表
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

-- 创建会话记录表索引
CREATE INDEX IF NOT EXISTS idx_session_records_user_id ON session_records(user_id);
CREATE INDEX IF NOT EXISTS idx_session_records_session_id ON session_records(session_id);
CREATE INDEX IF NOT EXISTS idx_session_records_started_at ON session_records(started_at);

-- 8. 用户行为记录表
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

-- 创建用户行为记录表索引
CREATE INDEX IF NOT EXISTS idx_user_action_records_user_id ON user_action_records(user_id);
CREATE INDEX IF NOT EXISTS idx_user_action_records_session_id ON user_action_records(session_id);
CREATE INDEX IF NOT EXISTS idx_user_action_records_action_type ON user_action_records(action_type);
CREATE INDEX IF NOT EXISTS idx_user_action_records_action_time ON user_action_records(action_time);

-- 9. 图像任务表
CREATE TABLE IF NOT EXISTS image_tasks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id TEXT UNIQUE NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    input_image_url TEXT,
    output_image_url TEXT,
    webhook_url TEXT,
    api_response JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    points_cost INTEGER DEFAULT 0
);

-- 创建图像任务表索引
CREATE INDEX IF NOT EXISTS idx_image_tasks_user_id ON image_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_image_tasks_task_id ON image_tasks(task_id);
CREATE INDEX IF NOT EXISTS idx_image_tasks_status ON image_tasks(status);
CREATE INDEX IF NOT EXISTS idx_image_tasks_created_at ON image_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_image_tasks_task_type ON image_tasks(task_type);

-- 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为相关表添加自动更新updated_at的触发器
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_sessions_updated_at 
    BEFORE UPDATE ON user_sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payment_orders_updated_at 
    BEFORE UPDATE ON payment_orders 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_config_updated_at 
    BEFORE UPDATE ON system_config 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_image_tasks_updated_at 
    BEFORE UPDATE ON image_tasks 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 完成提示
SELECT 'Supabase表结构创建完成！所有表和索引已成功创建。' as message; 