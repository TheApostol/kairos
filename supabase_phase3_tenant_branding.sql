-- POLKORP / KAIROS SaaS Phase 3
-- Tenant branding, domains and client-admin URL metadata.

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS logo_url text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS primary_domain text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subdomain text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS admin_path text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_primary_color text DEFAULT '#C9A040';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_secondary_color text DEFAULT '#2C1F16';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_accent_color text DEFAULT '#FAF7F2';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS brand_settings jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS onboarding_status text NOT NULL DEFAULT 'draft'
  CHECK (onboarding_status IN ('draft','invited','active','suspended'));

CREATE INDEX IF NOT EXISTS organizations_primary_domain_idx ON organizations(primary_domain);
CREATE INDEX IF NOT EXISTS organizations_subdomain_idx ON organizations(subdomain);
CREATE INDEX IF NOT EXISTS organizations_onboarding_status_idx ON organizations(onboarding_status);

UPDATE organizations
SET
  subdomain = COALESCE(subdomain, 'kairos'),
  primary_domain = COALESCE(primary_domain, 'kairos.polkorp.com'),
  admin_path = COALESCE(admin_path, '/kairos/admin'),
  logo_url = COALESCE(logo_url, '/logo.svg'),
  brand_primary_color = COALESCE(brand_primary_color, '#C9A040'),
  brand_secondary_color = COALESCE(brand_secondary_color, '#2C1F16'),
  brand_accent_color = COALESCE(brand_accent_color, '#FAF7F2'),
  onboarding_status = 'active',
  brand_settings = COALESCE(brand_settings, '{}'::jsonb) || '{"tenant_admin_url":"/kairos/admin","platform":"Polkorp","lead_client":true}'::jsonb,
  updated_at = now()
WHERE slug = 'kairos'
   OR id = '00000000-0000-0000-0000-000000000001';
