"""Record tested image identities and scan those exact local images without a rebuild."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from stack import ROOT


def inspect(reference, arch):
    result = subprocess.check_output(["docker", "image", "inspect", reference], text=True)
    image = json.loads(result)[0]
    if image["Os"] != "linux" or image["Architecture"] != arch:
        raise ValueError(f"Image {reference} has the wrong architecture")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image["Id"]):
        raise ValueError("Invalid local image ID")
    return image["Id"]


def validate_receipt(receipt, arch):
    references = {"mediawiki": f"mediawiki-ci:{arch}", "memcachephp": f"memcachephp-ci:{arch}"}
    if set(receipt) != set(references):
        raise ValueError("Incomplete tested-image receipt")
    for name, tag in references.items():
        if receipt[name]["tag"] != tag or inspect(tag, arch) != receipt[name]["id"]:
            raise ValueError("Image changed after its identity was recorded")
    return [f"{name}-{arch}={receipt[name]['id']}" for name in references]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("record", "scan"))
    parser.add_argument("--arch", required=True, choices=("amd64", "arm64"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--reports", type=Path)
    args = parser.parse_args()
    references = {
        "mediawiki": f"mediawiki-ci:{args.arch}",
        "memcachephp": f"memcachephp-ci:{args.arch}",
    }
    if args.operation == "record":
        receipt = {
            name: {"tag": tag, "id": inspect(tag, args.arch)} for name, tag in references.items()
        }
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
        patches = subprocess.check_output(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "sh",
                receipt["mediawiki"]["id"],
                "-c",
                "cat /usr/local/share/mediawiki-upstream-patches 2>/dev/null || true",
            ],
            text=True,
        )
        for patch in patches.splitlines():
            if re.fullmatch(r"[A-Za-z0-9_.-]+", patch):
                print(
                    f"::warning title=Redundant MediaWiki patch::{patch} is already included upstream; remove the manual patch."
                )
    else:
        if args.reports is None:
            raise ValueError("--reports is required when scanning")
        receipt = json.loads(args.receipt.read_text())
        images = validate_receipt(receipt, args.arch)
        subprocess.run(
            [
                "bash",
                str(ROOT / "tests/scan-images.sh"),
                str(args.reports),
                *images,
            ],
            cwd=ROOT,
            env=dict(
                os.environ, SCAN_CATEGORY=f"ci-{args.arch}", SCAN_PLATFORM=f"linux/{args.arch}"
            ),
            check=True,
        )


if __name__ == "__main__":
    main()
