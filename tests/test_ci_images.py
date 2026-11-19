"""Reject wrong-platform, incomplete and retagged images before vulnerability scans."""

import json
import unittest
from unittest.mock import patch

from ci_images import inspect, validate_receipt


class ImageReceiptTests(unittest.TestCase):
    def setUp(self):
        self.digest = "sha256:" + "a" * 64
        self.receipt = {
            name: {"tag": f"{name}-ci:arm64", "id": self.digest}
            for name in ("mediawiki", "memcachephp")
        }

    def test_only_recorded_ids_are_passed_to_scanner(self):
        with patch("ci_images.inspect", return_value=self.digest):
            self.assertEqual(
                validate_receipt(self.receipt, "arm64"),
                [f"mediawiki-arm64={self.digest}", f"memcachephp-arm64={self.digest}"],
            )

    def test_changed_tag_and_incomplete_receipt_fail(self):
        with patch("ci_images.inspect", return_value="sha256:" + "b" * 64):
            with self.assertRaisesRegex(ValueError, "changed"):
                validate_receipt(self.receipt, "arm64")
        self.receipt.pop("memcachephp")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            validate_receipt(self.receipt, "arm64")

    def test_wrong_architecture_is_not_scanned_as_a_supported_platform(self):
        output = json.dumps([{"Id": self.digest, "Os": "linux", "Architecture": "amd64"}])
        with patch("ci_images.subprocess.check_output", return_value=output):
            with self.assertRaisesRegex(ValueError, "architecture"):
                inspect("mediawiki-ci:arm64", "arm64")


if __name__ == "__main__":
    unittest.main()
