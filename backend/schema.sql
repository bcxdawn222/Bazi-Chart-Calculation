CREATE TABLE IF NOT EXISTS charts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prayers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wishes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consultations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    openid TEXT NOT NULL UNIQUE,
    unionid TEXT,
    nickname TEXT NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS experts (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'offline',
    price_cents INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expert_schedules (
    id TEXT PRIMARY KEY,
    expert_id TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (expert_id) REFERENCES experts(id)
);

CREATE TABLE IF NOT EXISTS consultation_orders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expert_id TEXT,
    schedule_id TEXT,
    subject TEXT NOT NULL,
    amount_cents INTEGER,
    payment_status TEXT NOT NULL DEFAULT 'not_configured',
    prepay_id TEXT,
    transaction_id TEXT,
    paid_at TEXT,
    payment_notify_id TEXT,
    service_status TEXT NOT NULL DEFAULT 'pending',
    kind TEXT NOT NULL DEFAULT 'consultation',
    chart_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (expert_id) REFERENCES experts(id),
    FOREIGN KEY (schedule_id) REFERENCES expert_schedules(id)
);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    chart_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, chart_key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    rating INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'visible',
    created_at TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES consultation_orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS runtime_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    is_public INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_notifications (
    notify_id TEXT PRIMARY KEY,
    out_trade_no TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_charts_user ON charts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prayers_user ON prayers(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wishes_user ON wishes(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_user ON consultation_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON consultation_orders(payment_status, service_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_schedules_expert ON expert_schedules(expert_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_schedules_status ON expert_schedules(status, starts_at);
CREATE INDEX IF NOT EXISTS idx_experts_status ON experts(status, display_name);
