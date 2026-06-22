-- POLKORP / KAIROS SaaS Phase 1 Ops Seeds + RLS
-- Run after supabase_phase1_ops_schema.sql.

INSERT INTO plans (id, name, monthly_price_cents, currency, features)
VALUES
  ('starter', 'Starter', 2900, 'USD', '{"support":"email","ai":"limited"}'::jsonb),
  ('growth', 'Growth', 9900, 'USD', '{"support":"priority","ai":"standard"}'::jsonb),
  ('pro', 'Pro', 29900, 'USD', '{"support":"priority","ai":"advanced","white_label":true}'::jsonb),
  ('enterprise', 'Enterprise', 0, 'USD', '{"support":"dedicated","ai":"custom","sso":true}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  monthly_price_cents = EXCLUDED.monthly_price_cents,
  currency = EXCLUDED.currency,
  features = EXCLUDED.features,
  updated_at = now();

INSERT INTO plan_limits (plan_id, metric, limit_value, period)
VALUES
  ('starter','users',1,'none'),
  ('starter','leads',1000,'none'),
  ('starter','products',100,'none'),
  ('starter','campaign_sends',1000,'monthly'),
  ('starter','ai_requests',100,'monthly'),
  ('growth','users',5,'none'),
  ('growth','leads',10000,'none'),
  ('growth','products',1000,'none'),
  ('growth','campaign_sends',10000,'monthly'),
  ('growth','ai_requests',1000,'monthly'),
  ('pro','users',20,'none'),
  ('pro','leads',100000,'none'),
  ('pro','products',10000,'none'),
  ('pro','campaign_sends',100000,'monthly'),
  ('pro','ai_requests',10000,'monthly'),
  ('enterprise','users',-1,'none'),
  ('enterprise','leads',-1,'none'),
  ('enterprise','products',-1,'none'),
  ('enterprise','campaign_sends',-1,'monthly'),
  ('enterprise','ai_requests',-1,'monthly')
ON CONFLICT (plan_id, metric, period) DO UPDATE SET limit_value = EXCLUDED.limit_value;

INSERT INTO subscriptions (organization_id, plan_id, status, provider)
SELECT id, COALESCE(plan, 'starter'), status, 'manual'
FROM organizations
ON CONFLICT (organization_id) DO NOTHING;

DROP TRIGGER IF EXISTS platform_admins_updated_at ON platform_admins;
CREATE TRIGGER platform_admins_updated_at
BEFORE UPDATE ON platform_admins
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS plans_updated_at ON plans;
CREATE TRIGGER plans_updated_at
BEFORE UPDATE ON plans
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS subscriptions_updated_at ON subscriptions;
CREATE TRIGGER subscriptions_updated_at
BEFORE UPDATE ON subscriptions
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS invoices_updated_at ON invoices;
CREATE TRIGGER invoices_updated_at
BEFORE UPDATE ON invoices
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.is_platform_admin(allowed_roles text[] DEFAULT ARRAY['super_admin','support','finance','ops'])
RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1 FROM platform_admins pa
    WHERE pa.user_id = auth.uid()
      AND pa.status = 'active'
      AND pa.role = ANY(allowed_roles)
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

DROP POLICY IF EXISTS platform_admins_self_or_super ON platform_admins;
CREATE POLICY platform_admins_self_or_super ON platform_admins
  FOR SELECT USING (user_id = auth.uid() OR public.is_platform_admin(ARRAY['super_admin']));

DROP POLICY IF EXISTS platform_admins_super_manage ON platform_admins;
CREATE POLICY platform_admins_super_manage ON platform_admins
  FOR ALL USING (public.is_platform_admin(ARRAY['super_admin']))
  WITH CHECK (public.is_platform_admin(ARRAY['super_admin']));

DROP POLICY IF EXISTS audit_logs_org_members ON audit_logs;
CREATE POLICY audit_logs_org_members ON audit_logs
  FOR SELECT USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']) OR public.is_platform_admin());

DROP POLICY IF EXISTS plans_public_read ON plans;
CREATE POLICY plans_public_read ON plans
  FOR SELECT USING (active = true OR public.is_platform_admin());

DROP POLICY IF EXISTS plan_limits_public_read ON plan_limits;
CREATE POLICY plan_limits_public_read ON plan_limits
  FOR SELECT USING (true);

DROP POLICY IF EXISTS subscriptions_org_admin_read ON subscriptions;
CREATE POLICY subscriptions_org_admin_read ON subscriptions
  FOR SELECT USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']) OR public.is_platform_admin());

DROP POLICY IF EXISTS invoices_org_admin_read ON invoices;
CREATE POLICY invoices_org_admin_read ON invoices
  FOR SELECT USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']) OR public.is_platform_admin());

DROP POLICY IF EXISTS payments_org_admin_read ON payments;
CREATE POLICY payments_org_admin_read ON payments
  FOR SELECT USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']) OR public.is_platform_admin());

DROP POLICY IF EXISTS usage_events_org_admin_read ON usage_events;
CREATE POLICY usage_events_org_admin_read ON usage_events
  FOR SELECT USING (public.user_has_org_role(organization_id, ARRAY['owner','admin']) OR public.is_platform_admin());
