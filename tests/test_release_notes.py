"""Keep release notes complete, escaped, tag-bound and idempotent."""

import copy
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock

from create_release_notes import previous_tag, publication_images, publish_notes, render
from release_plan import IMAGE_NAMES
from test_release_flow import release_fixture


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.release = release_fixture()
        self.publication = {
            "release": self.release,
            "aliases": self.release["aliases"],
            "images": {
                image: {"repository": f"ghcr.io/owner/{name}", "digest": "sha256:" + "b" * 64}
                for image, name in IMAGE_NAMES.items()
            },
        }

    def test_semver_reachable_candidates_and_initial_release(self):
        self.assertEqual(
            previous_tag("v2.0.0", ["v1.9.0", "v1.10.0", "v3.0.0", "v2.0.0-rc1"]), "v1.10.0"
        )
        self.assertIsNone(previous_tag("v1.0.0", []))

    def test_both_real_image_names_and_digests_appear_in_notes_with_escaped_direct_commits(self):
        images, latest = publication_images("v2.0.0", "Owner/mediawiki", "a" * 40, self.publication)
        text = render(
            "v2.0.0",
            "v1.9.0",
            [("a" * 40, "Fix [link](bad) @everyone <tag>")],
            "Owner/mediawiki",
            images,
        )
        self.assertTrue(latest)
        self.assertIn("ghcr.io/owner/mediawiki-custom:2.0.0", text)
        self.assertIn("ghcr.io/owner/memcachephp:2.0.0", text)
        self.assertIn("&#64;everyone &lt;tag&gt;", text)
        self.assertIn("/compare/v1.9.0...v2.0.0", text)
        self.assertIn("/blob/v2.0.0/README.md", text)

    def test_incomplete_wrong_sha_and_bad_digest_publications_fail(self):
        broken = copy.deepcopy(self.publication)
        broken["images"].pop("mediawiki")
        with self.assertRaises(ValueError):
            publication_images("v2.0.0", "Owner/mediawiki", "a" * 40, broken)
        with self.assertRaises(ValueError):
            publication_images("v2.0.0", "Owner/mediawiki", "c" * 40, self.publication)
        broken = copy.deepcopy(self.publication)
        broken["images"]["mediawiki"]["digest"] = "wrong"
        with self.assertRaises(ValueError):
            publication_images("v2.0.0", "Owner/mediawiki", "a" * 40, broken)

    def test_existing_release_draft_or_api_error_never_overwrites_notes(self):
        execute = Mock(return_value="v1.0.0\nv2.0.0")
        publish_notes("v2.0.0", "Owner/mediawiki", Path("notes.md"), True, execute)
        self.assertEqual(execute.call_count, 1)
        execute = Mock(side_effect=subprocess.CalledProcessError(1, ["gh"]))
        with self.assertRaises(subprocess.CalledProcessError):
            publish_notes("v2.0.0", "Owner/mediawiki", Path("notes.md"), True, execute)
        self.assertEqual(execute.call_count, 1)

    def test_create_verifies_remote_tag_and_older_release_is_not_latest(self):
        execute = Mock(side_effect=["v3.0.0", "created"])
        publish_notes("v2.0.0", "Owner/mediawiki", Path("notes.md"), False, execute)
        self.assertIn("--verify-tag", execute.call_args.args)
        self.assertIn("--notes-file", execute.call_args.args)
        self.assertIn("--latest=false", execute.call_args.args)


if __name__ == "__main__":
    unittest.main()
