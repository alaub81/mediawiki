"""Resolve an isolated test stack from public fixtures and current source contexts."""

import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def resolve(port=8080, source_root=ROOT):
    source_root = Path(source_root).resolve()
    base = source_root / "compose.yml"
    if not base.is_file():
        base = source_root / "docker-compose.example.yml"
    environment = {
        key: value for key, value in os.environ.items() if key in ("PATH", "HOME", "TMPDIR")
    }
    arch = os.environ.get("TEST_ARCH", "")
    if arch not in ("", "amd64", "arm64"):
        raise ValueError("TEST_ARCH must be amd64 or arm64")
    suffix = arch or "local"
    environment.update(
        MW_CI_ENV_FILE=str(ROOT / "tests/e2e.env"),
        MW_TEST_IMAGE=f"mediawiki-ci:{suffix}",
        MEMCACHEPHP_TEST_IMAGE=f"memcachephp-ci:{suffix}",
        MW_HTTP_PORT=str(port),
        MW_SERVER_URL=f"http://localhost:{port}",
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            "mw-test",
            "--env-file",
            "tests/e2e.env",
            "-f",
            str(base),
            "-f",
            str(ROOT / "tests/compose.test.yml"),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    config = json.loads(result.stdout)
    for service in config["services"].values():
        service["restart"] = "no"
    if arch:
        for name in ("mediawiki", "memcachephp"):
            config["services"][name]["platform"] = f"linux/{arch}"
            config["services"][name]["build"]["platforms"] = [f"linux/{arch}"]
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-file", required=True, type=Path)
    args = parser.parse_args()
    config = resolve()
    args.build_file.write_text(json.dumps(config, indent=2) + "\n")


if __name__ == "__main__":
    main()
