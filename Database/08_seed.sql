BEGIN;
INSERT INTO organizations_organization(name) VALUES ('Demo Sponsor Organization') ON CONFLICT DO NOTHING;
INSERT INTO organizations_role(name,organization_id)
SELECT 'ADMIN',id FROM organizations_organization WHERE name='Demo Sponsor Organization'
ON CONFLICT DO NOTHING;
INSERT INTO billing_plantier(name,price,max_studies,max_users,storage_limit_gb,features,is_default,is_active)
VALUES ('Basic',0,3,5,10,'[]',TRUE,TRUE) ON CONFLICT DO NOTHING;
INSERT INTO subscriptions_plan(name,price,max_studies,max_users,storage_limit_gb,is_active)
VALUES ('Basic',0,3,5,10,TRUE) ON CONFLICT DO NOTHING;
COMMIT;
