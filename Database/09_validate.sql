SELECT current_database() AS database_name, version() AS postgres_version;
SELECT count(*) AS engine_tables FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'ctms_%';
SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;
SELECT tc.table_name,kcu.column_name,ccu.table_name AS referenced_table,ccu.column_name AS referenced_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name AND ccu.table_schema=tc.table_schema
WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'
ORDER BY tc.table_name,kcu.column_name;
SELECT 'organizations_organization' table_name,count(*) row_count FROM organizations_organization
UNION ALL SELECT 'accounts_user',count(*) FROM accounts_user
UNION ALL SELECT 'ctms_studies',count(*) FROM ctms_studies
UNION ALL SELECT 'ctms_sites',count(*) FROM ctms_sites
UNION ALL SELECT 'ctms_subjects',count(*) FROM ctms_subjects
UNION ALL SELECT 'ctms_visits',count(*) FROM ctms_visits
UNION ALL SELECT 'ctms_documents',count(*) FROM ctms_documents
UNION ALL SELECT 'ctms_amendment',count(*) FROM ctms_amendment
UNION ALL SELECT 'ctms_subject',count(*) FROM ctms_subject
UNION ALL SELECT 'ctms_visit',count(*) FROM ctms_visit
UNION ALL SELECT 'eisf_document',count(*) FROM eisf_document
UNION ALL SELECT 'eisf_documentversion',count(*) FROM eisf_documentversion
UNION ALL SELECT 'ctms_complianceconfig',count(*) FROM ctms_complianceconfig
UNION ALL SELECT 'ctms_deviation',count(*) FROM ctms_deviation
UNION ALL SELECT 'ctms_capa',count(*) FROM ctms_capa
UNION ALL SELECT 'ctms_auditevent',count(*) FROM ctms_auditevent
UNION ALL SELECT 'ctms_riskrule',count(*) FROM ctms_riskrule
UNION ALL SELECT 'ctms_riskscore',count(*) FROM ctms_riskscore
UNION ALL SELECT 'ctms_riskevent',count(*) FROM ctms_riskevent
UNION ALL SELECT 'ctms_electronic_signature',count(*) FROM ctms_electronic_signature
UNION ALL SELECT 'ctms_signature_requests',count(*) FROM ctms_signature_requests
UNION ALL SELECT 'ctms_signature_request_signers',count(*) FROM ctms_signature_request_signers
ORDER BY table_name;
