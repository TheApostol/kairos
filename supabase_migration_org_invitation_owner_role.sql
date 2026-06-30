-- Allow 'owner' role in organization_invitations so that the platform admin
-- can invite the founding owner when creating a new organization.
ALTER TABLE organization_invitations
  DROP CONSTRAINT IF EXISTS organization_invitations_role_check;
ALTER TABLE organization_invitations
  ADD CONSTRAINT organization_invitations_role_check
  CHECK (role IN ('owner', 'admin', 'manager', 'sales', 'viewer'));
