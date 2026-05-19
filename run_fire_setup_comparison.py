#!/usr/bin/env python3
"""
5 sipariş + çoklu rulo için fire × kapasite × sıra cezası grid karşılaştırması.

Çıktı: reports/fire_setup_grid_runs/fire_setup_grid_<timestamp>/ (diğer suite'lerden ayrı kök).
"""

from __future__ import annotations

import argparse
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from thesis_ofat_baseline import (
    DEFAULT_MAX_ORDERS_PER_ROLL,
    DEFAULT_MAX_ROLLS_PER_ORDER,
    DEFAULT_ROLLS_BAND,
    DEFAULT_ROLLS_SEED,
    DEFAULT_SETUP_COST,
    baseline_costs,
    baseline_orders_multi,
)
from thesis_chart_builder import ofat_eksen_line_grafikleri, senaryo_seti_karsilastirma_grafikleri
from thesis_report_common import (
    coklu_satir_csv_yaz,
    index_md_yaz,
    karsilastirma_klasoru_hazirla,
    karsilastirma_md_yaz,
    metrik_satiri_derle,
    safe_slug,
    simdi_ts,
    suite_kok_olustur,
)
from thesis_test_harness import test_calistir
from thesis_xlsx_report import build_cozum_raporu_xlsx, karsilastirma_xlsx, scenario_meta_from_test_calistir

# Tez / OFAT / birim test klasörleriyle karışmaması için sabit üst dizin adı
FIRE_SETUP_SUITE_PARENT_DIR = "fire_setup_grid_runs"

# Grafik çıktıları: tam gridde yüzlerce çubuk okunamaz; Optimal koşuları örneklemek için tavanlar
_FIRE_GRID_BAR_CHART_ROW_CAP = 96
_FIRE_GRID_FIRE_LINE_BUCKET_CAP = 36


def fire_setup_reports_parent(reports_root: Optional[str]) -> str:
    """
    Fire-setup suite'lerinin yazılacağı üst klasörü döner.

    Varsayılan: backend/reports/fire_setup_grid_runs
    `--out X` verilirse: X/fire_setup_grid_runs

    Args:
        reports_root: None ise backend/reports kullanılır; aksi halde kullanıcı kökü

    Returns:
        Zaman damgalı suite klasörünün bir üst dizini (oluşturulmuş tam yol)
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    base = reports_root if reports_root is not None else os.path.join(backend_dir, "reports")
    parent = os.path.join(base, FIRE_SETUP_SUITE_PARENT_DIR)
    os.makedirs(parent, exist_ok=True)
    return parent


def _baseline_aciklama_text() -> str:
    """
    INDEX ve raporlarda kullanılan sabit baseline özet cümlesi üretir.

    Returns:
        Türkçe özet metni
    """
    return (
        "5 sipariş (baseline_orders_multi), rolls_band=(4,13), rolls_seed=42, "
        f"maxOrdersPerRoll={DEFAULT_MAX_ORDERS_PER_ROLL}, maxRollsPerOrder={DEFAULT_MAX_ROLLS_PER_ORDER}; "
        "kurulum çarpanı grid boyunca 1.0 (birim kurulum sabit)."
    )


def _grafik_huc_etiketi(row: Dict[str, Any]) -> str:
    """
    Bar grafiklerde kullanılacak kısa hücre etiketi üretir.

    Args:
        row: Grid CSV satırı

    Returns:
        Örn. 'k110 ic0 fx0.1'
    """
    cap = row.get("roll_capacity_ton", "?")
    ic = float(row.get("interleaving_penalty_cost") or 0.0)
    ic_lbl = str(int(ic)) if abs(ic - round(ic)) < 1e-9 else str(ic)
    fm = row.get("fire_cost_mult", "?")
    return f"k{cap} ic{ic_lbl} fx{fm}"


def _referans_fire_mult_chart(axis_vals: Sequence[float]) -> float:
    """
    OFAT line grafikleri için referans dikey çizgi: 1.0 varsa onu; yoksa en yakın fire çarpanı.

    Args:
        axis_vals: Bucket içindeki fire_cost_mult listesi

    Returns:
        Referans x değeri
    """
    vs = sorted(float(x) for x in axis_vals)
    if not vs:
        return 1.0
    if any(abs(v - 1.0) < 1e-9 for v in vs):
        return 1.0
    return min(vs, key=lambda v: abs(v - 1.0))


def yaz_fire_suite_grafikleri(
    all_rows: List[Dict[str, Any]],
    bucket_keys: Dict[Tuple[float, float, float], List[Dict[str, Any]]],
    grafikler_dir: str,
    *,
    alt_baslik: str,
    bar_row_cap: int = _FIRE_GRID_BAR_CHART_ROW_CAP,
    line_bucket_cap: int = _FIRE_GRID_FIRE_LINE_BUCKET_CAP,
) -> List[str]:
    """
    OFAT/tez ile uyumlu 12 bar grafik + her bucket için fire çarpanı line seti üretir.

    Args:
        all_rows: Tüm grid satırları
        bucket_keys: (kapasite, interleaving, stock_mult) → satırlar
        grafikler_dir: Çıktı klasörü (genelde _karsilastirma/grafikler)
        alt_baslik: Grafik dipnotları
        bar_row_cap: Bar grafikte en fazla kaç Optimal hücre
        line_bucket_cap: En fazla kaç bucket için line grafik (dosya şişmesini sınırlar)

    Returns:
        Üretilen PNG dosya yolları (sırayla bar seti sonra line setleri)
    """
    merged: List[str] = []

    optimal = [r for r in all_rows if r.get("solver_status") == "Optimal"]
    if bar_row_cap > 0 and len(optimal) > bar_row_cap:
        step = max(1, math.ceil(len(optimal) / bar_row_cap))
        optimal = optimal[::step][:bar_row_cap]

    bar_input: List[Dict[str, Any]] = []
    for r in optimal:
        g = dict(r)
        g["senaryo_adi"] = _grafik_huc_etiketi(r)
        bar_input.append(g)

    if bar_input:
        merged.extend(senaryo_seti_karsilastirma_grafikleri(bar_input, grafikler_dir, alt_baslik=alt_baslik))

    buckets_done = 0
    for key in sorted(bucket_keys.keys(), key=lambda k: (k[0], k[1], k[2])):
        if buckets_done >= line_bucket_cap:
            break
        brow = bucket_keys[key]
        sub = sorted(
            [x for x in brow if x.get("solver_status") == "Optimal"],
            key=lambda x: float(x.get("fire_cost_mult") or 0),
        )
        if len(sub) < 2:
            continue
        cap, ic, sm = key
        slug = safe_slug(f"cap{cap}_ic{int(ic) if abs(ic-round(ic))<1e-9 else ic}_st{sm}")
        sub_dir = os.path.join(grafikler_dir, slug)
        axis_vals = [float(x.get("fire_cost_mult") or 0.0) for x in sub]
        ref_fm = _referans_fire_mult_chart(axis_vals)
        merged.extend(
            ofat_eksen_line_grafikleri(
                "fire_cost_mult",
                axis_vals,
                sub,
                sub_dir,
                referans_axis_value=ref_fm,
                alt_baslik=f"kap={cap} t  ic={ic}  st×={sm}",
            )
        )
        buckets_done += 1

    return merged


def run_single_cell(
    roll_capacity_ton: float,
    orders: List[Dict[str, Any]],
    *,
    fire_mult: float,
    setup_mult: float,
    stock_mult: float,
    interleaving_penalty_cost: float,
    time_limit_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Tek bir grid hücresi için test_calistir çalıştırır ve satır paketi döner.

    Args:
        roll_capacity_ton: Toplam rulo kapasitesi (ton)
        orders: Sipariş listesi (m² / panel ölçüleri)
        fire_mult: Referans fire maliyetine göre çarpan
        setup_mult: Kurulum çarpanı
        stock_mult: Stok çarpanı
        interleaving_penalty_cost: Sıra / araya girme ceza birimi
        time_limit_seconds: Çözücü zaman sınırı

    Returns:
        CSV satırı + ham sonuç (`row`, `raw_calistir`) içeren sözlük
    """
    costs = baseline_costs(fire_mult=fire_mult, stock_mult=stock_mult, setup_mult=setup_mult)
    fc = float(costs["fire_cost"])
    sc = float(costs["stock_cost"])
    stc = float(costs["setup_cost"])

    cal = test_calistir(
        roll_capacity_ton,
        orders,
        fire_cost=fc,
        setup_cost=stc,
        stock_cost=sc,
        max_orders_per_roll=DEFAULT_MAX_ORDERS_PER_ROLL,
        max_rolls_per_order=DEFAULT_MAX_ROLLS_PER_ORDER,
        interleaving_penalty_cost=float(interleaving_penalty_cost),
        time_limit_seconds=int(time_limit_seconds),
        rolls_band=DEFAULT_ROLLS_BAND,
        rolls_seed=int(DEFAULT_ROLLS_SEED),
    )

    scenario_meta = scenario_meta_from_test_calistir(
        senaryo_adi=f"cap={roll_capacity_ton} fire×{fire_mult} ic={interleaving_penalty_cost}",
        sonuc=cal,
        siparisler=orders,
        fire_cost=fc,
        setup_cost=stc,
        stock_cost=sc,
        max_siparis_per_rulo=DEFAULT_MAX_ORDERS_PER_ROLL,
        max_rulo_per_siparis=DEFAULT_MAX_ROLLS_PER_ORDER,
        aciklama=(
            f"interleavingPenaltyCost={interleaving_penalty_cost}; "
            f"fire_mult={fire_mult}; setup_mult={setup_mult}; stock_mult={stock_mult}; "
            f"referans kurulum birimi={DEFAULT_SETUP_COST}"
        ),
    )

    metrik = metrik_satiri_derle(
        senaryo_adi=f"{roll_capacity_ton}t_fire×{fire_mult}_ic×{interleaving_penalty_cost}",
        girdi_ozeti=_baseline_aciklama_text(),
        sonuc=cal,
        scenario_meta=scenario_meta,
        passed="PASS" if cal.get("solver_status") == "Optimal" else "",
    )

    row = {
        **metrik,
        "roll_capacity_ton": roll_capacity_ton,
        "fire_cost_mult": fire_mult,
        "setup_cost_mult": setup_mult,
        "stock_cost_mult": stock_mult,
        "interleaving_penalty_cost": interleaving_penalty_cost,
        "input_fire_cost": fc,
        "input_setup_cost": stc,
        "input_stock_cost": sc,
    }
    return {"row": row, "raw_calistir": cal, "scenario_meta": scenario_meta, "orders": orders}


def fire_ratio_pct(row: Dict[str, Any]) -> float:
    """
    Grid satırından fire / kapasite yüzdesini döner.

    Args:
        row: metrik_satiri_derle çıktısı ile genişletilmiş satır

    Returns:
        Yüzde (0–100 ölçeği)
    """
    return float(row.get("fire_orani_pct") or 0.0)


def passes_fire_shift_criterion(row_a: Dict[str, Any], row_ref: Dict[str, Any]) -> bool:
    """
    Fire-ucuz profilin referansa göre 'fire üretimi' kriterini sağlayıp sağlamadığını döner.

    Args:
        row_a: Fire çarpanı düşük hücre satırı
        row_ref: Aynı kapasite / interleaving için fire_mult=1 referans satırı

    Returns:
        True ise totalFire eşiği veya fire_orani_pct artışı koşulu sağlanır
    """
    tf_a = float(row_a.get("toplam_fire") or 0.0)
    if tf_a >= 0.05:
        return True
    ref_pct = fire_ratio_pct(row_ref)
    return fire_ratio_pct(row_a) >= ref_pct + 0.5


def passes_transition_shift_criterion(row_b: Dict[str, Any], row_a: Dict[str, Any]) -> bool:
    """
    Fire-pahalı profilin fire-ucuza göre rulo geçiş metriklerinde belirgin artış gösterip göstermediğini döner.

    Args:
        row_b: Fire çarpanı yüksek hücre satırı
        row_a: Fire çarpanı düşük hücre satırı

    Returns:
        True ise kesim dilimi geçişi, hat geçişi veya açılan rulo eşiklerinden biri tutar
    """
    rc_b = int(row_b.get("rulo_degisim_sayisi") or 0)
    rc_a = int(row_a.get("rulo_degisim_sayisi") or 0)
    lt_b = int(row_b.get("uretim_hatti_rulo_gecis_sayisi") or 0)
    lt_a = int(row_a.get("uretim_hatti_rulo_gecis_sayisi") or 0)
    op_b = int(row_b.get("acilan_rulo") or 0)
    op_a = int(row_a.get("acilan_rulo") or 0)
    return (
        rc_b >= rc_a + 2
        or lt_b >= lt_a + 2
        or op_b >= op_a + 1
    )


def pick_best_cheap_row(
    optimal_rows_by_fire: Dict[float, Dict[str, Any]],
    cheap_fire_mults: Sequence[float],
) -> Optional[Dict[str, Any]]:
    """
    Optimal fire-ucuz adayları arasından fire tonunu maksimize eden satırı seçer.

    Args:
        optimal_rows_by_fire: fire_mult → tam CSV satırı (yalnız Optimal olanlar)
        cheap_fire_mults: Ucuz profil çarpanları

    Returns:
        Seçilen satır veya uygun aday yoksa None
    """
    candidates: List[Dict[str, Any]] = []
    for m in cheap_fire_mults:
        r = optimal_rows_by_fire.get(float(m))
        if r is not None:
            candidates.append(r)
    if not candidates:
        return None
    return max(candidates, key=lambda x: float(x.get("toplam_fire") or 0.0))


def pick_best_expensive_row_for_transitions(
    optimal_rows_by_fire: Dict[float, Dict[str, Any]],
    expensive_fire_mults: Sequence[float],
    row_a: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Optimal fire-pahalı adayları arasından geçiş skorunu (özet metrik) maksimize eden satırı seçer.

    Args:
        optimal_rows_by_fire: fire_mult → satır
        expensive_fire_mults: Pahalı profil çarpanları
        row_a: Karşılaştırılacak ucuz satır

    Returns:
        Seçilen satır veya None
    """
    rc_a = int(row_a.get("rulo_degisim_sayisi") or 0)
    lt_a = int(row_a.get("uretim_hatti_rulo_gecis_sayisi") or 0)
    op_a = int(row_a.get("acilan_rulo") or 0)

    def score(rb: Dict[str, Any]) -> Tuple[int, int, int]:
        """Geçiş artışına göre skor anahtarı üretir."""
        return (
            int(rb.get("rulo_degisim_sayisi") or 0) - rc_a,
            int(rb.get("uretim_hatti_rulo_gecis_sayisi") or 0) - lt_a,
            int(rb.get("acilan_rulo") or 0) - op_a,
        )

    candidates: List[Dict[str, Any]] = []
    for m in expensive_fire_mults:
        r = optimal_rows_by_fire.get(float(m))
        if r is not None:
            candidates.append(r)
    if not candidates:
        return None
    return max(candidates, key=lambda rb: score(rb))


def score_dual_success_pair(row_ref: Dict[str, Any], row_a: Dict[str, Any], row_b: Dict[str, Any]) -> float:
    """
    Çift başarılı kombinasyonları sıralamak için tek sayılı özet skor üretir.

    Args:
        row_ref: Referans satırı (fire_mult=1)
        row_a: Fire ucuz satırı
        row_b: Fire pahalı satırı

    Returns:
        Büyük olan daha iyi (fire üretimi + geçiş artışı ağırlıklı)
    """
    tf_gain = float(row_a.get("toplam_fire") or 0.0) - float(row_ref.get("toplam_fire") or 0.0)
    trans_gain = (
        int(row_b.get("rulo_degisim_sayisi") or 0)
        - int(row_a.get("rulo_degisim_sayisi") or 0)
        + 0.5 * (
            int(row_b.get("uretim_hatti_rulo_gecis_sayisi") or 0)
            - int(row_a.get("uretim_hatti_rulo_gecis_sayisi") or 0)
        )
    )
    return float(tf_gain) * 10.0 + float(trans_gain)


def evaluate_dual_success_for_bucket(
    rows_for_bucket: Sequence[Dict[str, Any]],
    *,
    cheap_fire_mults: Sequence[float],
    expensive_fire_mults: Sequence[float],
    ref_fire_mult: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Aynı (kapasite, interleaving, stock_mult) için fire ucuz / referans / pahalı üçlüsünü analiz eder.

    Args:
        rows_for_bucket: Bu anahtara ait tüm grid satırları
        cheap_fire_mults: Ucuz çarpan kümesi
        expensive_fire_mults: Pahalı çarpan kümesi
        ref_fire_mult: Referans çarpanı (varsayılan 1.0)

    Returns:
        dual_success bayrakları ve metrik farkları içeren özet sözlükler listesi
    """
    optimal: Dict[float, Dict[str, Any]] = {}
    for r in rows_for_bucket:
        if r.get("solver_status") != "Optimal":
            continue
        fm = float(r.get("fire_cost_mult") or 0.0)
        optimal[fm] = r

    row_ref = optimal.get(float(ref_fire_mult))
    row_a = pick_best_cheap_row(optimal, cheap_fire_mults)
    if row_ref is None or row_a is None:
        return []

    row_b = pick_best_expensive_row_for_transitions(optimal, expensive_fire_mults, row_a)
    if row_b is None:
        return []

    fire_ok = passes_fire_shift_criterion(row_a, row_ref)
    trans_ok = passes_transition_shift_criterion(row_b, row_a)
    dual = bool(fire_ok and trans_ok)

    summary = {
        "roll_capacity_ton": row_ref.get("roll_capacity_ton"),
        "interleaving_penalty_cost": row_ref.get("interleaving_penalty_cost"),
        "stock_cost_mult": row_ref.get("stock_cost_mult"),
        "fire_ok_vs_ref": fire_ok,
        "trans_ok_B_vs_A": trans_ok,
        "dual_success": dual,
        "score": score_dual_success_pair(row_ref, row_a, row_b),
        "ref_fire_mult": ref_fire_mult,
        "ref_totalFire": row_ref.get("toplam_fire"),
        "ref_rollChangeCount": row_ref.get("rulo_degisim_sayisi"),
        "ref_lineTransitions": row_ref.get("uretim_hatti_rulo_gecis_sayisi"),
        "A_fire_mult": row_a.get("fire_cost_mult"),
        "A_totalFire": row_a.get("toplam_fire"),
        "A_rollChangeCount": row_a.get("rulo_degisim_sayisi"),
        "A_lineTransitions": row_a.get("uretim_hatti_rulo_gecis_sayisi"),
        "B_fire_mult": row_b.get("fire_cost_mult"),
        "B_totalFire": row_b.get("toplam_fire"),
        "B_rollChangeCount": row_b.get("rulo_degisim_sayisi"),
        "B_lineTransitions": row_b.get("uretim_hatti_rulo_gecis_sayisi"),
    }
    return [summary]


def run_comparison_suite(
    *,
    reports_root: Optional[str] = None,
    quick: bool = False,
    minimal: bool = False,
    stock_mults: Optional[Sequence[float]] = None,
    time_limit_seconds: int = 120,
    write_detail_xlsx_top_n: int = 2,
) -> Dict[str, Any]:
    """
    Tam grid veya quick grid çalıştırır; suite klasörü ve karşılaştırma çıktılarını üretir.

    Args:
        reports_root: Rapor kökü (None ise backend/reports); suite her zaman .../fire_setup_grid_runs/ altına yazılır
        quick: True ise dar grid (kapasite × fire × interleaving küçük)
        minimal: True ise pytest/CI için tek kapasite ve üç fire çarpanı (çok kısa süre)
        stock_mults: Stok çarpanı listesi (varsayılan [1.0])
        time_limit_seconds: Çözücü zaman sınırı
        write_detail_xlsx_top_n: dual_success sıralamasında ilk N çift için A/B tam rapor xlsx

    Returns:
        suite_yolu, dual_success sayısı ve özet listesi içeren sözlük
    """
    ts = simdi_ts()
    suite_name = f"fire_setup_grid_{ts}"
    rap_parent = fire_setup_reports_parent(reports_root)
    suite_kok = suite_kok_olustur(rap_parent, suite_name)

    stock_mult_list = list(stock_mults) if stock_mults is not None else [1.0]

    if minimal:
        capacities = [110.0]
        fire_mults = [0.1, 1.0, 10.0]
        interleaving_levels = [0.0]
    elif quick:
        capacities = [72.0, 85.0, 110.0]
        fire_mults = [0.1, 1.0, 10.0]
        interleaving_levels = [0.0, 100.0]
    else:
        capacities = [72.0, 78.0, 85.0, 95.0, 110.0, 120.0]
        fire_mults = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
        interleaving_levels = [0.0, 25.0, 100.0, 250.0]

    cheap_fire_mults = [m for m in fire_mults if m <= 0.25]
    expensive_fire_mults = [m for m in fire_mults if m >= 5.0]
    setup_mult_fixed = 1.0

    orders = baseline_orders_multi(5, 1.0)

    cell_packages: List[Dict[str, Any]] = []
    all_rows: List[Dict[str, Any]] = []

    for cap in capacities:
        for icost in interleaving_levels:
            for smult in stock_mult_list:
                for fm in fire_mults:
                    pkg = run_single_cell(
                        cap,
                        orders,
                        fire_mult=fm,
                        setup_mult=setup_mult_fixed,
                        stock_mult=smult,
                        interleaving_penalty_cost=icost,
                        time_limit_seconds=time_limit_seconds,
                    )
                    cell_packages.append(pkg)
                    all_rows.append(pkg["row"])

    grid_csv = os.path.join(suite_kok, "grid_tum_kosular.csv")
    coklu_satir_csv_yaz(grid_csv, all_rows)

    summaries: List[Dict[str, Any]] = []
    bucket_keys: Dict[Tuple[float, float, float], List[Dict[str, Any]]] = {}

    for r in all_rows:
        key = (
            float(r.get("roll_capacity_ton") or 0),
            float(r.get("interleaving_penalty_cost") or 0),
            float(r.get("stock_cost_mult") or 1.0),
        )
        bucket_keys.setdefault(key, []).append(r)

    for key, bucket_rows in bucket_keys.items():
        summaries.extend(
            evaluate_dual_success_for_bucket(
                bucket_rows,
                cheap_fire_mults=cheap_fire_mults,
                expensive_fire_mults=expensive_fire_mults,
            )
        )

    dual_success = [s for s in summaries if s.get("dual_success")]
    dual_success.sort(key=lambda s: float(s.get("score") or 0.0), reverse=True)

    kk = karsilastirma_klasoru_hazirla(suite_kok)
    coklu_satir_csv_yaz(os.path.join(kk["klasor"], "dual_success_summary.csv"), summaries)

    graf_paths = yaz_fire_suite_grafikleri(
        all_rows,
        bucket_keys,
        kk["grafikler_dir"],
        alt_baslik=_baseline_aciklama_text(),
    )
    kk_dir = kk["klasor"]
    md_grafik_listesi = [
        os.path.relpath(p, kk_dir).replace("\\", "/") for p in graf_paths
    ]

    top_table_rows = dual_success[:10]
    md_headers = [
        "kap_t",
        "ic",
        "A_fire×",
        "A_fire_t",
        "B_fire×",
        "B_rc",
        "A_rc",
        "skor",
    ]
    md_body: List[List[Any]] = []
    for s in top_table_rows:
        md_body.append(
            [
                s.get("roll_capacity_ton"),
                s.get("interleaving_penalty_cost"),
                s.get("A_fire_mult"),
                s.get("A_totalFire"),
                s.get("B_fire_mult"),
                s.get("B_rollChangeCount"),
                s.get("A_rollChangeCount"),
                round(float(s.get("score") or 0.0), 4),
            ]
        )

    yorum_parts = [
        "**Referans:** Her grupta `fire_cost_mult=1.0`, kurulum çarpanı 1.0 (birim kurulum sabit).",
        "**Fire üretimi (A):** `totalFire ≥ 0.05 t` veya `fire_orani_pct` referansa göre ≥ +0.5 puan.",
        "**Geçiş artışı (B vs A):** `rollChangeCount ≥ A+2` veya hat geçişi ≥ A+2 veya `openedRolls ≥ A+1`.",
        "**Çift başarılı:** Yukarıdaki iki koşum aynı (kapasite, interleaving, stock_mult) grubunda birden sağlanır.",
    ]
    if not dual_success:
        yorum_parts.append(
            "**Uyarı:** Bu grid kombinasyonlarında çift başarılı özet bulunamadı. "
            "Kapasiteyi 110–120 t bandına çekmeyi veya `interleavingPenaltyCost` / fire çarpanı uçlarını "
            "genişletmeyi deneyin (bkz. tam grid)."
        )

    karsilastirma_md_yaz(
        kk["karsilastirma_md"],
        baslik="Fire / kurulum / sıra cezası karşılaştırması",
        aciklama=_baseline_aciklama_text(),
        tablo_basliklari=md_headers,
        tablo_satirlari=md_body,
        grafik_listesi=md_grafik_listesi[:42],
        ek_yorum=(
            "**Grafikler:** Tam set `_karsilastirma/grafikler/` klasöründe; "
            "12 bar grafik (Optimal hücrelerin örneklemi) ve her bucket için `fire_cost_mult` ekseninde line grafikleri. "
            "Aşağıda ilk birkaçı ön izleme olarak verilmiştir.\n\n"
            + "\n\n".join(yorum_parts)
        ),
    )

    xlsx_summary_rows: List[Dict[str, Any]] = []
    for s in summaries[: min(200, len(summaries))]:
        xlsx_summary_rows.append({str(k): v for k, v in s.items()})
    karsilastirma_xlsx(
        xlsx_summary_rows,
        kk["karsilastirma_xlsx"],
        baslik="Fire-setup-interleaving grid özeti",
        grafik_yollari=[p for p in graf_paths[:20] if p],
    )

    demo_dir = os.path.join(kk["klasor"], "demo_raporlar")
    os.makedirs(demo_dir, exist_ok=True)

    # İlk N çift başarılı kombinasyon için A ve B tam Excel raporu yaz
    written_pairs = 0
    for s in dual_success:
        if written_pairs >= write_detail_xlsx_top_n:
            break
        cap = float(s["roll_capacity_ton"])
        ic = float(s["interleaving_penalty_cost"])
        sm = float(s["stock_cost_mult"])
        fm_a = float(s["A_fire_mult"])
        fm_b = float(s["B_fire_mult"])

        pkg_a = next(
            (
                p
                for p in cell_packages
                if float(p["row"]["roll_capacity_ton"]) == cap
                and float(p["row"]["interleaving_penalty_cost"]) == ic
                and float(p["row"]["stock_cost_mult"]) == sm
                and float(p["row"]["fire_cost_mult"]) == fm_a
            ),
            None,
        )
        pkg_b = next(
            (
                p
                for p in cell_packages
                if float(p["row"]["roll_capacity_ton"]) == cap
                and float(p["row"]["interleaving_penalty_cost"]) == ic
                and float(p["row"]["stock_cost_mult"]) == sm
                and float(p["row"]["fire_cost_mult"]) == fm_b
            ),
            None,
        )
        if not pkg_a or not pkg_b:
            continue

        slug = f"pair_{written_pairs + 1}_cap{int(cap)}_ic{int(ic)}"
        pa = os.path.join(demo_dir, f"{slug}_A_fire_{str(fm_a).replace('.', 'p')}.xlsx")
        pb = os.path.join(demo_dir, f"{slug}_B_fire_{str(fm_b).replace('.', 'p')}.xlsx")
        build_cozum_raporu_xlsx(scenario_meta=pkg_a["scenario_meta"], sonuc=pkg_a["raw_calistir"], output_path=pa)
        build_cozum_raporu_xlsx(scenario_meta=pkg_b["scenario_meta"], sonuc=pkg_b["raw_calistir"], output_path=pb)
        written_pairs += 1

    index_md_yaz(
        os.path.join(suite_kok, "INDEX.md"),
        baslik="Fire-setup-interleaving karşılaştırma grid'i",
        ts=ts,
        baseline_ozeti=_baseline_aciklama_text(),
        senaryolar_tablosu=[
            ["Dosya", "Açıklama"],
            ["grid_tum_kosular.csv", "Tüm LP koşuları (satır başına metrikler)"],
            ["_karsilastirma/karsilastirma.md", "Özet tablo + Grafik ön izleme bağlantıları"],
            ["_karsilastirma/grafikler/", "12 bar + bucket başına fire_mult line grafikleri (PNG)"],
            ["_karsilastirma/karsilastirma.xlsx", "Özet + gömülü Grafikler sayfası (ilk PNG’ler)"],
            ["_karsilastirma/dual_success_summary.csv", "Tüm grup özetleri (dual_success bayrakları)"],
            ["_karsilastirma/demo_raporlar/", "İlk çift başarılı kombinasyonlar için tam cozum_raporu.xlsx"],
        ],
        ek_aciklama=(
            "`kurulum` birimi sabittir (`setup_cost_mult=1.0`). "
            "Sıra / hat davranışı için API'deki `interleavingPenaltyCost` kullanılır. "
            "`minimal` veya unittest ile birkaç koşuda davranış doğrulanır; tam karşılaştırma için "
            "argümansız çalıştırın."
        ),
    )

    witness_fire_shift = any(bool(s.get("fire_ok_vs_ref")) for s in summaries)
    witness_trans_shift = any(bool(s.get("trans_ok_B_vs_A")) for s in summaries)

    return {
        "suite_root": suite_kok,
        "reports_parent": rap_parent,
        "grid_csv": grid_csv,
        "dual_success_count": len(dual_success),
        "dual_success_summaries": dual_success,
        "total_runs": len(all_rows),
        "demo_reports_written": written_pairs,
        "witness_fire_shift": witness_fire_shift,
        "witness_transition_shift": witness_trans_shift,
        "graf_paths": graf_paths,
    }


def main() -> None:
    """CLI giriş noktası: argparse ile suite çalıştırır."""
    parser = argparse.ArgumentParser(description="Fire-setup-interleaving grid karşılaştırması")
    parser.add_argument(
        "--out",
        dest="reports_root",
        default=None,
        help=(
            "Rapor kök dizini (varsayılan: backend/reports); çıktılar her zaman "
            "<kök>/fire_setup_grid_runs/ altına yazılır"
        ),
    )
    parser.add_argument("--quick", action="store_true", help="Dar grid (pytest / hızlı tarama)")
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Tek kapasite (110 t), interleaving=0, fire [0.1,1,10] — çok hızlı keşif",
    )
    parser.add_argument(
        "--stock-mults",
        type=float,
        nargs="*",
        default=[1.0],
        help="Stok maliyeti çarpanı listesi (varsayılan: 1.0)",
    )
    parser.add_argument("--time-limit", type=int, default=120, dest="time_limit", help="Çözücü süre sınırı (sn)")
    parser.add_argument(
        "--demo-xlsx-count",
        type=int,
        default=2,
        dest="demo_xlsx_count",
        help="Çift başarılı sıralamada kaç çift için tam Excel yazılsın",
    )
    args = parser.parse_args()

    res = run_comparison_suite(
        reports_root=args.reports_root,
        quick=args.quick,
        minimal=args.minimal,
        stock_mults=args.stock_mults,
        time_limit_seconds=args.time_limit,
        write_detail_xlsx_top_n=max(0, int(args.demo_xlsx_count)),
    )
    print(f"Üst klasör: {res['reports_parent']}")
    print(f"Suite: {res['suite_root']}")
    print(f"Koşu sayısı: {res['total_runs']} · Çift başarılı grup: {res['dual_success_count']}")
    print(f"Demo Excel çifti: {res['demo_reports_written']}")
    print(f"Grafik PNG: {len(res.get('graf_paths') or [])}")


if __name__ == "__main__":
    main()
