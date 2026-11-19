"""Verify both staged architectures and promote only complete release indexes."""

import argparse
import json
import os
from pathlib import Path
import re

from release_platform import DIGEST, run
from release_tags import select_tags


def remote_sha(repository, tag, execute=run):
    obj = json.loads(execute("gh", "api", f"repos/{repository}/git/ref/tags/{tag}"))["object"]
    for _ in range(10):
        if obj["type"] == "commit" and re.fullmatch(r"[a-f0-9]{40,64}", obj["sha"]):
            return obj["sha"]
        if obj["type"] != "tag":
            break
        obj = json.loads(execute("gh", "api", f"repos/{repository}/git/tags/{obj['sha']}"))[
            "object"
        ]
    raise ValueError("Cannot resolve the existing remote tag")


def collect(release, receipts):
    platforms = {}
    for path in Path(receipts).rglob("platform-published.json"):
        value = json.loads(path.read_text())
        arch = value["arch"]
        if value["release"] != release or arch not in ("amd64", "arm64") or arch in platforms:
            raise ValueError("Mismatched, duplicate or unexpected platform receipt")
        if set(value["images"]) != {e["image"] for e in release["entries"]}:
            raise ValueError("Incomplete platform image set")
        for entry in release["entries"]:
            image = value["images"][entry["image"]]
            prefix = entry["repository"] + "@"
            if not image["reference"].startswith(prefix) or not DIGEST.fullmatch(
                image["reference"][len(prefix) :]
            ):
                raise ValueError("Invalid staged image reference")
            if image["checked"]["kind"] not in ("config", "manifest") or not DIGEST.fullmatch(
                image["checked"]["id"]
            ):
                raise ValueError("Invalid validated image identity")
            for field in ("config_id", "manifest_id"):
                if field in image["checked"] and not DIGEST.fullmatch(image["checked"][field]):
                    raise ValueError("Invalid selected platform identity")
        platforms[arch] = value["images"]
    if set(platforms) != {"amd64", "arm64"}:
        raise ValueError("Both successfully validated architectures are required")
    return platforms


def publish(release, receipts, repository, output, execute=run):
    Path(output).unlink(missing_ok=True)
    platforms = collect(release, receipts)
    if remote_sha(repository, release["ref"], execute) != release["sha"]:
        raise ValueError("Remote tag changed after CI/planning")
    tags = execute(
        "gh", "api", "--paginate", f"repos/{repository}/tags?per_page=100", "--jq", ".[].name"
    ).splitlines()
    current = select_tags(tags, release["ref"])[0]
    aliases = [alias for alias in release["aliases"] if alias in current["aliases"]]
    candidates = {}
    # Verify all candidate indexes before moving any public alias.
    for entry in release["entries"]:
        name = entry["image"]
        references = [platforms[arch][name]["reference"] for arch in ("amd64", "arm64")]
        for arch, reference in zip(("amd64", "arm64"), references):
            raw = json.loads(
                execute("docker", "buildx", "imagetools", "inspect", reference, "--raw")
            )
            checked = platforms[arch][name]["checked"]
            observed = (
                reference.rsplit("@", 1)[1]
                if checked["kind"] == "manifest"
                else raw.get("config", {}).get("digest")
            )
            if checked["kind"] not in ("config", "manifest") or observed != checked.get(
                "config_id", checked.get("manifest_id", checked["id"])
            ):
                raise ValueError("Staged digest no longer matches validated image")
        tag = f"{entry['repository']}:checked-{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}-{release['ref'][1:]}"
        execute("docker", "buildx", "imagetools", "create", "--tag", tag, *references)
        manifest = json.loads(
            execute(
                "docker", "buildx", "imagetools", "inspect", tag, "--format", "{{json .Manifest}}"
            )
        )
        found = {
            (m.get("platform", {}).get("architecture"), m.get("digest"))
            for m in manifest.get("manifests", [])
            if m.get("platform", {}).get("os") == "linux"
        }
        expected = {
            (arch, platforms[arch][name]["reference"].rsplit("@", 1)[1]) for arch in platforms
        }
        if (
            len(manifest.get("manifests", [])) != 2
            or found != expected
            or not DIGEST.fullmatch(manifest.get("digest", ""))
        ):
            raise ValueError(
                "Candidate index does not contain exactly the validated platform digests"
            )
        candidates[name] = {"repository": entry["repository"], "digest": manifest["digest"]}
    for image in candidates.values():
        args = ["docker", "buildx", "imagetools", "create"]
        for alias in aliases:
            args.extend(("--tag", f"{image['repository']}:{alias}"))
        execute(*args, f"{image['repository']}@{image['digest']}")
    Path(output).write_text(
        json.dumps({"release": release, "aliases": aliases, "images": candidates}, indent=2) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    publish(
        json.loads(os.environ["RELEASE"]),
        args.receipts,
        os.environ["GITHUB_REPOSITORY"],
        args.output,
    )


if __name__ == "__main__":
    main()
