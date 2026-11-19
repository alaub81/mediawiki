"""Exercise CI report detection outside the workspace, including failed scan gates."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class SarifUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
        steps = workflow["jobs"]["stack"]["steps"]
        cls.detect = next(step for step in steps if step.get("id") == "sarif")
        cls.upload = next(step for step in steps if "upload-sarif@" in step.get("uses", ""))

    def detect_reports(self, directory, output):
        environment = os.environ | {
            "SARIF_DIRECTORY": str(directory),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_WORKSPACE": str(ROOT),
        }
        subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", self.detect["run"]],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return dict(line.split("=", 1) for line in output.read_text().splitlines())

    def test_detects_external_reports_after_failed_gate_for_each_architecture(self):
        for arch in ("amd64", "arm64"):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                reports = directory / "reports with spaces"
                reports.mkdir()
                report = reports / f"mediawiki-{arch}.sarif"
                # A failed gate must not hide the full report already written by the scanner.
                scan = subprocess.run(
                    [
                        "bash",
                        "-c",
                        'printf \'%s\\n\' \'{"version":"2.1.0","runs":[]}\' > "$1"; exit 1',
                        "fixture",
                        str(report),
                    ],
                    check=False,
                )
                self.assertEqual(scan.returncode, 1)
                self.assertEqual(
                    self.detect_reports(reports, directory / "output"), {"available": "true"}
                )
                self.assertEqual(json.loads(report.read_text())["version"], "2.1.0")

    def test_missing_or_empty_directory_and_json_only_do_not_request_upload(self):
        for state in ("missing", "empty", "json-only"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                reports = directory / "trivy"
                if state != "missing":
                    reports.mkdir()
                if state == "json-only":
                    (reports / "mediawiki.json").write_text("{}")
                self.assertEqual(
                    self.detect_reports(reports, directory / "output"), {"available": "false"}
                )

    def test_upload_remains_independent_of_previous_step_success(self):
        self.assertEqual(self.detect["if"], "always()")
        condition = self.upload["if"]
        self.assertIn("always()", condition)
        self.assertIn("steps.sarif.outputs.available == 'true'", condition)
        self.assertNotIn("hashFiles", condition)
        self.assertIn("github.event_name == 'push'", condition)
        self.assertIn("github.event.repository.private == false", condition)
        self.assertEqual(self.detect["env"]["SARIF_DIRECTORY"], self.upload["with"]["sarif_file"])
