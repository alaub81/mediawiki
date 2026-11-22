"""Resolve the actual E2E inputs and verify container-test isolation."""

from pathlib import Path
import unittest
import tempfile
import shutil
from unittest.mock import patch

from stack import ROOT, resolve


class StackTests(unittest.TestCase):
    def test_test_stack_uses_both_current_images_and_only_test_volumes(self):
        with patch.dict(
            "os.environ", TEST_ARCH="arm64", COMPOSE_FILE="compose.yml:compose.config.yml"
        ):
            config = resolve(18999)
        for service in ("mediawiki", "memcachephp"):
            self.assertEqual(config["services"][service]["image"], f"{service}-ci:arm64")
            self.assertEqual(config["services"][service]["platform"], "linux/arm64")
            self.assertEqual(config["services"][service]["build"]["platforms"], ["linux/arm64"])
            self.assertEqual(
                Path(config["services"][service]["build"]["context"]), ROOT / "resources" / service
            )
        wiki = config["services"]["mediawiki"]
        self.assertEqual(wiki["environment"]["MW_SERVER_URL"], "http://localhost:18999")
        self.assertTrue(all(mount["type"] == "volume" for mount in wiki["volumes"]))
        self.assertEqual(wiki["ports"][0]["host_ip"], "127.0.0.1")
        self.assertEqual(wiki["ports"][0]["published"], "18999")
        self.assertTrue(any(mount["target"] == "/var/www/html/conf" for mount in wiki["volumes"]))
        for network in config["networks"].values():
            self.assertFalse(network.get("driver_opts"))
        self.assertEqual(config["services"]["opensearch"]["platform"], "linux/amd64")

    def test_release_runtime_uses_selected_source_and_historical_compose_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            shutil.copyfile(ROOT / "compose.yml", source / "docker-compose.example.yml")
            with patch.dict("os.environ", TEST_ARCH="amd64"):
                config = resolve(18999, source)
            self.assertEqual(
                Path(config["services"]["mediawiki"]["build"]["context"]),
                source.resolve() / "resources/mediawiki",
            )
            self.assertEqual(config["services"]["mediawiki"]["image"], "mediawiki-ci:amd64")

    def test_unknown_platform_cannot_silently_use_host_architecture(self):
        with patch.dict("os.environ", TEST_ARCH="arm/v7"):
            with self.assertRaisesRegex(ValueError, "TEST_ARCH"):
                resolve()


if __name__ == "__main__":
    unittest.main()
