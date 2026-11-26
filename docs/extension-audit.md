# Read-only extension usage audit

Run the standard-library Python audit from the repository root against the running
wiki's actual API endpoint (adjust the URL, including `/w/` if applicable):

```sh
python3 tools/audit_extensions.py --api https://wiki.example.org/api.php
```

The script uses only HTTP GET requests with `action=query`. It does not edit wiki
pages, configuration, the database, or cookie files, and does not trigger parsing,
maintenance scripts or index rebuilds. Normal server request logs/session handling
may still occur. No Docker exec or database credentials are required.

It inventories loaded extensions, then reads the latest revision of every
API-visible page in every nonvirtual namespace, including templates, modules,
redirects and all content slots. It reports source evidence (counts and up to five
example titles), provisional candidates, and extensions requiring manual review.
Source evidence can also be documentation or an unused template; it is not a usage
counter. Background services, security tools, editors and unknown extensions are
never classified as unused just because no markup was found.

Only when the API session can read **all pages and namespaces**, including any
Lockdown-restricted namespaces, enable provisional candidates explicitly:

```sh
python3 tools/audit_extensions.py --api https://wiki.example.org/api.php \
  --confirm-full-read-access --json > extension-audit.json
```

This flag is your assertion, not an automatic permission check. For private wikis,
pass `--cookie-file /path/to/session-cookies.txt` with an existing Netscape-format
session-cookie file over HTTPS. The script does not log in or save cookies. Use an
account with complete read access; administrator status alone may not guarantee it.
Redirects are refused: supply the final API URL. Reports may contain private page
titles, so keep their output private as appropriate.

Candidate detection is deliberately limited to known content-oriented extensions.
Lua modules, `#invoke`, or computed `#tag` names suppress all candidates because
syntax may be generated dynamically. API errors/warnings or missing revision
content abort the scan with exit code 1 and no report. Successful scans exit 0,
including scans with manual-review items. Progress goes to stderr, reports to stdout.

The audit does not inspect historical/deleted content, extension database tables,
server settings, access logs, external API consumers or extension dependency
manifests. It is not an atomic snapshot. Before disabling a candidate, check its
configuration and dependencies and test representative pages in a staging wiki.
A candidate means **no known syntax found in the scanned scope**, not proof that
removal is safe. The API cannot reliably reveal pages silently hidden by access
control extensions.

API references: [Siteinfo](https://www.mediawiki.org/wiki/API:Siteinfo),
[Allpages](https://www.mediawiki.org/wiki/API:Allpages),
[Revisions](https://www.mediawiki.org/wiki/API:Revisions).
