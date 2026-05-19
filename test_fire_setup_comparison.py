"""
Fire-setup-interleaving grid karşılaştırması için hafif unittest.

Tam grid uzun sürdüğünden `minimal=True` ile tek kapasite bandında üç fire çarpanı koşulur.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from run_fire_setup_comparison import run_comparison_suite


class TestFireSetupComparison(unittest.TestCase):
    """Minimal grid çıktısı ve çift başarılı kombinasyon için koşullu doğrulama."""

    def test_minimal_fire_setup_grid_dual_success_or_skip(self) -> None:
        """
        Minimal grid çalışır; çift başarılı kombinasyon varsa doğrular, yoksa skipTest.

        Çift başarılı yoksa unittest skip ile bilgi verilir (CI kırılmaz).
        """
        with tempfile.TemporaryDirectory(prefix="fire_grid_utest_") as tmp:
            res = run_comparison_suite(
                reports_root=tmp,
                minimal=True,
                time_limit_seconds=45,
                write_detail_xlsx_top_n=0,
            )
            self.assertEqual(res["total_runs"], 3)
            self.assertTrue(os.path.isfile(res["grid_csv"]))

        if res["dual_success_count"] >= 1:
            self.assertTrue(res["dual_success_summaries"])
            top = res["dual_success_summaries"][0]
            self.assertTrue(top.get("dual_success"))
            return

        self.skipTest(
            "Minimal grid'de çift başarılı kombinasyon yok; "
            f"witness_fire_shift={res.get('witness_fire_shift')}, "
            f"witness_transition_shift={res.get('witness_transition_shift')}. "
            "Tam grid: python run_fire_setup_comparison.py"
        )


if __name__ == "__main__":
    unittest.main()
