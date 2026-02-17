-- Schema for conversation analysis pipeline (mirrors Alembic migration).
-- Used by sqlc for type-safe query codegen.

CREATE TABLE users (
    id VARCHAR(32) PRIMARY KEY,
    visitor_id VARCHAR(32),
    email VARCHAR(255),
    name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ,
    total_sessions INTEGER NOT NULL DEFAULT 0,
    total_bookings INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE UNIQUE INDEX ix_users_visitor_id ON users (visitor_id);

CREATE TABLE user_profiles (
    user_id VARCHAR(32) PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    company VARCHAR(255),
    domain VARCHAR(255),
    last_intent_type VARCHAR(32),
    booked_before BOOLEAN NOT NULL DEFAULT false,
    last_visit_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_sec INTEGER,
    booking_made BOOLEAN NOT NULL DEFAULT false,
    analysis_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    analysis_version INTEGER NOT NULL DEFAULT 1,
    r2_report_path VARCHAR(512),
    r2_audio_path VARCHAR(512),
    analysis_attempts INTEGER NOT NULL DEFAULT 0,
    last_analysis_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_sessions_user_id ON sessions (user_id);
CREATE INDEX ix_sessions_user_id_analysis_status ON sessions (user_id, analysis_status);

CREATE TABLE bookings (
    id VARCHAR(32) PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    user_id VARCHAR(32) NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    scheduled_time TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_bookings_user_id ON bookings (user_id);
CREATE INDEX ix_bookings_session_id ON bookings (session_id);

CREATE TABLE analysis_results (
    id VARCHAR(32) PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL UNIQUE REFERENCES sessions (id) ON DELETE CASCADE,
    sentiment_score DOUBLE PRECISION NOT NULL,
    engagement_score DOUBLE PRECISION NOT NULL,
    lead_score DOUBLE PRECISION NOT NULL,
    intent_label VARCHAR(64) NOT NULL,
    summary TEXT,
    analysis_version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_analysis_results_session_id ON analysis_results (session_id);
