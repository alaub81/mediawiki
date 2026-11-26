"""Use real pinned Trivy conversion to verify full evidence and fixable severity gates."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScanTests(unittest.TestCase):
    def test_full_reports_are_kept_for_every_gate_outcome(self):
        trivy = shutil.which("trivy")
        self.assertIsNotNone(trivy, "Prepare pinned Trivy with tests/test-check.sh")
        fixture = {
            "SchemaVersion": 2,
            "ArtifactName": "fixture",
            "ArtifactType": "container_image",
            "Metadata": {"OS": {"Family": "debian", "Name": "13"}},
            "Results": [
                {
                    "Target": "fixture (debian 13)",
                    "Class": "os-pkgs",
                    "Type": "debian",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2099-99999",
                            "PkgName": "example",
                            "InstalledVersion": "1.0",
                            "Title": "Policy fixture",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bin_path = directory / "bin"
            bin_path.mkdir()
            wrapper = bin_path / "trivy"
            wrapper.write_text(
                f"#!{sys.executable}\n"
                "import os, pathlib, sys\n"
                "if sys.argv[1] == 'image':\n"
                "    output = sys.argv[sys.argv.index('--output') + 1]\n"
                "    pathlib.Path(output).write_bytes(pathlib.Path(os.environ['SCAN_FIXTURE']).read_bytes())\n"
                "else:\n"
                f"    os.execv({trivy!r}, [{trivy!r}, *sys.argv[1:]])\n"
            )
            wrapper.chmod(0o755)
            cases = [
                ("HIGH", "fixed", "1.1", 0),
                ("CRITICAL", "fixed", "1.1", 1),
                ("HIGH", "affected", "", 0),
                ("CRITICAL", "affected", "", 0),
                ("LOW", "fixed", "1.1", 0),
                ("MEDIUM", "fixed", "1.1", 0),
            ]
            for index, (severity, status, fixed, expected) in enumerate(cases):
                with self.subTest(severity=severity, status=status):
                    data = copy.deepcopy(fixture)
                    data["Results"][0]["Vulnerabilities"][0].update(
                        Severity=severity, Status=status, FixedVersion=fixed
                    )
                    source = directory / "source.json"
                    source.write_text(json.dumps(data))
                    reports = directory / str(index)
                    result = subprocess.run(
                        ["bash", "tests/scan-images.sh", str(reports), "fixture=unused:test"],
                        cwd=ROOT,
                        env=dict(
                            os.environ,
                            PATH=f"{bin_path}{os.pathsep}{os.environ['PATH']}",
                            SCAN_FIXTURE=str(source),
                        ),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if severity == "HIGH":
                        self.assertIn("CVE-2099-99999", result.stdout)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    self.assertEqual(
                        len(
                            json.loads((reports / "fixture.json").read_text())["Results"][0][
                                "Vulnerabilities"
                            ]
                        ),
                        1,
                    )
                    sarif = json.loads((reports / "fixture.sarif").read_text())
                    self.assertEqual(len(sarif["runs"][0]["results"]), 1)
                    self.assertEqual(
                        sarif["runs"][0]["automationDetails"]["id"], "fixture-default/"
                    )

    def test_scanner_failure_fails_instead_of_reporting_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            tool = directory / "trivy"
            tool.write_text("#!/bin/sh\nexit 2\n")
            tool.chmod(0o755)
            result = subprocess.run(
                [
                    "bash",
                    "tests/scan-images.sh",
                    str(directory / "reports"),
                    "first=unused:test",
                    "second=unused:test",
                ],
                cwd=ROOT,
                env=dict(os.environ, PATH=f"{directory}{os.pathsep}{os.environ['PATH']}"),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((directory / "reports/first.sarif").exists())


if __name__ == "__main__":
    unittest.main()
