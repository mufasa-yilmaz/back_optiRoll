-- =============================================================================
-- OptiRoll – Supabase tabloları tam kurulum / migrasyon
-- =============================================================================
-- Kullanım: Supabase Dashboard > SQL Editor > Yeni sorgu > Bu dosyanın içeriğini
-- yapıştırıp "Run" ile çalıştırın. Birden fazla kez çalıştırılabilir (idempotent).
-- =============================================================================

-- 1) Ana tablolar (bağımlılık sırasına göre)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS optimization_configurations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT,
  material_thickness NUMERIC NOT NULL,
  material_density NUMERIC NOT NULL,
  safety_stock NUMERIC NOT NULL,
  max_orders_per_roll INT NOT NULL,
  max_rolls_per_order INT NOT NULL,
  fire_cost NUMERIC NOT NULL,
  setup_cost NUMERIC NOT NULL,
  stock_cost NUMERIC NOT NULL,
  rolls JSONB NOT NULL,
  orders JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS optimization_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  file_id TEXT NOT NULL UNIQUE,
  configuration_id UUID,
  created_at TIMESTAMPTZ DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'Optimal',
  input_data JSONB NOT NULL,
  summary JSONB NOT NULL,
  cutting_plan JSONB NOT NULL,
  roll_status JSONB NOT NULL,
  report_url TEXT
);

-- Eksik kolonlar (varsa eklenmez)
ALTER TABLE optimization_runs
  ADD COLUMN IF NOT EXISTS configuration_id UUID;
ALTER TABLE optimization_runs
  ADD COLUMN IF NOT EXISTS report_url TEXT;

-- FK: runs -> configurations (yoksa ekle)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'optimization_runs_configuration_id_fkey'
  ) THEN
    ALTER TABLE optimization_runs
      ADD CONSTRAINT optimization_runs_configuration_id_fkey
      FOREIGN KEY (configuration_id)
      REFERENCES optimization_configurations(id)
      ON DELETE SET NULL;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS order_sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  orders JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stock_sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  rolls JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2) Analitik / detay tabloları (optimization_runs'a bağlı)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS optimization_run_metrics (
  run_id UUID PRIMARY KEY REFERENCES optimization_runs(id) ON DELETE CASCADE,
  file_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(file_id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  total_cost NUMERIC NOT NULL,
  total_fire_ton NUMERIC NOT NULL,
  total_stock_ton NUMERIC NOT NULL,
  opened_rolls INT NOT NULL,
  total_tonnage NUMERIC NOT NULL,
  total_used_ton NUMERIC NOT NULL,
  material_usage_pct NUMERIC NOT NULL,
  fire_pct NUMERIC NOT NULL,
  total_panels INT NOT NULL,
  total_m2 NUMERIC NOT NULL,
  unique_rolls INT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- file_id FK (bazı kurulumlarda eksik kalabiliyor)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'optimization_run_metrics_file_id_fkey'
  ) THEN
    ALTER TABLE optimization_run_metrics
      ADD CONSTRAINT optimization_run_metrics_file_id_fkey
      FOREIGN KEY (file_id) REFERENCES optimization_runs(file_id) ON DELETE CASCADE;
  END IF;
EXCEPTION
  WHEN undefined_object THEN NULL;
  WHEN others THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS optimization_run_roll_status (
  id BIGSERIAL PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES optimization_runs(id) ON DELETE CASCADE,
  file_id TEXT NOT NULL,
  roll_id INT NOT NULL,
  total_tonnage NUMERIC NOT NULL,
  used_ton NUMERIC NOT NULL,
  remaining_ton NUMERIC NOT NULL,
  fire_ton NUMERIC NOT NULL,
  stock_ton NUMERIC NOT NULL,
  orders_used INT NOT NULL
);

CREATE TABLE IF NOT EXISTS optimization_run_cutting_plan (
  id BIGSERIAL PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES optimization_runs(id) ON DELETE CASCADE,
  file_id TEXT NOT NULL,
  roll_id INT NOT NULL,
  order_id INT NOT NULL,
  panel_count INT NOT NULL,
  panel_width NUMERIC NOT NULL,
  tonnage NUMERIC NOT NULL,
  m2 NUMERIC NOT NULL
);

-- 3) İndeksler
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_optimization_runs_file_id ON optimization_runs(file_id);
CREATE INDEX IF NOT EXISTS idx_optimization_runs_created_at ON optimization_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_optimization_runs_configuration_id ON optimization_runs(configuration_id);
CREATE INDEX IF NOT EXISTS idx_optimization_configurations_updated_at ON optimization_configurations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_sets_updated_at ON order_sets(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_sets_updated_at ON stock_sets(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_metrics_file_id ON optimization_run_metrics(file_id);
CREATE INDEX IF NOT EXISTS idx_roll_status_run_id ON optimization_run_roll_status(run_id);
CREATE INDEX IF NOT EXISTS idx_roll_status_file_id ON optimization_run_roll_status(file_id);
CREATE INDEX IF NOT EXISTS idx_cutting_plan_run_id ON optimization_run_cutting_plan(run_id);
CREATE INDEX IF NOT EXISTS idx_cutting_plan_file_id ON optimization_run_cutting_plan(file_id);
CREATE INDEX IF NOT EXISTS idx_cutting_plan_roll_order ON optimization_run_cutting_plan(run_id, roll_id, order_id);

-- 4) RLS açma (tablolar yoksa hata vermez)
-- -----------------------------------------------------------------------------

ALTER TABLE optimization_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_run_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_run_roll_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_run_cutting_plan ENABLE ROW LEVEL SECURITY;

-- 5) Politikalar: önce varsa kaldır, sonra oluştur (tüm ortamlarda çalışır)
-- -----------------------------------------------------------------------------

DO $$
BEGIN
  DROP POLICY IF EXISTS "Allow all for service role" ON optimization_runs;
  CREATE POLICY "Allow all for service role" ON optimization_runs
    FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'optimization_runs policy: %', SQLERRM;
END $$;

DO $$
BEGIN
  DROP POLICY IF EXISTS "Allow all for service role" ON optimization_configurations;
  CREATE POLICY "Allow all for service role" ON optimization_configurations
    FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'optimization_configurations policy: %', SQLERRM;
END $$;

DO $$
BEGIN
  DROP POLICY IF EXISTS "Allow all for service role" ON order_sets;
  CREATE POLICY "Allow all for service role" ON order_sets
    FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'order_sets policy: %', SQLERRM;
END $$;

DO $$
BEGIN
  DROP POLICY IF EXISTS "Allow all for service role" ON stock_sets;
  CREATE POLICY "Allow all for service role" ON stock_sets
    FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'stock_sets policy: %', SQLERRM;
END $$;

DO $$
BEGIN
  DROP POLICY IF EXISTS "Allow all for service role" ON optimization_run_metrics;
  CREATE POLICY "Allow all for service role" ON optimization_run_metrics
    FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'optimization_run_metrics policy: %', SQLERRM;
END $$;

DO $$
BEGIN
  DROP POLICY IF EXISTS "Allow all for service role" ON optimization_run_roll_status;
  CREATE POLICY "Allow all for service role" ON optimization_run_roll_status
    FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'optimization_run_roll_status policy: %', SQLERRM;
END $$;

DO $$
BEGIN
  DROP POLICY IF EXISTS "Allow all for service role" ON optimization_run_cutting_plan;
  CREATE POLICY "Allow all for service role" ON optimization_run_cutting_plan
    FOR ALL USING (true) WITH CHECK (true);
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'optimization_run_cutting_plan policy: %', SQLERRM;
END $$;

-- =============================================================================
-- Storage: Supabase Dashboard > Storage > New bucket
-- - Bucket adı: optimization-reports
-- - Public: Evet (rapor indirme için)
-- =============================================================================
