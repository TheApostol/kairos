-- ============================================================
-- KAIROS CRM — Schema completo
-- ============================================================

-- LEADS
CREATE TABLE IF NOT EXISTS leads (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa          text NOT NULL,
  rubro            text,
  direccion        text,
  ciudad           text,
  provincia        text,
  telefono         text,
  website          text,
  google_maps_url  text,
  rating           numeric(3,1),
  reviews_count    integer,
  price_level      integer,
  horarios         text,
  instagram        text,
  email            text,
  whatsapp         text,
  score_ia         integer,
  observaciones    text,
  fuente           text DEFAULT 'Google Places API',
  fecha_extraccion date,
  -- CRM fields
  estado           text DEFAULT 'nuevo'
                   CHECK (estado IN ('nuevo','contactado','interesado','cliente','descartado')),
  asignado_a       text,
  ultima_actividad timestamptz,
  created_at       timestamptz DEFAULT now(),
  updated_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS leads_rubro_idx      ON leads (rubro);
CREATE INDEX IF NOT EXISTS leads_provincia_idx  ON leads (provincia);
CREATE INDEX IF NOT EXISTS leads_score_idx      ON leads (score_ia);
CREATE INDEX IF NOT EXISTS leads_estado_idx     ON leads (estado);
CREATE INDEX IF NOT EXISTS leads_email_idx      ON leads (email) WHERE email IS NOT NULL AND email != '';

-- SCRAPER JOBS
CREATE TABLE IF NOT EXISTS scraper_jobs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  status       text DEFAULT 'pending'
               CHECK (status IN ('pending','running','completed','failed')),
  queries      jsonb,
  total_found  integer DEFAULT 0,
  new_found    integer DEFAULT 0,
  progress     integer DEFAULT 0,
  total        integer DEFAULT 0,
  output_file  text,
  error_msg    text,
  started_at   timestamptz,
  completed_at timestamptz,
  created_at   timestamptz DEFAULT now()
);

-- PRODUCTS / CATALOG
CREATE TABLE IF NOT EXISTS products (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre           text NOT NULL,
  descripcion      text,
  categoria        text,
  precio_minorista numeric(10,2),
  precio_mayorista numeric(10,2),
  precio_promo     numeric(10,2),
  stock            integer DEFAULT 0,
  sku              text UNIQUE,
  imagen_url       text,
  imagenes_extra   jsonb DEFAULT '[]',
  activo           boolean DEFAULT true,
  destacado        boolean DEFAULT false,
  orden            integer DEFAULT 0,
  created_at       timestamptz DEFAULT now(),
  updated_at       timestamptz DEFAULT now()
);

-- ORDERS
CREATE TABLE IF NOT EXISTS orders (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id        uuid REFERENCES leads(id) ON DELETE SET NULL,
  numero         text UNIQUE,           -- ej: KAI-2026-0001
  estado         text DEFAULT 'borrador'
                 CHECK (estado IN ('borrador','confirmado','en_preparacion','despachado','entregado','cancelado')),
  subtotal       numeric(12,2) DEFAULT 0,
  descuento      numeric(12,2) DEFAULT 0,
  total          numeric(12,2) DEFAULT 0,
  moneda         text DEFAULT 'ARS',
  notas          text,
  fecha_pedido   date DEFAULT CURRENT_DATE,
  fecha_entrega  date,
  created_at     timestamptz DEFAULT now(),
  updated_at     timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS orders_lead_idx   ON orders (lead_id);
CREATE INDEX IF NOT EXISTS orders_estado_idx ON orders (estado);

-- ORDER ITEMS
CREATE TABLE IF NOT EXISTS order_items (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id    uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id  uuid REFERENCES products(id) ON DELETE SET NULL,
  nombre      text NOT NULL,
  cantidad    integer NOT NULL DEFAULT 1,
  precio_unit numeric(10,2) NOT NULL,
  subtotal    numeric(10,2) GENERATED ALWAYS AS (cantidad * precio_unit) STORED
);

-- CAMPAIGNS
CREATE TABLE IF NOT EXISTS campaigns (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre         text NOT NULL,
  tipo           text CHECK (tipo IN ('email','whatsapp','instagram')),
  estado         text DEFAULT 'borrador'
                 CHECK (estado IN ('borrador','programada','enviando','completada','pausada')),
  asunto         text,
  cuerpo         text,
  cuerpo_html    text,
  segmento       jsonb,                 -- filtros aplicados {rubro, provincia, score_min, ...}
  total_leads    integer DEFAULT 0,
  enviados       integer DEFAULT 0,
  abiertos       integer DEFAULT 0,
  clicks         integer DEFAULT 0,
  respondidos    integer DEFAULT 0,
  convertidos    integer DEFAULT 0,
  fecha_envio    timestamptz,
  created_at     timestamptz DEFAULT now(),
  updated_at     timestamptz DEFAULT now()
);

-- CAMPAIGN SENDS (detalle por lead)
CREATE TABLE IF NOT EXISTS campaign_sends (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id  uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  lead_id      uuid REFERENCES leads(id) ON DELETE SET NULL,
  estado       text DEFAULT 'pendiente'
               CHECK (estado IN ('pendiente','enviado','abierto','click','respondido','error')),
  email_dest   text,
  error_msg    text,
  enviado_at   timestamptz,
  abierto_at   timestamptz,
  click_at     timestamptz,
  created_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sends_campaign_idx ON campaign_sends (campaign_id);
CREATE INDEX IF NOT EXISTS sends_lead_idx     ON campaign_sends (lead_id);

-- ACTIVITIES (timeline por lead)
CREATE TABLE IF NOT EXISTS activities (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id     uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  tipo        text CHECK (tipo IN ('nota','email','whatsapp','llamada','pedido','sistema')),
  descripcion text,
  metadata    jsonb,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS activities_lead_idx ON activities (lead_id);

-- CATALOG EXPORTS
CREATE TABLE IF NOT EXISTS catalog_exports (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre       text,
  tipo         text CHECK (tipo IN ('pdf','link')),
  productos    jsonb,                   -- lista de product_ids incluidos
  url          text,
  created_at   timestamptz DEFAULT now()
);

-- AUTO-UPDATE updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at    BEFORE UPDATE ON leads    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER orders_updated_at   BEFORE UPDATE ON orders   FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER campaigns_updated_at BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ORDER NUMBER SEQUENCE
CREATE SEQUENCE IF NOT EXISTS order_number_seq START 1;
CREATE OR REPLACE FUNCTION generate_order_number()
RETURNS TRIGGER AS $$
BEGIN
  NEW.numero = 'KAI-' || to_char(now(), 'YYYY') || '-' || lpad(nextval('order_number_seq')::text, 4, '0');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER orders_number_trigger
  BEFORE INSERT ON orders
  FOR EACH ROW
  WHEN (NEW.numero IS NULL)
  EXECUTE FUNCTION generate_order_number();
