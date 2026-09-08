BEGIN;
CREATE TABLE IF NOT EXISTS ctms_document_folders (
 folder_id BIGSERIAL PRIMARY KEY, organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE CASCADE,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
 parent_folder_id BIGINT REFERENCES ctms_document_folders(folder_id) ON DELETE CASCADE, folder_code VARCHAR(100), folder_name VARCHAR(255) NOT NULL,
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(study_id,parent_folder_id,folder_name)
);
CREATE TABLE IF NOT EXISTS ctms_documents (
 document_id BIGSERIAL PRIMARY KEY, organization_id BIGINT NOT NULL REFERENCES organizations_organization(id) ON DELETE RESTRICT,
 study_id BIGINT REFERENCES ctms_studies(study_id) ON DELETE CASCADE, site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
 subject_id BIGINT REFERENCES ctms_subjects(subject_id) ON DELETE SET NULL, folder_id BIGINT REFERENCES ctms_document_folders(folder_id) ON DELETE SET NULL,
 module_id VARCHAR(100), section_id VARCHAR(100), category VARCHAR(255), document_type VARCHAR(255), title VARCHAR(500) NOT NULL,
 description TEXT, current_version_no VARCHAR(50), status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', expiry_date DATE,
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_document_versions (
 document_version_id BIGSERIAL PRIMARY KEY, document_id BIGINT NOT NULL REFERENCES ctms_documents(document_id) ON DELETE CASCADE,
 version_no VARCHAR(50) NOT NULL, file_name VARCHAR(500) NOT NULL, mime_type VARCHAR(255), file_size_bytes BIGINT,
 s3_bucket VARCHAR(255), s3_key TEXT, checksum_sha256 VARCHAR(64), uploaded_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(), change_note TEXT, extracted_text TEXT, UNIQUE(document_id,version_no)
);
CREATE TABLE IF NOT EXISTS ctms_document_approvals (
 approval_id BIGSERIAL PRIMARY KEY, document_version_id BIGINT NOT NULL REFERENCES ctms_document_versions(document_version_id) ON DELETE CASCADE,
 status VARCHAR(50) NOT NULL, approved_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, approval_date TIMESTAMPTZ,
 comments TEXT, expiry_date DATE
);
CREATE TABLE IF NOT EXISTS ctms_document_audit_trail (
 document_audit_id BIGSERIAL PRIMARY KEY, document_id BIGINT NOT NULL REFERENCES ctms_documents(document_id) ON DELETE CASCADE,
 document_version_id BIGINT REFERENCES ctms_document_versions(document_version_id) ON DELETE SET NULL,
 action VARCHAR(100) NOT NULL, actor_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, details JSONB,
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_document_extractions (
 extraction_id BIGSERIAL PRIMARY KEY, document_version_id BIGINT NOT NULL REFERENCES ctms_document_versions(document_version_id) ON DELETE CASCADE,
 extraction_type VARCHAR(100) NOT NULL, extracted_text TEXT, structured_data JSONB, confidence_score NUMERIC(5,4) CHECK(confidence_score BETWEEN 0 AND 1),
 review_status VARCHAR(50) NOT NULL DEFAULT 'PENDING', reviewed_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 reviewed_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_etmf_zones (
 zone_id BIGSERIAL PRIMARY KEY, zone_code VARCHAR(100) NOT NULL UNIQUE, zone_name VARCHAR(255) NOT NULL, description TEXT, sort_order INTEGER
);
CREATE TABLE IF NOT EXISTS ctms_etmf_documents (
 etmf_document_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 zone_id BIGINT NOT NULL REFERENCES ctms_etmf_zones(zone_id), folder_id BIGINT REFERENCES ctms_document_folders(folder_id) ON DELETE SET NULL,
 artifact_name VARCHAR(500) NOT NULL, document_id BIGINT REFERENCES ctms_documents(document_id) ON DELETE SET NULL,
 status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', completeness_required BOOLEAN NOT NULL DEFAULT FALSE,
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_etmf_completeness_requirements (
 requirement_id BIGSERIAL PRIMARY KEY, zone_id BIGINT NOT NULL REFERENCES ctms_etmf_zones(zone_id) ON DELETE CASCADE,
 artifact_name VARCHAR(500) NOT NULL, required BOOLEAN NOT NULL DEFAULT TRUE, UNIQUE(zone_id,artifact_name)
);
COMMIT;
