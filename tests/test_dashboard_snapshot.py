import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[1] / "tools/build_dashboard_snapshot.py"
SPEC = importlib.util.spec_from_file_location("dashboard_snapshot", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class DashboardSnapshotTest(unittest.TestCase):
    def test_dashboard_does_not_claim_phone_delivery_from_provider_acceptance(self):
        app = (Path(__file__).parents[1] / "dashboard/app.js").read_text(encoding="utf-8")
        self.assertIn("平台已接收", app)
        self.assertIn("不等于手机送达", app)
        self.assertNotIn("24h 已推送", app)

    def test_snapshot_reconciles_render_qc_push_and_sla(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/reel_publish_ledger").mkdir(parents=True)
            (root / "data/reel-dispatch-queue").mkdir(parents=True)
            (root / "specs/reel").mkdir(parents=True)
            (root / "output/2026-08-26/reel/demo").mkdir(parents=True)
            (root / "data/orchestration_state.json").write_text('{"dispatched":{"demo":{}},"last_dispatch_at":"2026-08-26T00:00:00Z"}')
            (root / "specs/reel/demo.json").write_text('{}')
            (root / "output/2026-08-26/reel/demo/render.json").write_text(json.dumps({"qc_attestation_sha256":"abc","production_sla":{"slug":"demo","met":True,"elapsed_seconds":120,"artifact_ready_at":"2026-08-26T01:02:00Z"}}))
            accepted_at = module.datetime.now(module.timezone.utc).isoformat().replace("+00:00", "Z")
            (root / "data/reel_publish_ledger/demo.json").write_text(json.dumps({"slug":"demo","attempts":[{"status":"sent","at":accepted_at,"run":"https://github.com/run/1"}]}))
            with patch.object(module, "github_runs", return_value=[]):
                data = module.build(root, None)
            item = data["content"][0]
            self.assertTrue(all(item[k] for k in ("discovered", "orchestrated", "spec", "rendered", "qc", "pushed")))
            self.assertEqual(item["platform_status"], "accepted")
            self.assertEqual(item["delivery_status"], "unverified")
            self.assertEqual(data["summary"]["accepted_24h"], 1)
            self.assertNotIn("published_24h", data["summary"])
            self.assertEqual(data["summary"]["sla_rate"], 100)

    def test_failed_workflow_drives_red_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/reel-dispatch-queue").mkdir(parents=True)
            (root / "data/orchestration_state.json").write_text('{"dispatched":{}}')
            now = module.datetime.now(module.timezone.utc).isoformat()
            runs = [{"name":"orchestrate","status":"completed","conclusion":"failure","created_at":now,"updated_at":now,"html_url":"https://github.com/run/2"}]
            with patch.object(module, "github_runs", return_value=runs):
                data = module.build(root, None)
            self.assertEqual(data["health"]["status"], "failed")
            self.assertEqual(data["stages"][1]["status"], "failure")

if __name__ == "__main__":
    unittest.main()
