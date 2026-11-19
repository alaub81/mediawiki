"""Run the preserved MediaWiki E2E suite against a disposable complete stack."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import uuid

from stack import ROOT, resolve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--reports", type=Path, default=ROOT / ".test-reports/e2e")
    args = parser.parse_args()
    args.reports = args.reports.resolve()
    args.reports.mkdir(parents=True, exist_ok=True)
    for tool in ("docker", "curl", "jq"):
        if not shutil.which(tool):
            raise ValueError(f"Missing E2E prerequisite: {tool}")
    subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    project = f"mw-e2e-{uuid.uuid4().hex[:10]}"
    with tempfile.TemporaryDirectory(prefix="mediawiki-e2e-") as temporary:
        directory = Path(temporary)
        config = resolve(port)
        config.pop("name", None)
        # Resolved Compose output contains explicit resource names from planning.
        # Remove them so the random runtime project owns every disposable resource.
        for kind in ("volumes", "networks"):
            for resource in config.get(kind, {}).values():
                resource.pop("name", None)
        compose = directory / "compose.json"
        compose.write_text(json.dumps(config))
        fixture = (ROOT / "tests/e2e.env").read_text()
        fixture += f"\nMW_HTTP_PORT={port}\nMW_SERVER_URL=http://localhost:{port}\n"
        (directory / ".env.ci").write_text(fixture)
        environment = {
            key: value for key, value in os.environ.items() if key in ("PATH", "HOME", "TMPDIR")
        }
        environment.update(
            COMPOSE_FILE=str(compose),
            COMPOSE_PROJECT_NAME=project,
            COMPOSE_PROFILES="clamav,elasticsearch",
            TMPDIR=str(directory),
        )
        command = ["docker", "compose"]

        def run(*argv, **kwargs):
            return subprocess.run(argv, cwd=directory, env=environment, check=True, **kwargs)

        try:
            if not args.skip_build:
                run(*command, "build", "--pull")
            # Set the owner of the test-only configuration volume before running the installer.
            run(
                *command,
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "sh",
                "--user",
                "root",
                "mediawiki",
                "-c",
                "chown www-data:www-data /var/www/html/conf",
            )
            run(*command, "up", "-d", "--no-build")
            for step in sorted((ROOT / "tests/e2e").glob("*.sh")):
                print(f"==> {step.stem}", flush=True)
                run("bash", str(step))
            memcachephp = config["services"]["memcachephp"]["image"]
            run("bash", str(ROOT / "tests/integration-check.sh"), "--image", memcachephp)
        finally:
            for name, arguments in (
                ("services.txt", ["ps", "--all"]),
                ("compose.log", ["logs", "--no-color", "--tail", "200"]),
            ):
                with (args.reports / name).open("w") as output:
                    subprocess.run(
                        [*command, *arguments],
                        cwd=directory,
                        env=environment,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
            run(*command, "down", "--volumes", "--remove-orphans", "--timeout", "20")
    print("MediaWiki E2E and MemcachePHP security checks passed", flush=True)


if __name__ == "__main__":
    main()
