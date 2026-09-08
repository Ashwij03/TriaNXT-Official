CREATE TABLE IF NOT EXISTS ctms_ui_storage (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    storage_key VARCHAR(255) NOT NULL,
    value JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ctms_ui_storage_user_key UNIQUE (user_id, storage_key)
);
CREATE INDEX IF NOT EXISTS ix_ctms_ui_storage_user_id ON ctms_ui_storage(user_id);
CREATE INDEX IF NOT EXISTS ix_ctms_ui_storage_key ON ctms_ui_storage(storage_key);
