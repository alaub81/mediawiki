"""Build/reuse, test and scan one native release platform before staging immutable digests."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

from release_plan import build_paths

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def local_tag(image, arch):
    return f"{image}-ci:{arch}"


def exported_config(tag, arch, execute=run):
    # Docker 29 can retain an index descriptor even with --platform inspection.
    # Export only that platform and read its config; do not unpack image layers.
    with tempfile.TemporaryDirectory(prefix="release-identity-") as temporary:
        archive = Path(temporary) / "image.tar"
        execute(
            "docker", "image", "save", "--platform", f"linux/{arch}", "--output", str(archive), tag
        )
        with tarfile.open(archive) as bundle:
            manifests = json.load(bundle.extractfile("manifest.json"))
            if len(manifests) != 1:
                raise ValueError("Expected exactly one exported platform")
            data = bundle.extractfile(manifests[0]["Config"]).read()
        digest = hashlib.sha256(data).hexdigest()
        if Path(manifests[0]["Config"]).name.removesuffix(".json") != digest:
            raise ValueError("Exported config checksum mismatch")
        config = json.loads(data)
        if config.get("os") != "linux" or config.get("architecture") != arch:
            raise ValueError("Exported config has the wrong platform")
        return "sha256:" + digest


def identity(tag, arch, execute=run, known=None):
    image = json.loads(execute("docker", "image", "inspect", tag))[0]
    root_id = image["Id"]
    descriptor = image.get("Descriptor")
    if descriptor:
        image = json.loads(
            execute("docker", "image", "inspect", "--platform", f"linux/{arch}", tag)
        )[0]
        descriptor = image.get("Descriptor", {})
    if image["Os"] != "linux" or image["Architecture"] != arch or not DIGEST.fullmatch(root_id):
        raise ValueError("Invalid image architecture/identity")
    media_type = descriptor.get("mediaType", "") if descriptor else ""
    if media_type.endswith(("image.index.v1+json", "manifest.list.v2+json")):
        if known and known["id"] == root_id and DIGEST.fullmatch(known.get("config_id", "")):
            return known
        config_id = exported_config(tag, arch, execute)
        after = json.loads(execute("docker", "image", "inspect", tag))[0]
        if after["Id"] != root_id:
            raise ValueError("Image changed during config export")
        return {"id": root_id, "kind": "config", "config_id": config_id}
    if descriptor:
        if not media_type.endswith(("manifest.v1+json", "manifest.v2+json")):
            raise ValueError("Expected a single-platform manifest")
        checked = {"id": root_id, "kind": "manifest"}
        if root_id != image["Id"]:
            if not DIGEST.fullmatch(image["Id"]):
                raise ValueError("Invalid selected platform manifest")
            checked["manifest_id"] = image["Id"]
        return checked
    return {"id": root_id, "kind": "config"}


def prepare(release, arch, source, reports, execute=run):
    for name in ("validated.json", "platform-published.json"):
        (reports / name).unlink(missing_ok=True)
    targets = {}
    for entry in release["entries"]:
        image = entry["image"]
        if entry["mode"] == "reuse":
            execute("docker", "pull", "--platform", f"linux/{arch}", entry["source"])
            execute("docker", "tag", entry["source"], local_tag(image, arch))
            selected = json.loads(execute("docker", "image", "inspect", local_tag(image, arch)))[0]
            if selected["Os"] != "linux" or selected["Architecture"] != arch:
                raise ValueError("Wrong reused-image architecture")
        else:
            context, dockerfile = build_paths(source, image)
            targets[image] = {
                "context": str(Path(context).resolve()),
                "dockerfile": str(Path(dockerfile).resolve()),
                "tags": [local_tag(image, arch)],
                "platforms": [f"linux/{arch}"],
                "cache-from": [f"type=gha,scope=release-{image}-{arch}"],
                "cache-to": [f"type=gha,mode=max,scope=release-{image}-{arch}"],
                "pull": True,
                "no-cache": bool(entry["refresh"]),
                "labels": {
                    "org.opencontainers.image.revision": release["sha"],
                    "org.opencontainers.image.version": release["ref"],
                    "org.opencontainers.image.source": f"https://github.com/{os.environ['GITHUB_REPOSITORY']}",
                },
            }
    (reports / "build.json").write_text(
        json.dumps({"group": {"default": {"targets": list(targets)}}, "target": targets})
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"has_builds={str(bool(targets)).lower()}\n")


def validate(release, arch, source, reports, execute=run):
    receipt = reports / "validated.json"
    receipt.unlink(missing_ok=True)
    checked = {
        entry["image"]: identity(local_tag(entry["image"], arch), arch, execute)
        for entry in release["entries"]
    }
    environment = dict(os.environ, TEST_ARCH=arch, SCAN_CATEGORY=f"release-{release['ref']}-{arch}")
    errors = []
    commands = [
        (
            "bash",
            str(ROOT / "tests/e2e-check.sh"),
            "--skip-build",
            "--source-root",
            str(source.resolve()),
            "--reports",
            str(reports / "e2e"),
        ),
        (
            "bash",
            str(ROOT / "tests/scan-images.sh"),
            str(reports / "trivy"),
            *[f"{image}-{arch}={value['id']}" for image, value in checked.items()],
        ),
    ]
    for index, command in enumerate(commands):
        print(
            f"Validating {release['ref']} / {arch}: {'E2E' if index == 0 else 'Trivy'}", flush=True
        )
        try:
            log = execute(*command, cwd=ROOT, env=dict(environment, SCAN_PLATFORM=f"linux/{arch}"))
        except (OSError, subprocess.CalledProcessError) as error:
            log = str(getattr(error, "output", "") or error)
            errors.append(str(error))
        (reports / f"validation-{index}.log").write_text(log + "\n")
        print(log, flush=True)
    if errors:
        raise ValueError("Release validation failed: " + "; ".join(errors))
    for image, value in checked.items():
        if identity(local_tag(image, arch), arch, execute, known=value) != value:
            raise ValueError("Image changed during validation")
    receipt.write_text(
        json.dumps({"release": release, "arch": arch, "images": checked}, indent=2) + "\n"
    )


def stage(release, arch, reports, execute=run):
    (reports / "platform-published.json").unlink(missing_ok=True)
    receipt = json.loads((reports / "validated.json").read_text())
    if (
        receipt["release"] != release
        or receipt["arch"] != arch
        or set(receipt["images"]) != {e["image"] for e in release["entries"]}
    ):
        raise ValueError("No matching successful validation receipt")
    for image, checked in receipt["images"].items():
        if identity(local_tag(image, arch), arch, execute, known=checked) != checked:
            raise ValueError("Image differs from the validated image")
    images = {}
    for entry in release["entries"]:
        image = entry["image"]
        checked = receipt["images"][image]
        staging = f"{entry['repository']}:checked-{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}-{release['ref'][1:]}-{arch}"
        execute("docker", "tag", checked["id"], staging)
        if "config_id" in checked or "manifest_id" in checked:
            execute("docker", "push", "--platform", f"linux/{arch}", staging)
        else:
            execute("docker", "push", staging)
        manifest = json.loads(
            execute(
                "docker",
                "buildx",
                "imagetools",
                "inspect",
                staging,
                "--format",
                "{{json .Manifest}}",
            )
        )
        digest = manifest.get("digest", "")
        if not DIGEST.fullmatch(digest):
            raise ValueError("Invalid pushed platform digest")
        reference = f"{entry['repository']}@{digest}"
        raw = json.loads(execute("docker", "buildx", "imagetools", "inspect", reference, "--raw"))
        observed = digest if checked["kind"] == "manifest" else raw.get("config", {}).get("digest")
        if observed != checked.get("config_id", checked.get("manifest_id", checked["id"])):
            raise ValueError("Registry config/manifest differs from the scanned image")
        images[image] = {"reference": reference, "checked": checked}
    (reports / "platform-published.json").write_text(
        json.dumps({"release": release, "arch": arch, "images": images}, indent=2) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "validate", "stage"))
    parser.add_argument("--source", type=Path, default=Path("source"))
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    args = parser.parse_args()
    release = json.loads(os.environ["RELEASE"])
    arch = os.environ["TEST_ARCH"]
    if arch not in ("amd64", "arm64"):
        raise ValueError("Unsupported architecture")
    args.reports = args.reports.resolve()
    args.reports.mkdir(parents=True, exist_ok=True)
    if args.operation == "prepare":
        prepare(release, arch, args.source, args.reports)
    elif args.operation == "validate":
        validate(release, arch, args.source, args.reports)
    else:
        stage(release, arch, args.reports)


if __name__ == "__main__":
    main()
