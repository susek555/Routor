-- 1. USERS
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);


-- 2. USER_DEVICES
CREATE TABLE IF NOT EXISTS user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fcm_token VARCHAR(512) UNIQUE NOT NULL,
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_user_devices_user_id ON user_devices (user_id);


-- 3. ROUTE_VARIANTS
CREATE TABLE IF NOT EXISTS route_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id VARCHAR(64) NOT NULL,
    variant_index SMALLINT NOT NULL,
    distance_meters INTEGER NOT NULL,
    fitness_score DOUBLE PRECISION NOT NULL,
    geojson JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

-- Indices for downloading route variants by task, and for expiring old variants
CREATE INDEX IF NOT EXISTS ix_route_variants_task_id ON route_variants (task_id);
CREATE INDEX IF NOT EXISTS ix_route_variants_expires_at ON route_variants (expires_at);


-- 4. ROUTE_RATINGS
CREATE TABLE IF NOT EXISTS route_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    rating SMALLINT NULL,
    was_completed BOOLEAN NOT NULL DEFAULT FALSE,
    features JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_route_ratings_user_id ON route_ratings (user_id);


-- -- 5. USER_MODELS
-- CREATE TABLE IF NOT EXISTS user_models (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     user_id UUID REFERENCES users(id) ON DELETE CASCADE,
--     file_path VARCHAR(255) NOT NULL,
--     training_samples_count INTEGER NOT NULL DEFAULT 0,
--     updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     CONSTRAINT uq_user_models_user_id UNIQUE NULLS NOT DISTINCT (user_id)
-- );

-- -- Base model
-- INSERT INTO user_models (user_id, file_path, training_samples_count)
-- VALUES (
--     NULL,
--     '/app/ml_models/global_weights.pt',
--     0
-- )
-- ON CONFLICT (user_id) DO NOTHING;