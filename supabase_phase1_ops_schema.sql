-- POLKORP / KAIROS SaaS Phase 1 Ops Schema
-- Audit logs, billing primitives, usage metering and platform admins.
-- Run in Supabase SQL editor after backing up the database.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS platform_admins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'super_admin' CHECK (role IN ('super_admin','support','finance','ops')),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS platform_admins_user_idx ON platform_admins(user_id);
CREATE INDEX IF NOT EXISTS platform_admins_status_idx ON platform_admins(status);

CREATE TABLE IF NOT EXISTS audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  actor_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  actor_email text,
  actor_role text,
  action text NOT NULL,
  entity text,
  entity_id text,
  ip_address text,
  user_agent text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_logs_org_created_idx ON audit_logs(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_actor_created_idx ON audit_logs(actor_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_action_idx ON audit_logs(action);
CREATE INDEX IF NOT EXISTS audit_logs_entity_idx ON audit_logs(entity, entity_id);

CREATE TABLE IF NOT EXISTS plans (
  id text PRIMARY KEY,
  name text NOT NULL,
  monthly_price_cents integer NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'USD',
  active boolean NOT NULL DEFAULT true,
  features jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plan_limits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id text NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
  metric text NOT NULL,
  limit_value integer NOT NULL,
  period text NOT NULL DEFAULT 'monthly' CHECK (period IN ('monthly','daily','lifetime','none')),
  created_at timestamptz DEFAULT now(),
  UNIQUE(plan_id, metric, period)
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  plan_id text NOT NULL REFERENCES plans(id),
  status text NOT NULL DEFAULT 'trialing' CHECK (status IN ('trialing','active','past_due','cancelled','paused')),
  provider text NOT NULL DEFAULT 'manual' CHECK (provider IN ('manual','stripe','mercadopago','lemonsqueezy')),
  provider_customer_id text,
  provider_subscription_id text,
  current_period_start timestamptz,
  current_period_end timestamptz,
  trial_ends_at timestamptz,
  cancel_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE(organization_id)
);

CREATE INDEX IF NOT EXISTS subscriptions_org_idx ON subscriptions(organization_id);
CREATE INDEX IF NOT EXISTS subscriptions_status_idx ON subscriptions(status);

CREATE TABLE IF NOT EXISTS invoices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  subscription_id uuid REFERENCES subscriptions(id) ON DELETE SET NULL,
  provider text NOT NULL DEFAULT 'manual',
  provider_invoice_id text,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','open','paid','void','uncollectible')),
  amount_cents integer NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'USD',
  due_at timestamptz,
  paid_at timestamptz,
  invoice_url text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS invoices_org_created_idx ON invoices(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS invoices_status_idx ON invoices(status);

CREATE TABLE IF NOT EXISTS payments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  invoice_id uuid REFERENCES invoices(id) ON DELETE SET NULL,
  provider text NOT NULL DEFAULT 'manual',
  provider_payment_id text,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','succeeded','failed','refunded')),
  amount_cents integer NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'USD',
  paid_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS payments_org_created_idx ON payments(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS payments_status_idx ON payments(status);

CREATE TABLE IF NOT EXISTS usage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  actor_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  metric text NOT NULL,
  quantity integer NOT NULL DEFAULT 1,
  source text,
  entity text,
  entity_id text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS usage_events_org_metric_created_idx ON usage_events(organization_id, metric, created_at DESC);
CREATE INDEX IF NOT EXISTS usage_events_actor_idx ON usage_events(actor_user_id);
