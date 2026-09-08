BEGIN;
CREATE TABLE IF NOT EXISTS ctms_amendments (
 amendment_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 amendment_number VARCHAR(50) NOT NULL, version VARCHAR(50), classification VARCHAR(50), title VARCHAR(500) NOT NULL, summary TEXT,
 effective_date DATE, status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', re_consent_required BOOLEAN NOT NULL DEFAULT FALSE,
 binder_update_required BOOLEAN NOT NULL DEFAULT FALSE, training_required BOOLEAN NOT NULL DEFAULT FALSE, irb_submission_ref VARCHAR(100),
 impacted_site_codes JSONB, history JSONB, created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(study_id,amendment_number)
);
CREATE TABLE IF NOT EXISTS ctms_amendment_site_tasks (
 amendment_site_task_id BIGSERIAL PRIMARY KEY, amendment_id BIGINT NOT NULL REFERENCES ctms_amendments(amendment_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, site_code VARCHAR(100) NOT NULL, task_id VARCHAR(100) NOT NULL,
 task_name VARCHAR(500), status VARCHAR(50), completed_at TIMESTAMPTZ, completed_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 UNIQUE(amendment_id,site_code,task_id)
);
CREATE TABLE IF NOT EXISTS ctms_irb_submissions (
 submission_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, submission_number VARCHAR(50) NOT NULL, submission_type VARCHAR(50) NOT NULL,
 title VARCHAR(500), committee VARCHAR(255), linked_ref VARCHAR(100), review_cycle_months INTEGER, status VARCHAR(50) DEFAULT 'PREPARING',
 submitted_date DATE, decision_date DATE, decision_note TEXT, conditions JSONB, correspondence JSONB,
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(study_id,submission_number)
);
CREATE TABLE IF NOT EXISTS ctms_icf_versions (
 icf_version_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE, language VARCHAR(100) NOT NULL DEFAULT 'English', version VARCHAR(50) NOT NULL,
 amendment_id BIGINT REFERENCES ctms_amendments(amendment_id) ON DELETE SET NULL, witness_required BOOLEAN NOT NULL DEFAULT FALSE,
 status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', document_id BIGINT REFERENCES ctms_documents(document_id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(site_id,version)
);
CREATE TABLE IF NOT EXISTS ctms_consent_events (
 consent_event_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, subject_id BIGINT NOT NULL REFERENCES ctms_subjects(subject_id) ON DELETE CASCADE,
 icf_version_id BIGINT NOT NULL REFERENCES ctms_icf_versions(icf_version_id) ON DELETE RESTRICT, consent_date DATE NOT NULL,
 method VARCHAR(50), witness VARCHAR(255), status VARCHAR(50) DEFAULT 'CONSENTED', consent_form_document_id BIGINT REFERENCES ctms_documents(document_id) ON DELETE SET NULL,
 captured_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_reconsent_campaigns (
 campaign_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 amendment_id BIGINT REFERENCES ctms_amendments(amendment_id) ON DELETE SET NULL, icf_version_id BIGINT REFERENCES ctms_icf_versions(icf_version_id) ON DELETE SET NULL,
 reason TEXT, status VARCHAR(50) DEFAULT 'PLANNED', due_date DATE, created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_reconsent_subjects (
 campaign_subject_id BIGSERIAL PRIMARY KEY, campaign_id BIGINT NOT NULL REFERENCES ctms_reconsent_campaigns(campaign_id) ON DELETE CASCADE,
 subject_id BIGINT NOT NULL REFERENCES ctms_subjects(subject_id) ON DELETE CASCADE, status VARCHAR(50) DEFAULT 'PENDING', completed_at TIMESTAMPTZ,
 UNIQUE(campaign_id,subject_id)
);
CREATE TABLE IF NOT EXISTS ctms_ip_lots (
 lot_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE, lot_number VARCHAR(100) NOT NULL, kit_number VARCHAR(100),
 quantity_received INTEGER NOT NULL DEFAULT 0, quantity_on_hand INTEGER NOT NULL DEFAULT 0, status VARCHAR(50) DEFAULT 'SHIPPED', condition VARCHAR(50),
 received_at TIMESTAMPTZ, received_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, reconciliation_status VARCHAR(50) DEFAULT 'UNDER_INVESTIGATION',
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(study_id,site_id,lot_number)
);
CREATE TABLE IF NOT EXISTS ctms_ip_transactions (
 transaction_id BIGSERIAL PRIMARY KEY, lot_id BIGINT NOT NULL REFERENCES ctms_ip_lots(lot_id) ON DELETE CASCADE,
 subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL, visit_code VARCHAR(100), transaction_type VARCHAR(50) NOT NULL,
 quantity INTEGER NOT NULL, reason TEXT, witness VARCHAR(255), created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_ip_shipments (
 shipment_id BIGSERIAL PRIMARY KEY, lot_id BIGINT NOT NULL REFERENCES ctms_ip_lots(lot_id) ON DELETE CASCADE,
 from_site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, to_site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
 tracking_number VARCHAR(100), quantity INTEGER NOT NULL DEFAULT 0, status VARCHAR(50) DEFAULT 'IN_TRANSIT', shipped_at TIMESTAMPTZ, received_at TIMESTAMPTZ, notes TEXT
);
CREATE TABLE IF NOT EXISTS ctms_ip_excursions (
 excursion_id BIGSERIAL PRIMARY KEY, lot_id BIGINT NOT NULL REFERENCES ctms_ip_lots(lot_id) ON DELETE CASCADE,
 excursion_type VARCHAR(50), min_temp NUMERIC(6,2), max_temp NUMERIC(6,2), duration_minutes INTEGER,
 detected_at TIMESTAMPTZ NOT NULL DEFAULT now(), disposition VARCHAR(50) DEFAULT 'PENDING', disposition_reason TEXT,
 disposition_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, notes TEXT
);
CREATE TABLE IF NOT EXISTS ctms_vendors (
 vendor_id BIGSERIAL PRIMARY KEY, organization_id BIGINT NOT NULL REFERENCES organizations_organization(id) ON DELETE RESTRICT,
 name VARCHAR(255) NOT NULL, vendor_type VARCHAR(100), scope VARCHAR(500), contract_ref VARCHAR(100), contract_expiry_date DATE,
 contact_name VARCHAR(255), contact_email VARCHAR(320), contact_phone VARCHAR(50), status VARCHAR(50) DEFAULT 'ONBOARDING', notes TEXT, history JSONB,
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_vendor_contracts (
 contract_id BIGSERIAL PRIMARY KEY, vendor_id BIGINT NOT NULL REFERENCES ctms_vendors(vendor_id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, contract_number VARCHAR(100) NOT NULL, title VARCHAR(500), amount NUMERIC(18,2),
 currency VARCHAR(10) DEFAULT 'USD', start_date DATE, end_date DATE, status VARCHAR(50) DEFAULT 'ACTIVE', document_id BIGINT REFERENCES ctms_documents(document_id) ON DELETE SET NULL,
 UNIQUE(vendor_id,contract_number)
);
CREATE TABLE IF NOT EXISTS ctms_vendor_kits (
 kit_id BIGSERIAL PRIMARY KEY, vendor_id BIGINT NOT NULL REFERENCES ctms_vendors(vendor_id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL,
 visit_code VARCHAR(100), kit_type VARCHAR(100) NOT NULL, specimen_id VARCHAR(100), collected_location VARCHAR(100), status VARCHAR(50) DEFAULT 'COLLECTED',
 location VARCHAR(255), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_feasibility_candidates (
 candidate_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, institution VARCHAR(255) NOT NULL, contact_name VARCHAR(255), email VARCHAR(320), phone VARCHAR(50),
 department VARCHAR(100), status VARCHAR(50) DEFAULT 'IDENTIFIED', sent_date DATE, response_date DATE, response_submitted_at TIMESTAMPTZ,
 questionnaire JSONB, scores JSONB, score NUMERIC(6,2), min_score_required NUMERIC(6,2), rationale TEXT, decided_at TIMESTAMPTZ, converted BOOLEAN DEFAULT FALSE,
 notes TEXT, history JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(study_id,institution)
);
CREATE TABLE IF NOT EXISTS ctms_feasibility_scoring (
 scoring_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL UNIQUE REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 criteria JSONB NOT NULL, min_score NUMERIC(6,2), updated_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_adverse_events (
 ae_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL,
 case_number VARCHAR(100) NOT NULL UNIQUE, ae_type VARCHAR(50), severity VARCHAR(50), causality VARCHAR(50), outcome VARCHAR(50), description TEXT,
 onset_date DATE, pv_case_reference VARCHAR(100), is_serious BOOLEAN NOT NULL DEFAULT FALSE, status VARCHAR(50) DEFAULT 'OPEN', reported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 reconciled_at TIMESTAMPTZ, reconciled_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_monitoring_access_requests (
 request_id BIGSERIAL PRIMARY KEY, organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE CASCADE, requester_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
 start_date DATE NOT NULL, end_date DATE NOT NULL, reason TEXT, status VARCHAR(50) NOT NULL DEFAULT 'pending', decision_note TEXT,
 decided_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, decided_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK(end_date>=start_date)
);
COMMIT;
