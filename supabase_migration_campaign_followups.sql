-- Adds automated email follow-up support to campaigns: per-campaign
-- followup_1/followup_2 message templates, a send_type column on
-- campaign_sends to distinguish initial sends from follow-up sends, and the
-- corresponding estado values for tracking which follow-up stage a send is
-- at. Additive/nullable-default — backward compatible with existing rows.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS followup_1 text;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS followup_2 text;

ALTER TABLE campaign_sends ADD COLUMN IF NOT EXISTS send_type text DEFAULT 'initial';

ALTER TABLE campaign_sends DROP CONSTRAINT IF EXISTS campaign_sends_estado_check;
ALTER TABLE campaign_sends ADD CONSTRAINT campaign_sends_estado_check
  CHECK (estado IN ('pendiente','enviado','abierto','click','respondido','error','followup_1_enviado','followup_2_enviado'));
