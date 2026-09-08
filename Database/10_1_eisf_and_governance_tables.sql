-- eISF repository + governance scaffolding tables (SQL-package parity)
-- ====================================================================
-- Ports the Alembic revision `e7c4b2a1d9f8_eisf_subject_history_governance`
-- (tria_engine/alembic/versions/) into the authoritative SQL package so a
-- fresh database built from this package matches the live FastAPI models.
--
--   eisf_document / eisf_documentversion   — eISF regulatory repository
--                                           (apps/eisf/models.py) + Part 11
--                                           version/audit rows.
--   ctms_complianceconfig / ctms_deviation / ctms_capa / ctms_auditevent /
--   ctms_riskrule / ctms_riskscore / ctms_riskevent  — governance scaffolding
--                                           (apps/ctms/models.py).
--
-- ctms_subject_status_history is intentionally NOT here — it already exists
-- in 01_core_domain.sql.
--
-- The ctms_* rows use the same JSON-mirror shape as 05_engine_json_compat.sql
-- (thin relational row + `data` JSONB) so SQL-level scope filtering and the
-- shared record layer behave identically to every other ctms_* table.
-- All statements are additive / idempotent (IF NOT EXISTS).
-- Safe to rerun.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. eISF document repository (mirrors apps/eisf/models.py)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS eisf_document (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS ix_eisf_document_code ON eisf_document(code);
CREATE INDEX IF NOT EXISTS ix_eisf_document_organization_id ON eisf_document(organization_id);
CREATE INDEX IF NOT EXISTS ix_eisf_document_study_id ON eisf_document(study_id);
CREATE INDEX IF NOT EXISTS ix_eisf_document_site_id ON eisf_document(site_id);

CREATE TABLE IF NOT EXISTS eisf_documentversion (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES eisf_document(id) ON DELETE CASCADE,
    code VARCHAR(64) NOT NULL,
    version VARCHAR(32) NOT NULL,
    signed_by VARCHAR(255) NOT NULL,
    signature_stamp VARCHAR(512) NOT NULL,
    signed_at TIMESTAMP,
    uploaded_by VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_eisf_documentversion_code ON eisf_documentversion(code);
CREATE INDEX IF NOT EXISTS ix_eisf_documentversion_document_id ON eisf_documentversion(document_id);

-- ---------------------------------------------------------------------------
-- 2. Governance scaffolding (mirrors apps/ctms/models.py)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ctms_complianceconfig (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);
CREATE INDEX IF NOT EXISTS ix_ctms_complianceconfig_code ON ctms_complianceconfig(code);
CREATE INDEX IF NOT EXISTS ix_ctms_complianceconfig_organization_id ON ctms_complianceconfig(organization_id);
CREATE INDEX IF NOT EXISTS ix_ctms_complianceconfig_study_id ON ctms_complianceconfig(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_complianceconfig_site_id ON ctms_complianceconfig(site_id);

CREATE TABLE IF NOT EXISTS ctms_deviation (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);
CREATE INDEX IF NOT EXISTS ix_ctms_deviation_code ON ctms_deviation(code);
CREATE INDEX IF NOT EXISTS ix_ctms_deviation_organization_id ON ctms_deviation(organization_id);
CREATE INDEX IF NOT EXISTS ix_ctms_deviation_study_id ON ctms_deviation(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_deviation_site_id ON ctms_deviation(site_id);

CREATE TABLE IF NOT EXISTS ctms_capa (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);
CREATE INDEX IF NOT EXISTS ix_ctms_capa_code ON ctms_capa(code);
CREATE INDEX IF NOT EXISTS ix_ctms_capa_organization_id ON ctms_capa(organization_id);
CREATE INDEX IF NOT EXISTS ix_ctms_capa_study_id ON ctms_capa(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_capa_site_id ON ctms_capa(site_id);

CREATE TABLE IF NOT EXISTS ctms_auditevent (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);
CREATE INDEX IF NOT EXISTS ix_ctms_auditevent_code ON ctms_auditevent(code);
CREATE INDEX IF NOT EXISTS ix_ctms_auditevent_organization_id ON ctms_auditevent(organization_id);
CREATE INDEX IF NOT EXISTS ix_ctms_auditevent_study_id ON ctms_auditevent(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_auditevent_site_id ON ctms_auditevent(site_id);

CREATE TABLE IF NOT EXISTS ctms_riskrule (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);
CREATE INDEX IF NOT EXISTS ix_ctms_riskrule_code ON ctms_riskrule(code);
CREATE INDEX IF NOT EXISTS ix_ctms_riskrule_organization_id ON ctms_riskrule(organization_id);
CREATE INDEX IF NOT EXISTS ix_ctms_riskrule_study_id ON ctms_riskrule(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_riskrule_site_id ON ctms_riskrule(site_id);

CREATE TABLE IF NOT EXISTS ctms_riskscore (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);
CREATE INDEX IF NOT EXISTS ix_ctms_riskscore_code ON ctms_riskscore(code);
CREATE INDEX IF NOT EXISTS ix_ctms_riskscore_organization_id ON ctms_riskscore(organization_id);
CREATE INDEX IF NOT EXISTS ix_ctms_riskscore_study_id ON ctms_riskscore(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_riskscore_site_id ON ctms_riskscore(site_id);

CREATE TABLE IF NOT EXISTS ctms_riskevent (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id VARCHAR(100),
    site_id VARCHAR(100),
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);
CREATE INDEX IF NOT EXISTS ix_ctms_riskevent_code ON ctms_riskevent(code);
CREATE INDEX IF NOT EXISTS ix_ctms_riskevent_organization_id ON ctms_riskevent(organization_id);
CREATE INDEX IF NOT EXISTS ix_ctms_riskevent_study_id ON ctms_riskevent(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_riskevent_site_id ON ctms_riskevent(site_id);

COMMIT;