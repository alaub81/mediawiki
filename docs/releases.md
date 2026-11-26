# Releases and package refreshes

This is step 4 of Repository Standard v1. It changes release automation, not the
application Dockerfiles or dependency-update policy. Branch protection remains
deferred and KIWIOne is outside this migration.

## Regular release

1. Push the source commit to the default branch and wait for its CI to finish.
2. Only after successful CI, push an existing local stable `vMAJOR.MINOR.PATCH` tag
   pointing to that exact commit. Prereleases are not supported by this workflow.
3. The planner checks GitHub's CI runs for that SHA, push event and default branch.
   The newest run/attempt must be completed and successful. Missing, failed,
   queued or unverifiable CI blocks planning; there is no polling loop or bypass.
4. The previous lower stable tag must be reachable from the selected source.
   Changed image inputs build; unchanged images reuse a verified immutable index
   from that previous release. A missing image/platform falls back to a build;
   registry authentication/network errors fail instead of silently falling back.
5. Native amd64 and arm64 jobs each prepare both images. Reuse-only runs skip the
   empty build definition. Per-image/architecture caches are configured only for
   targets actually being built. Current `resources/<image>/Dockerfile` layouts
   and historical root Dockerfiles are recognized from the selected checkout.
6. Each job tests both images together with the shared full E2E suite, including
   MemcachePHP security behavior. It also scans both exact local IDs, including
   reused images, with the full JSON/SARIF and fixable CRITICAL policy.
   A failed E2E still permits scan evidence collection, but no success receipt.
7. Only validated images can be pushed to run/attempt/version/platform-specific
   `checked-*` staging tags. Their remote manifest/config identities must match
   the local validated images. No rebuild occurs after validation.
8. After **all** required platform jobs succeed, the publisher requires both
   matching platform receipts, verifies staged content and both candidate indexes,
   then promotes the checked immutable indexes to public image aliases.
9. A tag push creates English release notes and a public GitHub release only
   after both complete multi-platform images have been published successfully.

The own image names remain `ghcr.io/alaub81/mediawiki-custom` and
`ghcr.io/alaub81/memcachephp`, with version tags without the leading `v`.
Only the third-party Wikimedia OpenSearch test dependency is emulated on arm64;
the own images build and run natively on the configured GitHub runners.

HIGH findings appear in the scan logs and full reports. Fixable CRITICAL findings block publication.
A historical tag with older green CI must still pass current release tests/scans;
recognizing its file layout is not a promise that every historical version passes.

## Alias and identity safety

Full versions always refer to the selected release. Major/minor aliases only move
for the newest stable version in their series; `latest` only moves for the newest
stable tag overall. The publisher rechecks remote tag names and the target tag's
commit before promotion, so a newly created higher version cannot make a stale
plan move `latest` backwards. Moved target tags and API failures block publication.

Classic Docker config IDs, platform manifest IDs and Docker 29 index IDs are
handled separately. If Docker keeps an index descriptor during platform inspect,
validation exports that one platform to a temporary archive, reads its verified
config digest without extracting layers, and checks the local ID before/after.
The archive is removed immediately. Staging pushes the selected platform and
compares its remote config digest to that recorded config. The immutable index
ID still binds the image used for E2E and scanning. This avoids equating an index
digest with a config digest. Index exports add local I/O, not another build.
When platform inspection exposes a child manifest, that manifest digest is
recorded separately: local scanning still uses the daemon-addressable root ID,
while registry verification uses the selected platform digest. This avoids
asking Trivy to inspect a child ID that the daemon cannot resolve directly.

Both platform digests are checked in the final index. This pipeline publishes
runtime platform manifests; it does not claim separate SBOM/provenance attachment.
Cross-repository alias updates cannot be atomic: a registry failure during final
promotion can leave one image updated. No successful GitHub release is created
in that case; repair/rerun the failed publication before announcing completion.

## Scheduled and manual refreshes

The existing Tuesday 01:00 UTC schedule refreshes the newest stable tag.
For manual runs, retain the existing inputs: set `rebuild_tags=true` and choose
`num_tags` from 1 to 20 (default 1). Leaving the enable flag false skips the plan.

Refreshes rebuild both images with cache disabled and fresh base pulls so that
their Dockerfile package steps are rerun. They still require exact-commit CI,
both architecture tests and fresh scans. Rerunning package steps does not
guarantee that upstream has fixed every vulnerability. Refreshes neither create
new GitHub releases nor overwrite existing release text. Original release notes
record the initial publication; refresh receipts record replacement digests.

A single global release concurrency group serializes tag pushes and refreshes.
Within a run, architecture/tag jobs use `fail-fast: false`. One failed selected
tag/architecture blocks final publication for that whole run. Staging tags can
remain after failures; they are not version aliases and are not deployment tags.

## Notes and recovery

Notes include non-merge commits, including direct commits, since the preceding
reachable lower stable tag. They contain commit links, a comparison/source link,
tag-bound README and both actual published index digests. Commit metadata is
escaped. Review breaking changes and migrations before tagging; an automatic
commit list does not infer a migration procedure.

The notes helper checks all existing releases, including drafts, without editing
them. API errors fail the job rather than being interpreted as absence. Creation
uses `gh release create --verify-tag --notes-file`; it never creates a tag.
Only the notes job has content-write permission. Package writes are confined to
staging and final image publication; the plan has read-only access.

Full scan reports and E2E diagnostics are uploaded even after validation failures,
with public-repository SARIF upload when files exist. Evidence and successful
publication receipts are retained for seven days. A final publish/notes failure
can be retried with **Re-run failed jobs**, reusing successful platform receipts
without rebuilding. If receipts have expired, rerun validation rather than
inventing replacement evidence. Existing release texts remain unchanged on retry.

For a local notes preview, use a downloaded `published.json` from a successful
publication and a checkout containing its tag:

```bash
./tests/run-python.sh tools/create_release_notes.py --tag v1.46.12 \
  --publication /tmp/published.json --output /tmp/release-notes.md
```

Omitting `--publish` only writes the local preview. Offline tests use fake registry
and API responses to exercise negative publication paths without publishing images,
tags or GitHub releases. Native bake definitions can additionally be checked with
`docker buildx bake -f /tmp/build.json --print` before starting a build.
