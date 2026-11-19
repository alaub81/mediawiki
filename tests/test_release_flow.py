"""Prevent failed validation, wrong images and incomplete platforms from reaching public aliases."""

import json
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from release_plan import plan_images
from release_platform import exported_config, identity, prepare, stage, validate
from release_publish import collect, publish, remote_sha


def release_fixture():
    release = {"ref": "v2.0.0", "aliases": ["2.0.0", "2.0", "2", "latest"], "sha": "a" * 40}
    release["entries"] = plan_images(release, release["sha"], None, None, "Owner")
    return release


class ReleaseFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.release = release_fixture()
        self.identifier = "sha256:" + "1" * 64
        self.digests = {"amd64": "sha256:" + "3" * 64, "arm64": "sha256:" + "4" * 64}
        self.commands = []
        self.bad_registry = False
        self.fail_validation = None

    def execute(self, *args, **kwargs):
        self.commands.append(args)
        if args[:3] == ("docker", "image", "inspect"):
            arch = args[-1].rsplit(":", 1)[1]
            return json.dumps([{"Os": "linux", "Architecture": arch, "Id": self.identifier}])
        if args[0] == "bash" and self.fail_validation and self.fail_validation in args[1]:
            raise subprocess.CalledProcessError(1, args, output="test failure")
        if args[:2] == ("gh", "api"):
            if "--paginate" in args:
                return "v2.0.0\nv3.0.0"
            return json.dumps({"object": {"type": "commit", "sha": self.release["sha"]}})
        if args[:4] == ("docker", "buildx", "imagetools", "inspect"):
            if args[-1] == "--raw":
                return json.dumps(
                    {"config": {"digest": "wrong" if self.bad_registry else self.identifier}}
                )
            ref = args[4]
            if ref.endswith(("-amd64", "-arm64")):
                return json.dumps({"digest": self.digests[ref.rsplit("-", 1)[1]]})
            return json.dumps(
                {
                    "digest": "sha256:" + "5" * 64,
                    "manifests": [
                        {"digest": digest, "platform": {"os": "linux", "architecture": arch}}
                        for arch, digest in self.digests.items()
                    ],
                }
            )
        return ""

    def receipts(self):
        for arch in self.digests:
            directory = self.directory / arch
            directory.mkdir(exist_ok=True)
            images = {
                e["image"]: {
                    "reference": e["repository"] + "@" + self.digests[arch],
                    "checked": {"id": self.identifier, "kind": "config"},
                }
                for e in self.release["entries"]
            }
            (directory / "platform-published.json").write_text(
                json.dumps({"release": self.release, "arch": arch, "images": images})
            )

    def test_e2e_or_scan_failure_still_collects_other_evidence_but_cannot_stage(self):
        for failure in ("e2e-check", "scan-images"):
            with self.subTest(failure=failure):
                self.fail_validation = failure
                self.commands.clear()
                with self.assertRaisesRegex(ValueError, "validation failed"):
                    validate(self.release, "amd64", self.directory, self.directory, self.execute)
                self.assertEqual(len([c for c in self.commands if c[0] == "bash"]), 2)
                self.assertFalse((self.directory / "validated.json").exists())
                with self.assertRaises(FileNotFoundError):
                    stage(self.release, "amd64", self.directory, self.execute)
                self.assertFalse(any(c[:2] == ("docker", "push") for c in self.commands))

    def test_only_same_scanned_config_is_staged_without_a_rebuild(self):
        validate(self.release, "amd64", self.directory, self.directory, self.execute)
        with patch.dict(os.environ, GITHUB_RUN_ID="123"):
            stage(self.release, "amd64", self.directory, self.execute)
        self.assertTrue((self.directory / "platform-published.json").is_file())
        self.assertEqual(len([c for c in self.commands if c[:2] == ("docker", "push")]), 2)
        self.assertFalse(any("build" in c or ":latest" in " ".join(c) for c in self.commands))

    def test_wrong_plan_changed_local_id_or_registry_mismatch_cannot_succeed(self):
        validate(self.release, "amd64", self.directory, self.directory, self.execute)
        other = dict(self.release, ref="v2.0.1")
        with self.assertRaisesRegex(ValueError, "receipt"):
            stage(other, "amd64", self.directory, self.execute)
        self.identifier = "sha256:" + "9" * 64
        with self.assertRaisesRegex(ValueError, "differs"):
            stage(self.release, "amd64", self.directory, self.execute)
        self.identifier = "sha256:" + "1" * 64
        self.bad_registry = True
        with patch.dict(os.environ, GITHUB_RUN_ID="123"):
            with self.assertRaisesRegex(ValueError, "Registry"):
                stage(self.release, "amd64", self.directory, self.execute)
        self.assertFalse((self.directory / "platform-published.json").exists())

    def test_incomplete_duplicate_and_mismatched_platform_receipts_fail(self):
        self.receipts()
        self.assertEqual(set(collect(self.release, self.directory)), {"amd64", "arm64"})
        (self.directory / "arm64/platform-published.json").unlink()
        with self.assertRaisesRegex(ValueError, "Both"):
            collect(self.release, self.directory)
        self.receipts()
        with self.assertRaisesRegex(ValueError, "Mismatched"):
            collect(dict(self.release, sha="b" * 40), self.directory)
        duplicate = self.directory / "duplicate"
        duplicate.mkdir()
        (duplicate / "platform-published.json").write_bytes(
            (self.directory / "arm64/platform-published.json").read_bytes()
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            collect(self.release, self.directory)

    def test_complete_release_checks_both_indexes_before_aliases_and_rechecks_latest(self):
        self.receipts()
        with patch.dict(os.environ, GITHUB_RUN_ID="123"):
            publish(
                self.release,
                self.directory,
                "Owner/mediawiki",
                self.directory / "published.json",
                self.execute,
            )
        public = [
            c
            for c in self.commands
            if c[:4] == ("docker", "buildx", "imagetools", "create")
            and any(arg.endswith(":2.0.0") for arg in c)
        ]
        self.assertEqual(len(public), 2)
        self.assertFalse(any(arg.endswith(":latest") for c in public for arg in c))
        index_checks = [
            i
            for i, c in enumerate(self.commands)
            if c[:4] == ("docker", "buildx", "imagetools", "inspect") and c[-1] != "--raw"
        ]
        self.assertLess(max(index_checks), self.commands.index(public[0]))
        publication = json.loads((self.directory / "published.json").read_text())
        self.assertEqual(set(publication["images"]), {"mediawiki", "memcachephp"})
        self.assertNotIn("latest", publication["aliases"])

    def test_bad_registry_or_moved_tag_never_moves_public_aliases(self):
        self.receipts()
        self.bad_registry = True
        with self.assertRaisesRegex(ValueError, "Staged"):
            publish(
                self.release,
                self.directory,
                "Owner/mediawiki",
                self.directory / "published.json",
                self.execute,
            )
        with patch("release_publish.remote_sha", return_value="b" * 40):
            with self.assertRaisesRegex(ValueError, "tag changed"):
                publish(
                    self.release,
                    self.directory,
                    "Owner/mediawiki",
                    self.directory / "published.json",
                    self.execute,
                )
        self.assertFalse(
            any(c[:4] == ("docker", "buildx", "imagetools", "create") for c in self.commands)
        )

    def test_annotated_remote_tag_is_peeled_and_api_errors_propagate(self):
        def execute(*args):
            if "/git/ref/" in args[-1]:
                return json.dumps({"object": {"type": "tag", "sha": "c" * 40}})
            return json.dumps({"object": {"type": "commit", "sha": "a" * 40}})

        self.assertEqual(remote_sha("Owner/mediawiki", "v2.0.0", execute), "a" * 40)
        with patch("release_publish.remote_sha", side_effect=OSError("offline")):
            self.receipts()
            with self.assertRaises(OSError):
                publish(
                    self.release,
                    self.directory,
                    "Owner/mediawiki",
                    self.directory / "published.json",
                    self.execute,
                )

    def test_reuse_only_and_mixed_build_definition_select_only_needed_targets(self):
        for entry in self.release["entries"]:
            entry.update(mode="reuse", source=entry["repository"] + "@" + self.digests["amd64"])
        with patch.dict(
            os.environ,
            GITHUB_OUTPUT=str(self.directory / "outputs"),
            GITHUB_REPOSITORY="Owner/mediawiki",
        ):
            prepare(self.release, "amd64", self.directory, self.directory, self.execute)
            self.assertEqual(json.loads((self.directory / "build.json").read_text())["target"], {})
            self.assertIn("has_builds=false", (self.directory / "outputs").read_text())
            entry = self.release["entries"][0]
            entry["mode"] = "build"
            folder = self.directory / "resources/mediawiki"
            folder.mkdir(parents=True)
            (folder / "Dockerfile").write_text("FROM example\n")
            prepare(self.release, "amd64", self.directory, self.directory, self.execute)
            target = json.loads((self.directory / "build.json").read_text())["target"]
            self.assertEqual(set(target), {"mediawiki"})
            self.assertEqual(target["mediawiki"]["platforms"], ["linux/amd64"])

    def test_containerd_manifest_identity_is_not_compared_to_config_digest(self):
        descriptor = {"mediaType": "application/vnd.oci.image.manifest.v1+json"}

        def execute(*args):
            return json.dumps(
                [
                    {
                        "Os": "linux",
                        "Architecture": "arm64",
                        "Id": self.identifier,
                        "Descriptor": descriptor,
                    }
                ]
            )

        self.assertEqual(identity("image", "arm64", execute)["kind"], "manifest")

    def test_index_identity_binds_exported_config_without_resaving_known_ids(self):
        image = {
            "Os": "linux",
            "Architecture": "arm64",
            "Id": self.identifier,
            "Descriptor": {"mediaType": "application/vnd.oci.image.index.v1+json"},
        }

        def execute(*args):
            return json.dumps([image])

        config_id = "sha256:" + "8" * 64
        with patch("release_platform.exported_config", return_value=config_id) as export:
            checked = identity("image", "arm64", execute)
            self.assertEqual(checked["config_id"], config_id)
            self.assertEqual(identity("image", "arm64", execute, known=checked), checked)
            self.assertEqual(export.call_count, 1)

    def test_platform_export_config_checksum_and_architecture_are_verified(self):
        data = json.dumps({"os": "linux", "architecture": "arm64"}).encode()
        digest = hashlib.sha256(data).hexdigest()

        def execute(*args):
            output = Path(args[args.index("--output") + 1])
            files = {
                "manifest.json": json.dumps([{"Config": f"blobs/sha256/{digest}"}]).encode(),
                f"blobs/sha256/{digest}": data,
            }
            with tarfile.open(output, "w") as archive:
                for name, content in files.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
            return ""

        self.assertEqual(exported_config("image", "arm64", execute), "sha256:" + digest)
        with self.assertRaisesRegex(ValueError, "wrong platform"):
            exported_config("image", "amd64", execute)

    def test_selected_child_manifest_keeps_daemon_index_id_for_local_scanning(self):
        child = "sha256:" + "7" * 64

        def execute(*args):
            selected = "--platform" in args
            return json.dumps(
                [
                    {
                        "Os": "linux",
                        "Architecture": "arm64",
                        "Id": child if selected else self.identifier,
                        "Descriptor": {
                            "mediaType": "application/vnd.oci.image.manifest.v1+json"
                            if selected
                            else "application/vnd.oci.image.index.v1+json"
                        },
                    }
                ]
            )

        checked = identity("image", "arm64", execute)
        self.assertEqual(checked["id"], self.identifier)
        self.assertEqual(checked["manifest_id"], child)

    def test_index_staging_checks_selected_manifest_or_config_and_pushes_one_platform(self):
        for kind in ("manifest", "config"):
            with self.subTest(kind=kind):
                self.commands.clear()
                checked = {"id": self.identifier, "kind": kind}
                checked["manifest_id" if kind == "manifest" else "config_id"] = self.digests[
                    "amd64"
                ]
                (self.directory / "validated.json").write_text(
                    json.dumps(
                        {
                            "release": self.release,
                            "arch": "amd64",
                            "images": {
                                entry["image"]: checked for entry in self.release["entries"]
                            },
                        }
                    )
                )

                def execute(*args, **kwargs):
                    if args[:3] == ("docker", "image", "inspect"):
                        selected = "--platform" in args and kind == "manifest"
                        return json.dumps(
                            [
                                {
                                    "Os": "linux",
                                    "Architecture": "amd64",
                                    "Id": self.digests["amd64"] if selected else self.identifier,
                                    "Descriptor": {
                                        "mediaType": "application/vnd.oci.image.manifest.v1+json"
                                        if selected
                                        else "application/vnd.oci.image.index.v1+json"
                                    },
                                }
                            ]
                        )
                    if args[-1] == "--raw":
                        return json.dumps({"config": {"digest": self.digests["amd64"]}})
                    return self.execute(*args, **kwargs)

                with patch.dict(os.environ, GITHUB_RUN_ID="123"):
                    stage(self.release, "amd64", self.directory, execute)
                pushes = [c for c in self.commands if c[:2] == ("docker", "push")]
                self.assertEqual(len(pushes), 2)
                self.assertTrue(all("--platform" in c and "linux/amd64" in c for c in pushes))


if __name__ == "__main__":
    unittest.main()
