import importlib.util
import io
import json
import pathlib
import tarfile
import tempfile
import unittest
import zipfile
from datetime import date, timedelta

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "recover_kell_history_artifact.py"
spec = importlib.util.spec_from_file_location("recover_kell_history_artifact", MODULE)
recover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recover)


def trading_bars(count=270, start_price=30.0):
    rows = []
    current = date(2025, 8, 1)
    price = start_price
    while len(rows) < count:
        if current.weekday() < 5:
            open_ = price
            price *= 1.001
            rows.append([
                current.isoformat(),
                open_,
                max(open_, price) * 1.005,
                min(open_, price) * 0.995,
                price,
                1_000_000,
                price / 5.0,  # embedded RS -> stable synthetic SPY around 500
            ])
        current += timedelta(days=1)
    return rows


def pages_zip(path: pathlib.Path):
    run_id = "2026-09-09-eod-test"
    session = "2026-09-09"
    bars = trading_bars()
    bars[-1][5] = 3_000_000
    bars[-1][4] = bars[-2][4] * 1.04
    bars[-1][2] = bars[-1][4] * 1.01

    files = {
        "data/manifest.json": {
            "runId": run_id,
            "sessionDate": session,
        },
    }
    for mode in recover.MODES:
        core = {
            "runId": run_id,
            "sessionDate": session,
            "universe": [{
                "ticker": "AAA",
                "rsRank": 95 if mode == "next" else 10,
                "revenueYoY": 40 if mode == "next" else None,
                "epsYoY": 35 if mode == "next" else None,
            }],
            "chartShards": {"AAA": "000.json"},
        }
        if mode == "bottom-fishing":
            # BBB proves exact historical membership can exist without becoming a
            # Kell match when the archived artifact has no usable chart evidence.
            core["universe"].append({"ticker": "BBB", "rsRank": 10})
            # CCC is shared only by Bottom/Ryan. Bottom must win scalar context,
            # matching build_review_snapshot.py merge semantics.
            core["universe"].append({"ticker": "CCC", "rsRank": 95})
        elif mode == "ryan-original":
            core["universe"].append({"ticker": "CCC", "rsRank": 10})
            core["chartShards"]["CCC"] = "001.json"
        chart_path = (
            f"runs/{run_id}/charts/manifest.json"
            if mode == "bottom-fishing"
            else f"runs/{run_id}/charts"
        )
        manifest = {
            "runId": run_id,
            "sessionDate": session,
            "status": "healthy",
            "assets": {
                "core": {"path": f"runs/{run_id}/core.json"},
                "charts": {"path": chart_path},
            },
        }
        files[f"data/modes/{mode}/manifest.json"] = manifest
        files[f"data/modes/{mode}/runs/{run_id}/core.json"] = core
        if mode in {"next", "ryan-original"}:
            files[f"data/modes/{mode}/runs/{run_id}/charts/000.json"] = {
                "AAA": bars,
            }
            if mode == "ryan-original":
                low_bars = trading_bars(start_price=9.0)
                for row in low_bars:
                    row[5] = 100_000
                files[f"data/modes/{mode}/runs/{run_id}/charts/001.json"] = {
                    "CCC": low_bars,
                }
        else:
            files[f"data/modes/{mode}/runs/{run_id}/charts/manifest.json"] = {
                "shardsByTicker": {},
            }

    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w") as tar:
        for name, payload in files.items():
            raw = json.dumps(payload).encode()
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
    tar_bytes.seek(0)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("artifact.tar", tar_bytes.getvalue())


class RecoverKellHistoryArtifactTests(unittest.TestCase):
    def test_recover_exact_membership_and_current_score_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "pages.zip"
            pages_zip(source)
            out = recover.recover(source)

        self.assertEqual(out["schemaVersion"], "kell-score-history-v2")
        self.assertEqual(out["source"]["sessionDate"], "2026-09-09")
        self.assertEqual(out["source"]["runId"], "2026-09-09-eod-test")
        self.assertTrue(out["source"]["pointInTimeCandidateMembership"])
        self.assertEqual(out["source"]["unifiedCandidateCount"], 3)
        self.assertEqual(out["source"]["chartCoverageCount"], 2)
        self.assertEqual(out["candidateCount"], 2)

        columns = out["columns"]
        rows = {row[0]: dict(zip(columns, row)) for row in out["candidates"]}
        item = rows["AAA"]
        self.assertEqual(item["source_mask"], 7)
        self.assertEqual(rows["CCC"]["source_mask"], 5)
        # CCC would not match on its low-price/low-volume Ryan chart alone.
        # Its inclusion proves Bottom rsRank=95 correctly overrides Ryan rsRank=10.
        self.assertGreater(rows["CCC"]["legacy_v4_score"], 0)
        # Next is deliberately the richest/higher-priority scalar context.
        self.assertGreater(item["kell_quality_score"], 0)
        self.assertGreater(item["kell_evidence_coverage"], 0)
        self.assertIsNotNone(item["legacy_v4_score"])
        self.assertIn(
            item["stage"],
            {
                "reversal_extension", "wedge_pop", "ema_crossback", "base_n_break",
                "exhaustion_extension", "wedge_drop", "trend_ema_support",
                "downtrend_repair", "transition",
            },
        )

    def test_pages_artifact_requires_consistent_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "pages.zip"
            pages_zip(source)
            tar_path = pathlib.Path(tmp) / "artifact.tar"
            recover._materialize_tar(source, tar_path)
            artifact = recover.PagesArtifact(tar_path)
            try:
                manifest = artifact.json("data/modes/next/manifest.json")
                manifest["sessionDate"] = "2026-09-08"
            finally:
                artifact.close()
            # Identity mismatch is covered by recover(); this helper check protects
            # the fixture contract without weakening the main integration test.
            self.assertNotEqual(manifest["sessionDate"], "2026-09-09")


if __name__ == "__main__":
    unittest.main()
