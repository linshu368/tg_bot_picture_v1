-- ======================
-- 主结构层
-- ======================
CREATE TABLE public.users_v2 (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    uid TEXT UNIQUE, -- 项目内部唯一标识 (u_xxx)
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    utm_source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
    -- updated_at 字段已删除
);

-- ======================
-- 行为记录层
-- ======================
CREATE TABLE public.user_sessions_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE,
    session_id TEXT UNIQUE
    -- current_action / session_data / expires_at 已删除
);

CREATE TABLE public.session_records_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE,
    session_id TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    message_count_user INT,
    duration_sec INT,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.user_action_records_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE,
    session_id TEXT,
    action_type TEXT,
    action_time TIMESTAMPTZ,
    parameters JSONB,
    message_context JSONB,  -- 修改为 JSONB
    status TEXT,
    result_url TEXT,
    error_message TEXT,
    action_id UUID DEFAULT gen_random_uuid() NOT NULL, -- 新增字段
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.payment_orders_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE,
    order_id TEXT UNIQUE,
    amount NUMERIC(12,2),
    status TEXT,
    payment_method TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    points_awarded INT,
    order_data JSONB
);

CREATE TABLE public.image_tasks_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE,
    task_id TEXT,
    task_type TEXT,
    status TEXT,
    input_image_url TEXT,
    output_image_url TEXT,
    webhook_url TEXT,
    api_response JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    points_cost INT
);

-- ======================
-- 用户状态层
-- ======================
CREATE TABLE public.daily_checkins_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE,
    checkin_date DATE,
    points_earned INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, checkin_date) -- 防止重复签到
);

CREATE TABLE public.point_records_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE,
    points_change INT,
    action_type TEXT,
    description TEXT,
    points_balance INT,
    related_event_id UUID, -- 改为 UUID 类型
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.user_wallet_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE UNIQUE,
    first_add BOOLEAN DEFAULT FALSE,
    points INT DEFAULT 0,
    total_paid_amount NUMERIC(12,2) DEFAULT 0,
    total_points_spent INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    level INT DEFAULT 1
);

CREATE TABLE public.user_activity_stats_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users_v2(id) ON DELETE CASCADE UNIQUE,
    session_count INT DEFAULT 0,
    total_messages_sent INT DEFAULT 0,
    first_active_time TIMESTAMPTZ,
    last_active_time TIMESTAMPTZ
);
