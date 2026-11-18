"""Resolve public examples and verify profiles, runtime parity and secret boundaries."""

import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ((), ("clamav",), ("elasticsearch",), ("clamav", "elasticsearch"))


def resolve(files, profiles=(), env_file=".env.example"):
    # Personal .env values and exported application variables must not affect tests.
    environment = {
        key: value for key, value in os.environ.items() if key in ("PATH", "HOME", "TMPDIR")
    }
    environment["COMPOSE_PROFILES"] = ",".join(profiles)
    args = ["docker", "compose", "--project-name", "mw-config-test", "--env-file", env_file]
    for file in files:
        args.extend(("-f", file))
    result = subprocess.run(
        [*args, "config", "--format", "json"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        # Avoid printing resolved environment values, including example passwords.
        raise AssertionError(f"Compose configuration failed for {files}: {result.stderr}")
    return json.loads(result.stdout)


class ComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configurations = {
            (file, profiles): resolve([file], profiles)
            for file in ("compose.yml", "compose.dev.yml", "compose.setup.yml")
            for profiles in PROFILES
        }

    def test_profiles_select_services_and_keep_search_internal(self):
        core = {"mediawiki", "database", "memcached", "memcachephp", "opensearch"}
        for (file, profiles), config in self.configurations.items():
            with self.subTest(file=file, profiles=profiles):
                self.assertEqual(set(config["services"]), core | set(profiles))
                search = config["services"]["opensearch"]
                self.assertFalse(search.get("ports"), "OpenSearch must not expose host ports")
                self.assertTrue(config["networks"]["backend-nw"]["internal"])

    def test_production_development_runtime_parity(self):
        for profiles in PROFILES:
            with self.subTest(profiles=profiles):
                production = copy.deepcopy(self.configurations[("compose.yml", profiles)])
                development = copy.deepcopy(self.configurations[("compose.dev.yml", profiles)])
                volumes = development["services"]["mediawiki"]["volumes"]
                # The development variant intentionally mounts an existing local configuration.
                local = [
                    volume
                    for volume in volumes
                    if volume["target"] == "/var/www/html/LocalSettings.php"
                ]
                self.assertEqual(len(local), 1)
                self.assertEqual(local[0]["type"], "bind")
                self.assertTrue(local[0]["read_only"])
                development["services"]["mediawiki"]["volumes"] = [
                    volume for volume in volumes if volume not in local
                ]
                for config in (production, development):
                    for image in ("mediawiki", "memcachephp"):
                        config["services"][image].pop("build", None)
                        config["services"][image].pop("image", None)
                self.assertEqual(production, development)

    def test_setup_keeps_writable_configuration_and_uploads(self):
        config = self.configurations[("compose.setup.yml", ())]
        mounts = {mount["target"]: mount for mount in config["services"]["mediawiki"]["volumes"]}
        self.assertEqual(mounts["/var/www/html/conf"]["type"], "bind")
        self.assertFalse(mounts["/var/www/html/conf"].get("read_only", False))
        self.assertEqual(mounts["/var/www/html/images"]["type"], "volume")

    def test_ci_override_resolves_build_contexts_from_root_base(self):
        config = resolve(["compose.yml", "tests/compose.test.yml"], env_file=".env.ci-test")
        for service in ("mediawiki", "memcachephp"):
            self.assertEqual(
                Path(config["services"][service]["build"]["context"]), ROOT / "resources" / service
            )
            self.assertEqual(config["services"][service]["pull_policy"], "never")
        self.assertEqual(
            config["services"]["mediawiki"]["environment"]["MW_CONFIG_FILE"],
            "/var/www/html/conf/LocalSettings.php",
        )

    def test_secrets_overlay_removes_password_values_and_exposes_only_required_files(self):
        config = resolve(["compose.yml", "compose.secrets.yml"], env_file=".env.secrets")
        services = config["services"]
        for service, variables in {
            "mediawiki": ("MW_DB_PASS", "MW_WANDA_OPENAI_API_KEY"),
            "database": ("MARIADB_PASSWORD", "MARIADB_ROOT_PASSWORD"),
            "memcachephp": ("MEMCACHEPHP_ADMIN_PASS",),
        }.items():
            for variable in variables:
                self.assertNotIn(variable, services[service]["environment"])
        expected = {
            "mediawiki": {
                "mw_db_pass",
                "mariadb_root_password",
                "mw_admin_pass",
                "mw_wanda_openai_api_key",
            },
            "database": {"mariadb_root_password", "mw_db_pass"},
            "memcachephp": {"memcachephp_admin_pass"},
        }
        for service, secrets in expected.items():
            self.assertEqual({item["source"] for item in services[service]["secrets"]}, secrets)
        self.assertEqual(
            services["database"]["environment"]["MARIADB_PASSWORD_FILE"], "/run/secrets/mw_db_pass"
        )
        self.assertEqual(
            services["memcachephp"]["environment"]["MEMCACHEPHP_ADMIN_PASS_FILE"],
            "/run/secrets/memcachephp_admin_pass",
        )


if __name__ == "__main__":
    unittest.main()
