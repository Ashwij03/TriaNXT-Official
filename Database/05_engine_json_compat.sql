BEGIN;
-- CURRENT FastAPI engine compatibility tables. These preserve the exact JSON
-- payload contract used by the gap routers while exposing study_id/site_id
-- columns for SQL-level scope filtering. They are intentionally separate from
-- the canonical normalized ctms_* domain tables.
CREATE TABLE IF NOT EXISTS ctms_amendment (
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
CREATE TABLE IF NOT EXISTS ctms_iplot (
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
CREATE TABLE IF NOT EXISTS ctms_irbsubmission (
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
CREATE TABLE IF NOT EXISTS ctms_icfversion (
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
CREATE TABLE IF NOT EXISTS ctms_consentevent (
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
CREATE TABLE IF NOT EXISTS ctms_reconsentcampaign (
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
CREATE TABLE IF NOT EXISTS ctms_vendor (
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
CREATE TABLE IF NOT EXISTS ctms_kit (
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
CREATE TABLE IF NOT EXISTS ctms_feasibilitycandidate (
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
CREATE TABLE IF NOT EXISTS ctms_feasibilityscoring (
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
CREATE TABLE IF NOT EXISTS ctms_safetyaecase (
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
CREATE TABLE IF NOT EXISTS ctms_monitoringrequest (
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
CREATE TABLE IF NOT EXISTS ctms_subject (
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
CREATE TABLE IF NOT EXISTS ctms_visit (
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
COMMIT;
