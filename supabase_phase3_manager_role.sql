-- POLKORP / KAIROS SaaS Phase 3
-- Add the tenant-level manager role required by the Polkorp RBAC model.
-- Run after supabase_saas_migration.sql.

ALTER TABLE organization_users
  DROP CONSTRAINT IF EXISTS organization_users_role_check;

ALTER TABLE organization_users
  ADD CONSTRAINT organization_users_role_check
  CHECK (role IN ('owner','admin','manager','sales','viewer'));

ALTER TABLE organization_invitations
  DROP CONSTRAINT IF EXISTS organization_invitations_role_check;

ALTER TABLE organization_invitations
  ADD CONSTRAINT organization_invitations_role_check
  CHECK (role IN ('admin','manager','sales','viewer'));
