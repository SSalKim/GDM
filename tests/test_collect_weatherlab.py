import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from scripts import collect_weatherlab as collector


def body(aid="FNV3", cycle="2026090412", lead=6):
    return (
        "# Original source notice\n# BEGIN DATA\n"
        f"WP, 22, {cycle}, 03, {aid}, 0, 250N, 1300E, 40, 990, XX, 34, NEQ,\n"
        f"WP, 22, {cycle}, 03, {aid}, {lead}, 260N, 1310E, 45, 985, XX, 34, NEQ,\n"
    ).encode()


def response(content=b"", status=200):
    result = Mock(status_code=status, content=content)
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(str(status))
    return result


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.model = collector.MODELS[1]
        self.cycle = collector.parse_cycle("2026090412")

    def collect(self, *responses, model=None):
        session = Mock()
        session.get.side_effect = responses
        result = collector.collect_cycle(model or self.model, self.cycle, self.root, session)
        return result, session

    def test_three_independent_model_codes(self):
        self.assertEqual(["GENC", "FNV3", "WNV3"], [m.aid for m in collector.MODELS])
        for model in collector.MODELS:
            result, _ = self.collect(response(body(model.aid)), model=model)
            self.assertEqual(model.aid, result["model"])
            self.assertIn(f"forecast_files/2026/09/04/{model.aid}_", result["path"])
        self.assertEqual(3, len(list((self.root / "forecast_files").rglob("*.txt"))))

    def test_p2_url_but_original_fnv3_aid_and_nested_date_path(self):
        result, session = self.collect(response(body()))
        self.assertEqual("FNV3P2", result["upstream_model"])
        self.assertIn("/FNV3P2/", session.get.call_args.args[0])
        self.assertEqual("forecast_files/2026/09/04/FNV3_2026_09_04T12_00_atcf_a_deck.txt", result["path"])
        self.assertEqual(body(), (self.root / result["path"]).read_bytes())
        old = self.root / "forecast_files/2026_09_04/FNV3_2026_09_04T12_00_atcf_a_deck.txt"
        self.assertFalse(old.exists())

    def test_legacy_archive_migration_preserves_content_and_is_idempotent(self):
        old = self.root / "forecast_files/2025_12_31/GENC_2025_12_31T18_00_atcf_a_deck.txt"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"# Original header\r\noriginal archive\r\n")
        new = self.root / "forecast_files/2025/12/31" / old.name
        self.assertEqual(1, collector.migrate_legacy_paths(self.root))
        self.assertEqual(b"# Original header\r\noriginal archive\r\n", new.read_bytes())
        self.assertFalse(old.parent.exists())
        self.assertEqual(0, collector.migrate_legacy_paths(self.root))

    def test_migration_conflict_changes_neither_file(self):
        old = self.root / "forecast_files/2026_09_04/GENC.txt"
        new = self.root / "forecast_files/2026/09/04/GENC.txt"
        old.parent.mkdir(parents=True)
        new.parent.mkdir(parents=True)
        old.write_bytes(b"old data")
        new.write_bytes(b"new data")
        with self.assertRaises(ValueError):
            collector.migrate_legacy_paths(self.root)
        self.assertEqual(b"old data", old.read_bytes())
        self.assertEqual(b"new data", new.read_bytes())

    def test_old_version_is_fallback_only_when_p2_missing(self):
        result, session = self.collect(response(status=404), response(body()))
        self.assertEqual(2, session.get.call_count)
        self.assertEqual("FNV3", result["upstream_model"])

    def test_upgrade_and_no_checkpoint_downgrade(self):
        self.collect(response(status=404), response(body()))
        upgraded, _ = self.collect(response(body(lead=12)))
        self.assertEqual("FNV3P2", upgraded["upstream_model"])
        unavailable, session = self.collect(response(status=404))
        self.assertEqual("not_ready", unavailable["status"])
        self.assertEqual(1, session.get.call_count)
        self.assertEqual(body(lead=12), (self.root / upgraded["path"]).read_bytes())

    def test_identical_responses_do_not_rewrite_files_or_latest(self):
        first, _ = self.collect(response(body()))
        collector.update_latest(self.root, [first])
        mtimes = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        second, _ = self.collect(response(body()))
        collector.update_latest(self.root, [second])
        self.assertEqual("unchanged", second["status"])
        self.assertEqual(mtimes, {p: p.stat().st_mtime_ns for p in mtimes})

    def test_missing_source_does_not_create_empty_files(self):
        result, _ = self.collect(response(status=404), response(status=410))
        self.assertEqual("not_ready", result["status"])
        self.assertEqual([], list(self.root.rglob("*.txt")))

    def test_invalid_content_never_overwrites_known_good_data(self):
        first, _ = self.collect(response(body()))
        for invalid in [b"", b"<html>login</html>", b"# BEGIN DATA\n",
                        body("WNV3"), body(cycle="2026090406"),
                        body().replace(b"250N", b"999N"),
                        body() + b"WP, truncated\n"]:
            with self.subTest(invalid=invalid[:30]), self.assertRaises(ValueError):
                self.collect(response(invalid))
            self.assertEqual(body(), (self.root / first["path"]).read_bytes())

    def test_transport_failure_does_not_downgrade(self):
        first, _ = self.collect(response(body()))
        with self.assertRaises(requests.HTTPError):
            self.collect(response(status=503))
        self.assertEqual(body(), (self.root / first["path"]).read_bytes())

    def test_southern_and_western_hemisphere_are_valid_archive_data(self):
        candidate = body().replace(b"250N", b"250S").replace(b"1300E", b"1300W")
        self.assertEqual(2, collector.validate_atcf(candidate, self.model, self.cycle)["row_count"])

    def test_latest_never_moves_back_or_drops_another_model(self):
        initial = {"status": "updated", "model": "FNV3", "cycle_utc": "2026090412"}
        other = {"status": "updated", "model": "WNV3", "cycle_utc": "2026090406"}
        collector.update_latest(self.root, [initial, other])
        collector.update_latest(self.root, [
            dict(initial, cycle_utc="2026090318"),
            dict(other, status="not_ready"),
        ])
        self.assertEqual(
            {"FNV3": {"model": "FNV3", "cycle_utc": "2026090412"},
             "WNV3": {"model": "WNV3", "cycle_utc": "2026090406"}},
            collector.read_json(self.root / "data/latest.json"),
        )

    def test_atomic_replacement_failure_preserves_old_file(self):
        path = self.root / "forecast.txt"
        collector.write_if_changed(path, b"original")
        with patch.object(collector.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                collector.write_if_changed(path, b"replacement")
        self.assertEqual(b"original", path.read_bytes())
        self.assertEqual([path], list(self.root.iterdir()))

    def test_recent_cycles_are_newest_first_and_include_earlier_runs(self):
        now = datetime(2026, 9, 5, 1, 15, tzinfo=timezone.utc)
        cycles = collector.cycles_to_check(now)
        self.assertEqual(9, len(cycles))
        self.assertEqual("2026090500", cycles[0].strftime("%Y%m%d%H"))
        self.assertEqual("2026090300", cycles[-1].strftime("%Y%m%d%H"))
        self.assertTrue(all(cycle <= now for cycle in cycles))

    def test_backfill_validation_and_inclusive_range(self):
        now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.assertEqual(3, len(collector.cycles_to_check(now, start="2026090400", end="2026090412")))
        for start, end in [("2026090400", ""), ("bad", "2026090412"),
                           ("2026090401", "2026090412"), ("2026090412", "2026090400"),
                           ("2026090400", "2026090600"), ("2026070100", "2026090100")]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                collector.cycles_to_check(now, start=start, end=end)

    def test_partial_error_still_checks_and_preserves_other_models(self):
        def collect(job, root):
            model, cycle = job
            return {"status": "error" if model.aid == "GENC" else "updated",
                    "model": model.aid, "cycle_utc": cycle.strftime("%Y%m%d%H")}
        with patch.object(collector, "collect_safely", side_effect=collect) as fetch:
            code = collector.main(["--root", str(self.root), "--start", "2026090400", "--end", "2026090412"])
        self.assertEqual(1, code)
        self.assertEqual(9, fetch.call_count)
        self.assertEqual({"FNV3", "WNV3"}, set(collector.read_json(self.root / "data/latest.json")))


if __name__ == "__main__":
    unittest.main()
