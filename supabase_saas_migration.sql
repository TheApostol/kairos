-- ============================================================
-- KAIROS SaaS Migration — Multi-tenant Supabase Auth foundation
-- Run this in Supabase SQL editor after taking a database backup.
-- ============================================================

-- Required extension for UUID generation
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
                   CHECK (role IN ('owner','admin','sales','viewer')),
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
                   CHECK (role IN ('admin','sales','viewer')),
  token            text UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(24), 'hex'),
  accepted_at      timestamptz,
  expires_at       timestamptz DEFAULT (now() + interval '7 days'),
  created_by       uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS organization_invitations_org_idx ON organization_invitations(organization_id);
CREATE INDEX IF NOT EXISTS organization_invitations_email_idx ON organization_invitations(lower(email));

-- ============================================================
-- TENANT COLUMNS
-- ============================================================
ALTER TABLE leads          ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE scraper_jobs   ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE products       ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE orders         ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE campaigns      ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE campaign_sends ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE activities     ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE catalog_exports ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS leads_org_idx ON leads(organization_id);
CREATE INDEX IF NOT EXISTS scraper_jobs_org_idx ON scraper_jobs(organization_id);
CREATE INDEX IF NOT EXISTS products_org_idx ON products(organization_id);
CREATE INDEX IF NOT EXISTS orders_org_idx ON orders(organization_id);
CREATE INDEX IF NOT EXISTS campaigns_org_idx ON campaigns(organization_id);
CREATE INDEX IF NOT EXISTS campaign_sends_org_idx ON campaign_sends(organization_id);
CREATE INDEX IF NOT EXISTS activities_org_idx ON activities(organization_id);
CREATE INDEX IF NOT EXISTS catalog_exports_org_idx ON catalog_exports(organization_id);

-- Make SKU unique per organization instead of globally.
DROP INDEX IF EXISTS products_sku_key;
CREATE UNIQUE INDEX IF NOT EXISTS products_org_sku_unique
  ON products(organization_id, sku)
  WHERE sku IS NOT NULL AND sku <> '';

-- ============================================================
-- ROLE HELPERS
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
  FOR ALL USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']));

DROP POLICY IF EXISTS invitations_manage_admins ON organization_invitations;
CREATE POLICY invitations_manage_admins ON organization_invitations
  FOR ALL USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']));

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

-- Order items inherit access through their parent order.
DROP POLICY IF EXISTS order_items_tenant_access ON order_items;
CREATE POLICY order_items_tenant_access ON order_items
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM orders o
      WHERE o.id = order_items.order_id
        AND public.user_has_org_access(o.organization_id)
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM orders o
      WHERE o.id = order_items.order_id
        AND public.user_has_org_access(o.organization_id)
    )
  );

-- ============================================================
-- BOOTSTRAP FUNCTION: create organization for current user
-- ============================================================
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
