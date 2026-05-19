# backend/reports — Rapor klasörü rehberi

Bu klasöre üretilen tüm test/tez/sensitivity raporları `suite_<ts>/` tarzında zaman
damgalı kök klasör içinde durur. Her alt klasörün yapısı ve üretim komutları aşağıdadır.

## Klasör yapısı

```
backend/reports/
├── README.md                          (bu dosya)
├── .gitignore                         (tüm *_ts klasörleri git dışı)
├── thesis_suite_<ts>/                 ← Tez doğrulama 7 senaryosu
│   ├── INDEX.md
│   ├── baseline_ozeti.md
│   ├── test_<N>_<slug>/
│   │   ├── cozum_raporu.xlsx          (5 sayfa + Grafikler)
│   │   ├── rapor.md
│   │   ├── metrikler.csv
│   │   └── grafikler/kesim_semasi.png
│   └── _karsilastirma/
│       ├── karsilastirma.xlsx / .md / .csv
│       └── grafikler/*.png            (12 karşılaştırma grafiği)
├── fire_setup_grid_runs/              ← Yalnızca fire-setup grid (OFAT/tez ile karışmaz)
│   └── fire_setup_grid_<ts>/
│       ├── INDEX.md
│       ├── grid_tum_kosular.csv
│       └── _karsilastirma/
│           ├── karsilastirma.md / .xlsx   (.md görsel ön izleme; .xlsx’e ilk PNG’ler)
│           ├── grafikler/                 (12 bar + cap*_ic*_st*/ altında fire_mult line PNG)
│           ├── dual_success_summary.csv
│           └── demo_raporlar/
├── ofat_suite_<ts>/                   ← OFAT duyarlılık 9 ekseni
│   ├── INDEX.md, baseline_ozeti.md
│   ├── test_<N>_<axis>_<aralik>/
│   │   ├── ofat_rapor.xlsx
│   │   ├── rapor.md
│   │   ├── metrikler.csv
│   │   ├── axis_noktalari/<carpan_X>/cozum_raporu.xlsx
│   │   └── grafikler/*_line.png       (5 line grafik/eksen)
│   └── _karsilastirma/
│       ├── karsilastirma.xlsx / .md / .csv
│       └── grafikler/eksenler_{fire,maliyet}_normalize.png
└── unit_tests_<ts>/                   ← Birim test özeti
    ├── ozet.xlsx, rapor.md, metrikler.csv
    └── grafikler/{pass_fail_pie,test_suresi_bar}.png
```

`main/sonuclar/batch_<ts>/` altında da aynı format kullanılır (5 main senaryosu için).

## Koşum komutları

```bash
# Tez doğrulama 7 senaryosu (thesis_suite_<ts> üretir)
python backend/run_thesis_validation_scenarios.py
# Opsiyonel: sondaj senaryoları da
python backend/run_thesis_validation_scenarios.py --with-infeasible-probes

# OFAT duyarlılık 9 ekseni (ofat_suite_<ts>)
python backend/run_sensitivity_analysis.py

# Fire-setup-interleaving grid (fire_setup_grid_<ts>)
python backend/run_fire_setup_comparison.py
python backend/run_fire_setup_comparison.py --quick
python backend/run_fire_setup_comparison.py --minimal --time-limit 45

# Birim testler XLSX raporu (unit_tests_<ts>)
python backend/run_unit_tests_report.py

# main/senaryolar.json 5 senaryo batch (main/sonuclar/batch_<ts>)
python main/run_senaryolar_batch.py
```

## Dosya türleri

| Dosya | Amaç |
|---|---|
| `cozum_raporu.xlsx` | main/sonuclar biçimine birebir uyumlu 5 sayfa + Grafikler (embed kesim şeması) |
| `rapor.md` | Hızlıca okunan senaryo özeti (phase/solver/fire/maliyet + kesim senaryosu) |
| `metrikler.csv` | Tek satırlık metrik kaydı (karşılaştırma CSV'leri ile birleştirilir) |
| `karsilastirma.xlsx` | Suite geneli Ozet + Maliyet + Detay + Grafikler |
| `karsilastirma.md` / `.csv` | Suite geneli okunabilir özet + CSV birleşimi |
| `grafikler/*.png` | 150 dpi bar/line/stacked/kesim_semasi figürleri |
| `INDEX.md` | Suite kök rehberi — klasör listesi + baseline özeti |
| `baseline_ozeti.md` | Suite sabit girdileri |
| `grid_tum_kosular.csv` | Fire-setup grid: her hücre için metrikler + fire/stock/setup çarpanları |
| `dual_success_summary.csv` | Fire-ucuz / fire-pahalı / referans grup özetleri ve `dual_success` bayrağı |

### Fire-setup grid Suite (`fire_setup_grid_runs/fire_setup_grid_<ts>`)

- **Sütunlar:** `fire_cost_mult`, `setup_cost_mult` (gridde 1.0 sabit), `stock_cost_mult`, `interleaving_penalty_cost`, `roll_capacity_ton`; metrikler `toplam_fire`, `rulo_degisim_sayisi`, `uretim_hatti_rulo_gecis_sayisi`, `acilan_rulo`, maliyet kırılımları.
- **Fire üretimi (A):** fire çarpanı düşük profilde `totalFire ≥ 0.05 t` veya `fire_orani_pct` referansa (aynı kapasitede `fire_mult=1`) göre ≥ +0.5 puan.
- **Geçiş artışı (B vs A):** fire çarpanı yüksek profilde `rollChangeCount ≥ A+2` veya hat geçişi ≥ A+2 veya `openedRolls ≥ A+1`.
- **Çift başarılı (`dual_success`):** Aynı `(kapasite, interleaving, stock_mult)` grubunda yukarıdaki iki koşum birlikte sağlanır.

## Karşılaştırma grafiği seti (tez ve main batch için ortak)

Her `_karsilastirma/grafikler/` altında şu 12 PNG bulunur:
`fire_bar`, `stok_bar`, `kullanilan_ton_bar`, `acilan_rulo_bar`, `maliyet_toplam_bar`,
`maliyet_kirilim_stacked`, `ton_kirilim_stacked`, `rulo_degisim_bar`, `hat_gecis_bar`,
`fire_orani_bar`, `kapasite_kullanim_bar`, `metrik_trend_line`.

OFAT için eksen başına 5 line grafik (fire / stok / maliyet / rulo / kapasite) + suite
düzeyinde 2 normalize trend üretilir.

## Ortak modüller

- `run_fire_setup_comparison.py` — Fire × kapasite × `interleavingPenaltyCost` grid suite üretimi
- `thesis_xlsx_report.py` — `build_cozum_raporu_xlsx`, `karsilastirma_xlsx`
- `thesis_chart_builder.py` — bar/line/stacked/kesim_semasi/pie PNG üreticileri
- `thesis_report_common.py` — slug, klasör iskeleti, INDEX/rapor/karsilastirma MD yazıcıları

Tüm grafikler `matplotlib` (Agg backend) + `DejaVu Sans` ile Türkçe karakter uyumlu çizilir
ve XLSX `Grafikler` sayfasına `openpyxl.drawing.image.Image` ile gömülür.
