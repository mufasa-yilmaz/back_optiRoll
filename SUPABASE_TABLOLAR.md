# Supabase tabloları – OptiRoll

Canlıda tablo/kolon hatası alıyorsanız **Supabase Dashboard > SQL Editor** üzerinden aşağıdaki dosyayı çalıştırın:

- **`supabase_migrate_all.sql`** – Tüm tabloları oluşturur, eksik kolonları ekler, RLS politikalarını ayarlar. Birden fazla kez çalıştırılabilir (idempotent).

## Beklenen tablolar

| Tablo | Açıklama |
|-------|----------|
| `optimization_runs` | Optimizasyon çalıştırmaları (file_id, summary, cutting_plan, roll_status, report_url) |
| `optimization_configurations` | Kayıtlı konfigürasyonlar (malzeme, maliyet, sipariş listesi) |
| `order_sets` | Hazır sipariş setleri |
| `stock_sets` | Hazır stok/rulo setleri |
| `optimization_run_metrics` | Çalıştırma KPI’ları (run_id, file_id ile) |
| `optimization_run_roll_status` | Rulo bazlı durum detayı |
| `optimization_run_cutting_plan` | Kesim planı detayı (rulo–sipariş kırılımı) |

## Storage

- **Bucket:** `optimization-reports` (public, rapor indirme için)

## Kontrol

SQL Editor’da şunu çalıştırarak tabloları listeleyebilirsiniz:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

Eksik tablo varsa `supabase_migrate_all.sql` dosyasını tekrar çalıştırın.
