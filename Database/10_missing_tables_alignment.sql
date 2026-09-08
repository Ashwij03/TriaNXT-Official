-- CTMS Schema Alignment Migration
-- Adds the objects identified as RED / missing in the CTMS Schema Alignment Audit.
-- Safe to rerun: tables and columns use IF NOT EXISTS semantics.
--
-- Source: CTMS Schema Alignment Audit Report, especially pages 4, 6 and 11.
-- The three financial tables are intentionally minimal, extensible records because
-- the audit names the concepts but does not define a complete ER-column contract.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Organization / user RBAC gaps
-- ---------------------------------------------------------------------------

ALTER TABLE organizations_organization
    ADD COLUMN IF NOT EXISTS org_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS parent_org_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS address TEXT,
    ADD COLUMN IF NOT EXISTS country VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE organizations_role
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE accounts_user
    ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(150) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    resource VARCHAR(100),
    action VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES organizations_role(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES organizations_role(id) ON DELETE CASCADE,
    study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
    site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_roles_assignment
ON user_roles (
    user_id,
    role_id,
    COALESCE(study_id, 0),
    COALESCE(site_id, 0)
);

CREATE INDEX IF NOT EXISTS ix_organizations_parent
    ON organizations_organization(parent_org_id);

CREATE INDEX IF NOT EXISTS ix_user_roles_user
    ON user_roles(user_id);

CREATE INDEX IF NOT EXISTS ix_user_roles_role
    ON user_roles(role_id);

CREATE INDEX IF NOT EXISTS ix_user_roles_study
    ON user_roles(study_id);

CREATE INDEX IF NOT EXISTS ix_user_roles_site
    ON user_roles(site_id);

-- ---------------------------------------------------------------------------
-- 2. Financial concepts used by the frontend but missing from the SQL package
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ctms_invoices (
    invoice_id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
    site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
    invoice_number VARCHAR(100) NOT NULL UNIQUE,
    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    description TEXT,
    metadata JSONB,
    created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ctms_receivables (
    receivable_id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
    study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
    site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
    invoice_id BIGINT REFERENCES ctms_invoices(invoice_id) ON DELETE SET NULL,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    received_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    due_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ctms_subject_costs (
    subject_cost_id BIGSERIAL PRIMARY KEY,
    study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
    site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
    subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL,
    cost_type VARCHAR(100) NOT NULL,
    description TEXT,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    cost_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'POSTED',
    payment_id BIGINT REFERENCES ctms_payments(payment_id) ON DELETE SET NULL,
    metadata JSONB,
    created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ctms_invoices_study ON ctms_invoices(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_invoices_site ON ctms_invoices(site_id);
CREATE INDEX IF NOT EXISTS ix_ctms_invoices_status ON ctms_invoices(status);
CREATE INDEX IF NOT EXISTS ix_ctms_receivables_study ON ctms_receivables(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_receivables_invoice ON ctms_receivables(invoice_id);
CREATE INDEX IF NOT EXISTS ix_ctms_receivables_status ON ctms_receivables(status);
CREATE INDEX IF NOT EXISTS ix_ctms_subject_costs_study ON ctms_subject_costs(study_id);
CREATE INDEX IF NOT EXISTS ix_ctms_subject_costs_site ON ctms_subject_costs(site_id);
CREATE INDEX IF NOT EXISTS ix_ctms_subject_costs_subject ON ctms_subject_costs(subject_id);

-- ---------------------------------------------------------------------------
-- 3. Common reference tables identified as missing by the audit
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS study_status (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS site_status (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS visit_types (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS activity_types (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS document_types (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS issue_types (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS severity_levels (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS currencies (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS countries (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS timezones (
    code VARCHAR(100) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    utc_offset VARCHAR(10),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS system_configurations (
    config_key VARCHAR(150) PRIMARY KEY,
    config_value TEXT,
    description TEXT,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notification_templates (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(150) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    subject_template TEXT,
    body_template TEXT,
    channel VARCHAR(50) NOT NULL DEFAULT 'IN_APP',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
