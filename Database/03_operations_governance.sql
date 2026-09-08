BEGIN;
CREATE TABLE IF NOT EXISTS ctms_monitoring_visits (
 monitoring_visit_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE, monitor_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 visit_type VARCHAR(50) NOT NULL, scheduled_date DATE, actual_date DATE, status VARCHAR(50), protocol_version VARCHAR(50),
 report_document_id BIGINT REFERENCES ctms_documents(document_id) ON DELETE SET NULL, notes TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_monitoring_findings (
 finding_id BIGSERIAL PRIMARY KEY, monitoring_visit_id BIGINT REFERENCES ctms_monitoring_visits(monitoring_visit_id) ON DELETE CASCADE,
 study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
 severity VARCHAR(50), title VARCHAR(500) NOT NULL, description TEXT, status VARCHAR(50) DEFAULT 'OPEN', owner_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 due_date DATE, resolved_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS ctms_issues (
 issue_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL,
 issue_type VARCHAR(50) NOT NULL, title VARCHAR(500) NOT NULL, description TEXT, severity VARCHAR(50) NOT NULL DEFAULT 'MEDIUM',
 status VARCHAR(50) NOT NULL DEFAULT 'OPEN', identified_date DATE DEFAULT CURRENT_DATE, due_date DATE, resolved_date DATE,
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_capa_actions (
 capa_id BIGSERIAL PRIMARY KEY, issue_id BIGINT NOT NULL REFERENCES ctms_issues(issue_id) ON DELETE CASCADE, root_cause TEXT,
 corrective_action TEXT, preventive_action TEXT, owner_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, target_date DATE,
 status VARCHAR(50) DEFAULT 'OPEN', completed_date DATE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_action_items (
 action_item_id BIGSERIAL PRIMARY KEY, study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
 title VARCHAR(500) NOT NULL, description TEXT, owner_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, due_date DATE,
 priority VARCHAR(30), status VARCHAR(50) DEFAULT 'OPEN', completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS ctms_comments (
 comment_id BIGSERIAL PRIMARY KEY, organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
 subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL, entity_type VARCHAR(100) NOT NULL, entity_key VARCHAR(255),
 parent_comment_id BIGINT REFERENCES ctms_comments(comment_id) ON DELETE CASCADE, author_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
 body TEXT NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'OPEN', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_progress_notes (
 note_id BIGSERIAL PRIMARY KEY, study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL,
 subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL, note_type VARCHAR(50), title VARCHAR(500), body TEXT NOT NULL,
 author_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_reports (
 report_id BIGSERIAL PRIMARY KEY, study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, name VARCHAR(255) NOT NULL,
 report_type VARCHAR(100) NOT NULL, description TEXT, parameters JSONB, created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_report_schedules (
 schedule_id BIGSERIAL PRIMARY KEY, report_id BIGINT NOT NULL REFERENCES ctms_reports(report_id) ON DELETE CASCADE,
 frequency VARCHAR(50) NOT NULL, recipients JSONB, next_run_at TIMESTAMPTZ, is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS ctms_budgets (
 budget_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL UNIQUE REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 total_budget NUMERIC(18,2) NOT NULL DEFAULT 0, currency VARCHAR(10) NOT NULL DEFAULT 'USD', start_date DATE, end_date DATE
);
CREATE TABLE IF NOT EXISTS ctms_site_budgets (
 site_budget_id BIGSERIAL PRIMARY KEY, budget_id BIGINT NOT NULL REFERENCES ctms_budgets(budget_id) ON DELETE CASCADE,
 site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE, amount NUMERIC(18,2) NOT NULL DEFAULT 0,
 payment_schedule JSONB, status VARCHAR(50) DEFAULT 'ACTIVE', UNIQUE(budget_id,site_id)
);
CREATE TABLE IF NOT EXISTS ctms_payments (
 payment_id BIGSERIAL PRIMARY KEY, site_budget_id BIGINT NOT NULL REFERENCES ctms_site_budgets(site_budget_id) ON DELETE CASCADE,
 payment_no VARCHAR(100), amount NUMERIC(18,2) NOT NULL, payment_date DATE, payment_type VARCHAR(100), status VARCHAR(50) DEFAULT 'PENDING',
 invoice_ref VARCHAR(255), notes TEXT
);
CREATE TABLE IF NOT EXISTS ctms_risk_rules (
 rule_id BIGSERIAL PRIMARY KEY, rule_name VARCHAR(255) NOT NULL UNIQUE, category VARCHAR(100) NOT NULL, condition JSONB NOT NULL,
 weight NUMERIC(10,4) NOT NULL DEFAULT 1, threshold NUMERIC(10,4), lookback_days INTEGER, is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_risk_events (
 risk_event_id BIGSERIAL PRIMARY KEY, rule_id BIGINT REFERENCES ctms_risk_rules(rule_id) ON DELETE SET NULL,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
 subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL, risk_type VARCHAR(100) NOT NULL, risk_score NUMERIC(10,4),
 severity VARCHAR(50), description TEXT, evidence JSONB, status VARCHAR(50) DEFAULT 'OPEN', detected_at TIMESTAMPTZ NOT NULL DEFAULT now(), resolved_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS ctms_ai_conversations (
 conversation_id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, title VARCHAR(500), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_ai_messages (
 message_id BIGSERIAL PRIMARY KEY, conversation_id BIGINT NOT NULL REFERENCES ctms_ai_conversations(conversation_id) ON DELETE CASCADE,
 role VARCHAR(50) NOT NULL, content TEXT NOT NULL, citations JSONB, model_id VARCHAR(255), input_tokens INTEGER, output_tokens INTEGER,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_ai_findings (
 finding_id BIGSERIAL PRIMARY KEY, study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, document_id BIGINT REFERENCES ctms_documents(document_id) ON DELETE SET NULL,
 source_type VARCHAR(100), finding_type VARCHAR(100), title VARCHAR(500), finding TEXT, evidence JSONB,
 decision VARCHAR(50), rationale TEXT, decided_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, decided_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_notifications (
 notification_id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, title VARCHAR(255) NOT NULL, body TEXT, notification_type VARCHAR(50) DEFAULT 'INFO',
 severity VARCHAR(50), link VARCHAR(500), is_read BOOLEAN NOT NULL DEFAULT FALSE, read_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_access_requests (
 access_request_id BIGSERIAL PRIMARY KEY, organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
 requested_by BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE, requested_role VARCHAR(100), reason TEXT,
 status VARCHAR(50) NOT NULL DEFAULT 'PENDING', requested_at TIMESTAMPTZ NOT NULL DEFAULT now(), decided_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 decided_at TIMESTAMPTZ, decision_note TEXT
);
CREATE TABLE IF NOT EXISTS ctms_audit_events (
 audit_event_id BIGSERIAL PRIMARY KEY, organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
 user_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, entity_type VARCHAR(100) NOT NULL, entity_key VARCHAR(255), action VARCHAR(100) NOT NULL,
 old_values JSONB, new_values JSONB, ip_address INET, user_agent TEXT, correlation_id UUID, event_timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_electronic_signatures (
 signature_id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE RESTRICT,
 document_id BIGINT REFERENCES ctms_documents(document_id) ON DELETE SET NULL, document_version_id BIGINT REFERENCES ctms_document_versions(document_version_id) ON DELETE SET NULL,
 signature_type VARCHAR(50) NOT NULL, signature_meaning VARCHAR(255), ip_address INET, signed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 verification_status VARCHAR(50), certificate_hash TEXT
);
CREATE TABLE IF NOT EXISTS ctms_signature_requests (
 request_id BIGSERIAL PRIMARY KEY, document_id BIGINT NOT NULL REFERENCES ctms_documents(document_id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, requested_by BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE RESTRICT,
 title VARCHAR(500), status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', sent_at TIMESTAMPTZ, expires_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_signature_request_signers (
 signer_id BIGSERIAL PRIMARY KEY, request_id BIGINT NOT NULL REFERENCES ctms_signature_requests(request_id) ON DELETE CASCADE,
 user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE RESTRICT, signer_role VARCHAR(100), signer_name VARCHAR(255) NOT NULL,
 status VARCHAR(50) NOT NULL DEFAULT 'PENDING', meaning VARCHAR(255), signed_at TIMESTAMPTZ, verification_status VARCHAR(50), certificate JSONB,
 UNIQUE(request_id,user_id)
);
COMMIT;
