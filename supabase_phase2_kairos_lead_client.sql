-- POLKORP / KAIROS SaaS Phase 2
-- Mark Kairos as the lead/reference client and add customer metadata.

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS customer_tier text NOT NULL DEFAULT 'standard'
  CHECK (customer_tier IN ('lead_client','standard','strategic','enterprise'));
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS internal_notes text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS public_catalog_enabled boolean NOT NULL DEFAULT true;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS feature_flags jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS organizations_customer_tier_idx ON organizations(customer_tier);

UPDATE organizations
SET
  customer_tier = 'lead_client',
  plan = 'pro',
  status = 'active',
  public_catalog_enabled = true,
  internal_notes = COALESCE(internal_notes, 'Lead client / reference implementation for Polkorp SaaS CRM.'),
  feature_flags = COALESCE(feature_flags, '{}'::jsonb) || '{"lead_client":true,"white_label":true,"ai_scoring":true,"public_catalog":true}'::jsonb,
  updated_at = now()
WHERE slug = 'kairos'
   OR id = '00000000-0000-0000-0000-000000000001';

UPDATE subscriptions s
SET
  plan_id = 'pro',
  status = 'active',
  provider = COALESCE(provider, 'manual'),
  updated_at = now()
FROM organizations o
WHERE s.organization_id = o.id
  AND (o.slug = 'kairos' OR o.id = '00000000-0000-0000-0000-000000000001');
