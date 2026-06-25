-- ============================================================
-- KAIROS SaaS Migration — Multi-tenant Supabase Auth foundation
-- Applied to project gachxhquivfvwejytsbb.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- ORGANIZATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  slug            text UNIQUE NOT NULL,
  plan            text NOT NULL DEFAULT 'starter'
                  CHECK (plan IN ('starter','growth','pro','enterprise')),
  status          text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','trialing','past_due','cancelled','suspended')),
  billing_email   text,
  country         text DEFAULT 'AR',
  public_catalog_enabled boolean NOT NULL DEFAULT true,
  created_by      uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS organizations_slug_idx ON organizations(slug);
CREATE INDEX IF NOT EXISTS organizations_status_idx ON organizations(status);

-- ============================================================
-- ORGANIZATION USERS / MEMBERSHIPS
-- ============================================================
CREATE TABLE IF NOT EXISTS organization_users (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id          uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role             text NOT NULL DEFAULT 'sales'
                   CHECK (role IN ('owner','admin','manager','sales','viewer')),
  status           text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','invited','disabled')),
  created_at       timestamptz DEFAULT now(),
  updated_at       timestamptz DEFAULT now(),
  UNIQUE (organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS organization_users_user_idx ON organization_users(user_id);
CREATE INDEX IF NOT EXISTS organization_users_org_idx ON organization_users(organization_id);

CREATE TABLE IF NOT EXISTS organization_invitations (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email            text NOT NULL,
  role             text NOT NULL DEFAULT 'sales'
                   CHECK (role IN ('admin','manager','sales','viewer')),
  token            text UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(24), 'hex'),
  accepted_at      timestamptz,
  expires_at       timestamptz DEFAULT (now() + interval '7 days'),
  created_by       uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS organization_invitations_org_idx ON organization_invitations(organization_id);
CREATE INDEX IF NOT EXISTS organization_invitations_email_idx ON organization_invitations(lower(email));
CREATE INDEX IF NOT EXISTS organization_invitations_token_idx ON organization_invitations(token);

-- ============================================================
-- TENANT COLUMNS
-- ============================================================
ALTER TABLE leads               ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE scraper_jobs        ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE products            ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE orders              ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE campaigns           ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE campaign_sends      ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE activities          ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE catalog_exports     ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE tasks               ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE product_price_history ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;

-- lead_notes.lead_id was mistakenly typed bigint (table has 0 rows) and had no FK
-- to leads(id) (uuid). Fix the type, add the FK, and add the tenant column.
ALTER TABLE lead_notes DROP COLUMN IF EXISTS lead_id;
ALTER TABLE lead_notes ADD COLUMN lead_id uuid REFERENCES leads(id) ON DELETE CASCADE;
ALTER TABLE lead_notes ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;

-- order_items has no tenant column of its own (it inherits access through its
-- parent order). Give it one directly too, so it can be scoped like every
-- other tenant table instead of needing a join on every query.
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
UPDATE order_items oi SET organization_id = o.organization_id
  FROM orders o WHERE oi.order_id = o.id AND oi.organization_id IS NULL;
CREATE INDEX IF NOT EXISTS order_items_org_idx ON order_items(organization_id);

CREATE INDEX IF NOT EXISTS leads_org_idx ON leads(organization_id);
CREATE INDEX IF NOT EXISTS scraper_jobs_org_idx ON scraper_jobs(organization_id);
CREATE INDEX IF NOT EXISTS products_org_idx ON products(organization_id);
CREATE INDEX IF NOT EXISTS orders_org_idx ON orders(organization_id);
CREATE INDEX IF NOT EXISTS campaigns_org_idx ON campaigns(organization_id);
CREATE INDEX IF NOT EXISTS campaign_sends_org_idx ON campaign_sends(organization_id);
CREATE INDEX IF NOT EXISTS activities_org_idx ON activities(organization_id);
CREATE INDEX IF NOT EXISTS catalog_exports_org_idx ON catalog_exports(organization_id);
CREATE INDEX IF NOT EXISTS tasks_org_idx ON tasks(organization_id);
CREATE INDEX IF NOT EXISTS product_price_history_org_idx ON product_price_history(organization_id);
CREATE INDEX IF NOT EXISTS lead_notes_org_idx ON lead_notes(organization_id);
CREATE INDEX IF NOT EXISTS lead_notes_lead_idx ON lead_notes(lead_id);

-- Make SKU unique per organization instead of globally.
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key;
DROP INDEX IF EXISTS products_sku_key;
CREATE UNIQUE INDEX IF NOT EXISTS products_org_sku_unique
  ON products(organization_id, sku)
  WHERE sku IS NOT NULL AND sku <> '';

-- ============================================================
-- DEFAULT ORGANIZATION + BACKFILL EXISTING DATA
-- ============================================================
INSERT INTO organizations (id, name, slug, plan, status)
VALUES ('00000000-0000-0000-0000-000000000001', 'Kairos Distribuidora', 'kairos', 'pro', 'active')
ON CONFLICT (id) DO NOTHING;

UPDATE leads               SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE scraper_jobs        SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE products            SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE orders              SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE campaigns           SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE campaign_sends      SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE activities          SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE catalog_exports     SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE tasks               SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;
UPDATE product_price_history SET organization_id = '00000000-0000-0000-0000-000000000001' WHERE organization_id IS NULL;

-- ============================================================
-- ROLE / TENANT HELPER FUNCTIONS
-- ============================================================
CREATE OR REPLACE FUNCTION public.user_has_org_access(org_id uuid)
RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1
    FROM organization_users ou
    WHERE ou.organization_id = org_id
      AND ou.user_id = auth.uid()
      AND ou.status = 'active'
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.user_has_org_role(org_id uuid, allowed_roles text[])
RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1
    FROM organization_users ou
    WHERE ou.organization_id = org_id
      AND ou.user_id = auth.uid()
      AND ou.status = 'active'
      AND ou.role = ANY(allowed_roles)
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_sends ENABLE ROW LEVEL SECURITY;
ALTER TABLE activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_notes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_select_members ON organizations;
CREATE POLICY org_select_members ON organizations
  FOR SELECT USING (public.user_has_org_access(id));

DROP POLICY IF EXISTS org_update_admins ON organizations;
CREATE POLICY org_update_admins ON organizations
  FOR UPDATE USING (public.user_has_org_role(id, ARRAY['owner','admin']));

DROP POLICY IF EXISTS org_users_select_members ON organization_users;
CREATE POLICY org_users_select_members ON organization_users
  FOR SELECT USING (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS org_users_manage_admins ON organization_users;
CREATE POLICY org_users_manage_admins ON organization_users
  FOR ALL USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']))
  WITH CHECK (public.user_has_org_role(organization_id, ARRAY['owner','admin']));

DROP POLICY IF EXISTS invitations_manage_admins ON organization_invitations;
CREATE POLICY invitations_manage_admins ON organization_invitations
  FOR ALL USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']))
  WITH CHECK (public.user_has_org_role(organization_id, ARRAY['owner','admin']));

-- Generic tenant policies
DROP POLICY IF EXISTS leads_tenant_access ON leads;
CREATE POLICY leads_tenant_access ON leads
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS scraper_jobs_tenant_access ON scraper_jobs;
CREATE POLICY scraper_jobs_tenant_access ON scraper_jobs
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS products_tenant_access ON products;
CREATE POLICY products_tenant_access ON products
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS orders_tenant_access ON orders;
CREATE POLICY orders_tenant_access ON orders
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS campaigns_tenant_access ON campaigns;
CREATE POLICY campaigns_tenant_access ON campaigns
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS campaign_sends_tenant_access ON campaign_sends;
CREATE POLICY campaign_sends_tenant_access ON campaign_sends
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS activities_tenant_access ON activities;
CREATE POLICY activities_tenant_access ON activities
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS catalog_exports_tenant_access ON catalog_exports;
CREATE POLICY catalog_exports_tenant_access ON catalog_exports
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS tasks_tenant_access ON tasks;
CREATE POLICY tasks_tenant_access ON tasks
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS product_price_history_tenant_access ON product_price_history;
CREATE POLICY product_price_history_tenant_access ON product_price_history
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

DROP POLICY IF EXISTS lead_notes_tenant_access ON lead_notes;
CREATE POLICY lead_notes_tenant_access ON lead_notes
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

-- Order items have their own organization_id (backfilled from the parent
-- order above), so they can be scoped directly like every other table.
DROP POLICY IF EXISTS order_items_tenant_access ON order_items;
CREATE POLICY order_items_tenant_access ON order_items
  FOR ALL USING (public.user_has_org_access(organization_id))
  WITH CHECK (public.user_has_org_access(organization_id));

-- ============================================================
-- ORG BOOTSTRAP / CREATION / INVITATIONS
-- ============================================================

-- Create a brand-new organization (used by the SaaS signup flow for
-- additional tenants).
CREATE OR REPLACE FUNCTION public.create_organization(org_name text, org_slug text)
RETURNS uuid AS $$
DECLARE
  new_org_id uuid;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Authentication required';
  END IF;

  INSERT INTO organizations(name, slug, created_by)
  VALUES (org_name, org_slug, auth.uid())
  RETURNING id INTO new_org_id;

  INSERT INTO organization_users(organization_id, user_id, role, status)
  VALUES (new_org_id, auth.uid(), 'owner', 'active');

  RETURN new_org_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Claim ownership of the pre-existing "Kairos Distribuidora" org. Only the
-- first user to call this (when the org has zero members) becomes its
-- owner; later callers are no-ops so they must be invited instead.
CREATE OR REPLACE FUNCTION public.claim_default_organization()
RETURNS uuid AS $$
DECLARE
  default_org_id uuid := '00000000-0000-0000-0000-000000000001';
  member_count int;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Authentication required';
  END IF;

  SELECT count(*) INTO member_count FROM organization_users WHERE organization_id = default_org_id;

  IF member_count = 0 THEN
    INSERT INTO organization_users(organization_id, user_id, role, status)
    VALUES (default_org_id, auth.uid(), 'owner', 'active');
  END IF;

  RETURN default_org_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Accept a team invitation by token. Bypasses RLS via SECURITY DEFINER so a
-- brand-new (not-yet-a-member) user can insert their own membership row.
CREATE OR REPLACE FUNCTION public.accept_invitation(invite_token text)
RETURNS uuid AS $$
DECLARE
  inv organization_invitations;
  uid uuid := auth.uid();
  current_email text;
BEGIN
  IF uid IS NULL THEN
    RAISE EXCEPTION 'Authentication required';
  END IF;

  SELECT * INTO inv FROM organization_invitations
  WHERE token = invite_token AND accepted_at IS NULL AND expires_at > now();

  IF inv.id IS NULL THEN
    RAISE EXCEPTION 'Invalid or expired invitation';
  END IF;

  SELECT email INTO current_email FROM auth.users WHERE id = uid;
  IF current_email IS NULL OR lower(current_email) <> lower(inv.email) THEN
    RAISE EXCEPTION 'This invitation was sent to a different email address';
  END IF;

  INSERT INTO organization_users(organization_id, user_id, role, status)
  VALUES (inv.organization_id, uid, inv.role, 'active')
  ON CONFLICT (organization_id, user_id) DO UPDATE SET role = inv.role, status = 'active';

  UPDATE organization_invitations SET accepted_at = now() WHERE id = inv.id;

  RETURN inv.organization_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- UPDATED_AT TRIGGERS
-- ============================================================
DROP TRIGGER IF EXISTS organizations_updated_at ON organizations;
CREATE TRIGGER organizations_updated_at
BEFORE UPDATE ON organizations
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS organization_users_updated_at ON organization_users;
CREATE TRIGGER organization_users_updated_at
BEFORE UPDATE ON organization_users
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
