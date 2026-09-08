-- Part 11 electronic signature ledger (Task 4.1)
-- ===============================================
-- One row per completed electronic signature (21 CFR Part 11 audit trail).
-- Mirrors apps/eisf/models.py's ESignature model exactly. The row is
-- immutable once written.
--
-- Note: the multi-signer workflow tables (ctms_signature_requests /
-- ctms_signature_request_signers) already exist in
-- 03_operations_governance.sql and are NOT recreated here.
-- Safe to rerun (IF NOT EXISTS).

BEGIN;

CREATE TABLE IF NOT EXISTS ctms_electronic_signature (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT,
    document_code VARCHAR(64) NOT NULL,
    document_type VARCHAR(50) NOT NULL DEFAULT 'eisf',
    signer_user_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
    signer_name VARCHAR(255) NOT NULL,
    signer_role VARCHAR(50) NOT NULL DEFAULT '',
    meaning VARCHAR(50) NOT NULL DEFAULT 'approval',
    signature_stamp VARCHAR(512) NOT NULL DEFAULT '',
    signed_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_ctms_electronic_signature_document_code ON ctms_electronic_signature(document_code);
CREATE INDEX IF NOT EXISTS ix_ctms_electronic_signature_document_id ON ctms_electronic_signature(document_id);
CREATE INDEX IF NOT EXISTS ix_ctms_electronic_signature_signer_user_id ON ctms_electronic_signature(signer_user_id);

COMMIT;