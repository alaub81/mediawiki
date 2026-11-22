"""Resolve public examples and verify profiles, runtime parity and secret boundaries."""

import copy
import json
import os
from pathlib import Path
import subprocess
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ((), ("clamav",), ("elasticsearch",), ("clamav", "elasticsearch"))
STACKS = {
    "production": ("compose.yml", "compose.config.yml"),
    "development": ("compose.yml", "compose.config.yml", "compose.dev.yml"),
    "setup": ("compose.setup.yml",),
}


def resolve(
    files=(), profiles=(), env_file=".env.example", directory=ROOT, project="mw-config-test"
):
    # Personal .env values and exported application variables must not affect tests.
    environment = {
        key: value for key, value in os.environ.items() if key in ("PATH", "HOME", "TMPDIR")
    }
    environment["COMPOSE_PROFILES"] = ",".join(profiles)
    args = ["docker", "compose"]
    if project:
        args.extend(("--project-name", project))
    if env_file:
        args.extend(("--env-file", str(env_file)))
    for file in files:
        args.extend(("-f", file))
    result = subprocess.run(
        [*args, "config", "--format", "json"],
        cwd=directory,
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
            (variant, profiles): resolve(files, profiles)
            for variant, files in STACKS.items()
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
                production = copy.deepcopy(self.configurations[("production", profiles)])
                development = copy.deepcopy(self.configurations[("development", profiles)])
                volumes = development["services"]["mediawiki"]["volumes"]
                # Both normal-operation modes mount the same existing read-only settings.
                local = [
                    volume
                    for volume in volumes
                    if volume["target"] == "/var/www/html/LocalSettings.php"
                ]
                self.assertEqual(len(local), 1)
                self.assertEqual(local[0]["type"], "bind")
                self.assertTrue(local[0]["read_only"])
                for config in (production, development):
                    for image in ("mediawiki", "memcachephp"):
                        config["services"][image].pop("build", None)
                        config["services"][image].pop("image", None)
                self.assertEqual(production, development)

    def test_setup_keeps_writable_configuration_and_uploads(self):
        config = self.configurations[("setup", ())]
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
        config = resolve(env_file=".env.secrets")
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

    def test_environment_selection_matches_explicit_files(self):
        implicit = resolve()
        self.assertEqual(implicit, self.configurations[("production", ())])
        self.assertNotIn("build", implicit["services"]["mediawiki"])
        self.assertNotIn("build", implicit["services"]["memcachephp"])

    def test_default_env_discovery_switches_builds_and_keeps_project_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("compose.yml", "compose.config.yml", "compose.dev.yml"):
                shutil.copyfile(ROOT / name, directory / name)
            template = (ROOT / ".env.example").read_text()
            results = {}
            for variant in ("production", "development"):
                selection = ":".join(STACKS[variant])
                content = re.sub(
                    r"^COMPOSE_FILE=.*$", f"COMPOSE_FILE={selection}", template, flags=re.MULTILINE
                )
                (directory / ".env").write_text(content + "\nCOMPOSE_PROJECT_NAME=existing-wiki\n")
                config = resolve(env_file=None, directory=directory, project=None)
                self.assertEqual(config["name"], "existing-wiki")
                self.assertEqual(config["volumes"]["data_db"]["name"], "existing-wiki_data_db")
                self.assertEqual(
                    config["volumes"]["data_mw_images"]["name"], "existing-wiki_data_mw_images"
                )
                self.assertEqual(len(config["services"]["mediawiki"]["ports"]), 1)
                results[variant] = config
            for service in ("mediawiki", "memcachephp"):
                self.assertNotIn("build", results["production"]["services"][service])
                self.assertIn("build", results["development"]["services"][service])
                self.assertEqual(
                    Path(results["development"]["services"][service]["build"]["context"]),
                    directory.resolve() / "resources" / service,
                )

    def test_explicit_files_override_environment_selection_for_setup_and_ci(self):
        self.assertEqual(resolve(STACKS["setup"]), self.configurations[("setup", ())])
        with tempfile.TemporaryDirectory() as temporary:
            template = Path(temporary) / "ci.env"
            template.write_text(
                (ROOT / ".env.example").read_text() + "\nMW_CI_ENV_FILE=.env.ci-test\n"
            )
            ci = resolve(("compose.yml", "tests/compose.test.yml"), env_file=template)
        self.assertFalse(
            any(mount["type"] == "bind" for mount in ci["services"]["mediawiki"]["volumes"])
        )

    def test_local_overlay_loads_last_and_secrets_work_with_dev_profiles(self):
        for profiles in PROFILES:
            with self.subTest(profiles=profiles):
                config = resolve(
                    (*STACKS["development"], "compose.secrets.yml"), profiles, ".env.secrets"
                )
                self.assertIn("build", config["services"]["mediawiki"])
                self.assertNotIn("MW_DB_PASS", config["services"]["mediawiki"]["environment"])
                self.assertEqual(
                    config["services"]["mediawiki"]["secrets"][0]["source"], "mw_db_pass"
                )
        with tempfile.TemporaryDirectory() as temporary:
            overlay = Path(temporary) / "compose.local.yml"
            overlay.write_text(
                'services:\n  mediawiki:\n    environment:\n      MW_SITENAME: "Local wiki"\n'
            )
            config = resolve((*STACKS["development"], str(overlay)))
            self.assertEqual(
                config["services"]["mediawiki"]["environment"]["MW_SITENAME"], "Local wiki"
            )
            self.assertIn("build", config["services"]["mediawiki"])


if __name__ == "__main__":
    unittest.main()
