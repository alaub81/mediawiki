"""Check custom-manager coverage against the actual dependency declarations."""

from collections import Counter
import json
from pathlib import Path
import re
import unittest

import yaml

from change_plan import IMAGES, ci_plan

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "renovate.json").read_text())


def compile_regex(expression):
    """Use Python's named-group spelling for Renovate's RE2-compatible patterns."""
    return re.compile(re.sub(r"\(\?<([A-Za-z][A-Za-z0-9_]*)>", r"(?P<\1>", expression))


def extract(manager, content):
    matches = [({}, content)]
    for expression in manager["matchStrings"]:
        next_matches = []
        for previous, text in matches:
            for match in compile_regex(expression).finditer(text):
                next_matches.append((previous | match.groupdict(), match.group(0)))
        matches = next_matches
    return [captures for captures, _ in matches]


def manager_for(path):
    matches = [
        manager
        for manager in CONFIG["customManagers"]
        if any(re.search(pattern[1:-1], path) for pattern in manager["managerFilePatterns"])
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one custom manager for {path}, got {len(matches)}")
    return matches[0]


class DependencyConfigTests(unittest.TestCase):
    def test_native_assets_update_version_and_checksum_together(self):
        content = (ROOT / "lint-tools.json").read_text()
        manifest = json.loads(content)
        expected = Counter(
            (tool["repository"], asset["version"], asset["sha256"])
            for tool in manifest.values()
            for asset in tool["assets"].values()
        )
        extracted = Counter(
            (match["depName"], match["currentValue"], match["currentDigest"])
            for match in extract(manager_for("lint-tools.json"), content)
        )
        self.assertTrue(expected)
        self.assertEqual(extracted, expected)

    def test_supercronic_download_is_covered_for_both_target_architectures(self):
        path = "resources/mediawiki/Dockerfile"
        content = (ROOT / path).read_text()
        versions = re.findall(
            r"https://github\.com/aptible/supercronic/releases/download/([^/]+)/", content
        )
        manager = manager_for(path)
        self.assertEqual(manager["depNameTemplate"], "aptible/supercronic")
        self.assertTrue(versions)
        self.assertEqual([match["currentValue"] for match in extract(manager, content)], versions)
        self.assertIn("supercronic-linux-${TARGETARCH}", content)

    def test_public_environment_versions_match_compose_defaults(self):
        names = {
            "MARIADB_VERSION": "mariadb",
            "OPENSEARCH_VERSION": "docker-registry.wikimedia.org/repos/search-platform/cirrussearch-opensearch-image",
            "ELASTICSEARCH_VERSION": "docker.elastic.co/elasticsearch/elasticsearch",
        }
        for path in (".env.example", ".env.secrets"):
            content = (ROOT / path).read_text()
            manager = manager_for(path)
            expected = Counter()
            for variable, package in names.items():
                value = re.search(rf"^{variable}=(\S+)$", content, re.MULTILINE)[1]
                expected[(package, value)] += 1
                for compose in ("compose.yml", "compose.dev.yml", "compose.setup.yml"):
                    with self.subTest(template=path, variable=variable, compose=compose):
                        self.assertIn(f"${{{variable}:-{value}}}", (ROOT / compose).read_text())
            self.assertEqual(
                Counter((m["depName"], m["currentValue"]) for m in extract(manager, content)),
                expected,
            )

    def test_supercronic_update_requires_runtime_checks(self):
        plan = ci_plan(["resources/mediawiki/Dockerfile"])
        self.assertTrue(plan["runtime"])
        self.assertTrue(plan["tests"])
        self.assertEqual(plan["affected"], ["mediawiki"])
        self.assertEqual(plan["build"], list(IMAGES))

    def test_compatibility_ranges_reject_untested_versions(self):
        cases = {
            "ubuntu": (["24.04"], ["22.04", "26.04", "latest"]),
            "mediawiki": (["1.46", "1.46.99"], ["1.45", "1.47", "2.0.0"]),
            "docker-registry.wikimedia.org/repos/search-platform/cirrussearch-opensearch-image": (
                ["v1.3.20-12", "v1.3.99-123"],
                ["v2.0.0-1", "v1.4.0-1", "latest"],
            ),
            "docker.elastic.co/elasticsearch/elasticsearch": (
                ["8.19.21", "8.19.99"],
                ["8.20.0", "9.0.0", "latest"],
            ),
        }
        for package, (accepted, rejected) in cases.items():
            rule = next(
                rule
                for rule in CONFIG["packageRules"]
                if package in rule.get("matchPackageNames", []) and "allowedVersions" in rule
            )
            pattern = re.compile(rule["allowedVersions"][1:-1])
            for version in accepted:
                with self.subTest(package=package, version=version):
                    self.assertRegex(version, pattern)
            for version in rejected:
                with self.subTest(package=package, version=version):
                    self.assertNotRegex(version, pattern)

    def test_dependabot_security_ownership_does_not_create_regular_prs(self):
        config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text())
        self.assertFalse(CONFIG["vulnerabilityAlerts"]["enabled"])
        for ecosystem in config["updates"]:
            with self.subTest(ecosystem=ecosystem["package-ecosystem"]):
                self.assertEqual(ecosystem["open-pull-requests-limit"], 0)
                self.assertNotIn("target-branch", ecosystem)
                self.assertNotIn("ignore", ecosystem)
                self.assertNotIn("cooldown", ecosystem)
