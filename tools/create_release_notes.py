#!/usr/bin/env python3
"""Generate notes from reachable history and verified publication receipts."""

import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess

from change_plan import IMAGES
from release_plan import IMAGE_NAMES

ROOT = Path(__file__).resolve().parents[1]
STABLE = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
SHA = re.compile(r"[a-f0-9]{40,64}")


def version(tag):
    match = STABLE.fullmatch(tag)
    if not match:
        raise ValueError("Expected a stable vMAJOR.MINOR.PATCH tag")
    return tuple(map(int, match.groups()))


def previous_tag(tag, reachable):
    current = version(tag)
    candidates = [item for item in reachable if STABLE.fullmatch(item) and version(item) < current]
    return max(candidates, key=version) if candidates else None


def markdown_text(value):
    value = html.escape(" ".join(value.split()), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", value).replace("@", "&#64;")


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=120).strip()


def publication_images(tag, repository, sha, publication):
    version(tag)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not SHA.fullmatch(sha):
        raise ValueError("Invalid repository or commit")
    release = publication["release"]
    if release["ref"] != tag or release["sha"] != sha or set(publication["images"]) != set(IMAGES):
        raise ValueError("Publication does not match the release")
    images = {}
    for image in IMAGES:
        data = publication["images"][image]
        expected = f"ghcr.io/{repository.split('/')[0].lower()}/{IMAGE_NAMES[image]}"
        if data["repository"] != expected or not DIGEST.fullmatch(data["digest"]):
            raise ValueError("Invalid published image digest/repository")
        images[image] = (expected, data["digest"])
    if tag[1:] not in publication["aliases"]:
        raise ValueError("Missing published version alias")
    return images, "latest" in publication["aliases"]


def render(tag, previous, commits, repository, images):
    base = f"https://github.com/{repository}"
    lines = [f"# MediaWiki {tag}", "", "## Changes", ""]
    for sha, subject in commits:
        if not SHA.fullmatch(sha) or not subject.strip():
            raise ValueError("Invalid commit metadata")
        lines.append(f"- {markdown_text(subject)} ([{sha[:7]}]({base}/commit/{sha}))")
    if not commits:
        lines.append("- No new non-merge commits since the preceding stable release.")
    lines += ["", "## Published images", "", "Platforms: `linux/amd64`, `linux/arm64`.", ""]
    for image in IMAGES:
        name, digest = images[image]
        lines += [f"- `{name}:{tag[1:]}`", f"  - Published index: `{name}@{digest}`"]
    lines += [
        "",
        "## Install or update",
        "",
        f"Follow the [README for this release]({base}/blob/{tag}/README.md).",
        "Review configuration changes and back up persistent data before updating.",
        "",
    ]
    if previous:
        lines.append(f"[Full changelog]({base}/compare/{previous}...{tag})")
    else:
        lines.append(f"[Release source]({base}/tree/{tag})")
    return "\n".join(lines) + "\n"


def publish_notes(tag, repository, notes, latest, execute=command):
    """Preserve existing drafts/notes; propagate API failures instead of guessing absence."""
    version(tag)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    releases = execute(
        "gh", "api", "--paginate", f"repos/{repository}/releases", "--jq", ".[].tag_name"
    )
    if tag in releases.splitlines():
        print(f"Preserving existing release {tag}")
        return
    execute(
        "gh",
        "release",
        "create",
        tag,
        "--repo",
        repository,
        "--verify-tag",
        "--title",
        f"MediaWiki {tag}",
        "--notes-file",
        str(notes),
        f"--latest={str(latest).lower()}",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--repository", default=os.environ.get("GITHUB_REPOSITORY", "alaub81/mediawiki")
    )
    parser.add_argument("--publication", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--publish", action="store_true", help="Create the GitHub release after generation"
    )
    args = parser.parse_args()
    version(args.tag)
    sha = command("git", "rev-parse", f"refs/tags/{args.tag}^{{commit}}")
    images, latest = publication_images(
        args.tag, args.repository, sha, json.loads(args.publication.read_text())
    )
    previous = previous_tag(args.tag, command("git", "tag", "--merged", sha).splitlines())
    revision = f"{previous}..{sha}" if previous else sha
    history = command("git", "log", "--no-merges", "--format=%H%x09%s", revision)
    commits = [tuple(line.split("\t", 1)) for line in history.splitlines()]
    args.output.write_text(
        render(args.tag, previous, commits, args.repository, images), encoding="utf-8"
    )
    if args.publish:
        publish_notes(args.tag, args.repository, args.output, latest)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Release notes failed: {error}") from error
