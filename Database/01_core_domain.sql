BEGIN;
CREATE TABLE IF NOT EXISTS ctms_studies (
 study_id BIGSERIAL PRIMARY KEY, organization_id BIGINT NOT NULL REFERENCES organizations_organization(id) ON DELETE RESTRICT,
 code VARCHAR(100) NOT NULL, protocol_number VARCHAR(100) NOT NULL, name VARCHAR(500) NOT NULL,
 indication VARCHAR(255), therapeutic_area VARCHAR(200), country VARCHAR(100), location VARCHAR(255),
 sponsor_name VARCHAR(255), cro_name VARCHAR(255), principal_investigator_name VARCHAR(255),
 description TEXT, phase VARCHAR(50), status VARCHAR(50) NOT NULL DEFAULT 'PLANNED',
 planned_start_date DATE, planned_end_date DATE, actual_start_date DATE, actual_end_date DATE,
 target_subjects INTEGER NOT NULL DEFAULT 0 CHECK(target_subjects>=0),
 created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(organization_id,code), UNIQUE(organization_id,protocol_number)
);
CREATE TABLE IF NOT EXISTS ctms_study_versions (
 study_version_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 version_no VARCHAR(50) NOT NULL, effective_date DATE, summary_of_changes TEXT,
 protocol_document_id BIGINT, created_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(study_id,version_no)
);
CREATE TABLE IF NOT EXISTS ctms_study_team_members (
 study_team_member_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE, role_in_study VARCHAR(100) NOT NULL,
 start_date DATE, end_date DATE, UNIQUE(study_id,user_id,role_in_study)
);
CREATE TABLE IF NOT EXISTS ctms_study_milestones (
 milestone_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 parent_milestone_id BIGINT REFERENCES ctms_study_milestones(milestone_id) ON DELETE SET NULL,
 title VARCHAR(255) NOT NULL, due_date DATE, owner_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 status VARCHAR(50) NOT NULL DEFAULT 'Not Started', notes TEXT, actual_date DATE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_study_tasks (
 task_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 milestone_id BIGINT REFERENCES ctms_study_milestones(milestone_id) ON DELETE SET NULL,
 title VARCHAR(500) NOT NULL, description TEXT, owner_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 due_date DATE, status VARCHAR(50) NOT NULL DEFAULT 'Not Started', priority VARCHAR(30), completed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_regulatory_checklist_items (
 checklist_item_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 item_name VARCHAR(500) NOT NULL, status VARCHAR(50) NOT NULL DEFAULT 'Pending', owner_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 due_date DATE, notes TEXT, completed_at TIMESTAMPTZ, UNIQUE(study_id,item_name)
);
CREATE TABLE IF NOT EXISTS ctms_protocols (
 protocol_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 protocol_code VARCHAR(100), version_no VARCHAR(50), title VARCHAR(500), status VARCHAR(50), effective_date DATE,
 document_id BIGINT, notes TEXT, UNIQUE(study_id,version_no)
);
CREATE TABLE IF NOT EXISTS ctms_sites (
 site_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 organization_id BIGINT REFERENCES organizations_organization(id) ON DELETE SET NULL,
 site_code VARCHAR(100) NOT NULL, site_number VARCHAR(100), name VARCHAR(255) NOT NULL,
 address TEXT, city VARCHAR(100), state_province VARCHAR(100), postal_code VARCHAR(30), country VARCHAR(100),
 status VARCHAR(50) NOT NULL DEFAULT 'PLANNED', activation_date DATE, closeout_date DATE,
 target_enrollment INTEGER NOT NULL DEFAULT 0 CHECK(target_enrollment>=0), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(study_id,site_code)
);
CREATE TABLE IF NOT EXISTS ctms_site_contacts (
 contact_id BIGSERIAL PRIMARY KEY, site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
 name VARCHAR(255) NOT NULL, role VARCHAR(100), email VARCHAR(320), phone VARCHAR(50), is_primary BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS ctms_investigators (
 investigator_id BIGSERIAL PRIMARY KEY, site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
 user_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL, investigator_type VARCHAR(50), license_no VARCHAR(100),
 status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE', start_date DATE, end_date DATE
);
CREATE TABLE IF NOT EXISTS ctms_site_staff (
 site_staff_id BIGSERIAL PRIMARY KEY, site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE,
 user_id BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE, job_title VARCHAR(100), start_date DATE, end_date DATE,
 UNIQUE(site_id,user_id)
);
CREATE TABLE IF NOT EXISTS ctms_subjects (
 subject_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT NOT NULL REFERENCES ctms_sites(site_id) ON DELETE CASCADE, subject_code VARCHAR(100) NOT NULL,
 subject_number VARCHAR(100), initials VARCHAR(20), date_of_birth DATE, gender VARCHAR(30), screening_date DATE,
 enrollment_date DATE, status VARCHAR(50) NOT NULL DEFAULT 'SCREENING', screen_failure_reason TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(study_id,subject_code)
);
CREATE TABLE IF NOT EXISTS ctms_subject_status_history (
 history_id BIGSERIAL PRIMARY KEY, subject_id BIGINT NOT NULL REFERENCES ctms_subjects(subject_id) ON DELETE CASCADE,
 old_status VARCHAR(50), new_status VARCHAR(50) NOT NULL, reason TEXT, changed_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ctms_visits (
 visit_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 site_id BIGINT REFERENCES ctms_sites(site_id) ON DELETE SET NULL, subject_id BIGINT NOT NULL REFERENCES ctms_subjects(subject_id) ON DELETE CASCADE,
 visit_code VARCHAR(100) NOT NULL, visit_type VARCHAR(50) NOT NULL, scheduled_date DATE, scheduled_time VARCHAR(30), actual_date DATE,
 status VARCHAR(50) NOT NULL DEFAULT 'SCHEDULED', notes TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(subject_id,visit_code)
);
CREATE TABLE IF NOT EXISTS ctms_visit_activities (
 activity_id BIGSERIAL PRIMARY KEY, visit_id BIGINT NOT NULL REFERENCES ctms_visits(visit_id) ON DELETE CASCADE,
 activity_name VARCHAR(255) NOT NULL, status VARCHAR(50), completed_at TIMESTAMPTZ, performed_by BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
 notes TEXT
);
CREATE TABLE IF NOT EXISTS ctms_visit_plans (
 visit_plan_id BIGSERIAL PRIMARY KEY, study_id BIGINT NOT NULL REFERENCES ctms_studies(study_id) ON DELETE CASCADE,
 name VARCHAR(255) NOT NULL, version_no VARCHAR(50), status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', effective_date DATE, description TEXT,
 UNIQUE(study_id,name,version_no)
);
CREATE TABLE IF NOT EXISTS ctms_visit_plan_visits (
 plan_visit_id BIGSERIAL PRIMARY KEY, visit_plan_id BIGINT NOT NULL REFERENCES ctms_visit_plans(visit_plan_id) ON DELETE CASCADE,
 visit_code VARCHAR(100) NOT NULL, visit_type VARCHAR(50) NOT NULL, sequence_no INTEGER, window_before_days INTEGER DEFAULT 0,
 window_after_days INTEGER DEFAULT 0, target_day INTEGER, UNIQUE(visit_plan_id,visit_code)
);
CREATE TABLE IF NOT EXISTS ctms_visit_plan_procedures (
 procedure_id BIGSERIAL PRIMARY KEY, plan_visit_id BIGINT NOT NULL REFERENCES ctms_visit_plan_visits(plan_visit_id) ON DELETE CASCADE,
 procedure_code VARCHAR(100), procedure_name VARCHAR(255) NOT NULL, required BOOLEAN NOT NULL DEFAULT TRUE, sequence_no INTEGER
);
CREATE TABLE IF NOT EXISTS ctms_visit_plan_tasks (
 plan_task_id BIGSERIAL PRIMARY KEY, plan_visit_id BIGINT NOT NULL REFERENCES ctms_visit_plan_visits(plan_visit_id) ON DELETE CASCADE,
 task_name VARCHAR(255) NOT NULL, owner_role VARCHAR(100), required BOOLEAN NOT NULL DEFAULT TRUE, sequence_no INTEGER
);
COMMIT;
