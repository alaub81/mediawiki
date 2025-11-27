# ToDos

[?] MARIADB_VARS doch setzen und wiki DB anlegen lassen? testen
[!] !!nicht machen!! - MW_SITEMAP_IDENTIFIER=wiki und $wgArticlePath = "/wiki/$1"; kann noch in die redirects und in die shortURLs?
[?] ExternalContent Extension wenn für 1.44 verfügbar [ExternalContent](https://www.mediawiki.org/wiki/Extension:External_Content)
[!] !!nicht machen!! - Database Port kann weg beim mw-default installer!
[!] !!geht nicht als default!! copy bei SyntaxHighlight
[?] Artikel kleinschreiben

  ```php
  // Make first character of page titles case-sensitive globally
  $wgCapitalLinks = false; // Changes canonical titles. Test on staging first!
  // Override just the main namespace to allow lowercase first letters
  $wgCapitalLinkOverrides[NS_MAIN] = false; // Only main namespace is affected
  ```

[] Kategorien aufräumen --> Unterkategorien --> bei den Haupt Categorien Logos und Text
[] Page Speed Results umsetzen
[] Wenn Google Adsense geht: CSP aktivieren und Header Prüfen, Pagespeed tests
    <https://securityheaders.com/?q=https%3A%2F%2Flhlab.wiki&followRedirects=on>
    <https://pagespeed.web.dev/analysis/https-lhlab-wiki-wiki-Dimplex_Wärmepumpe_Smart-Grid_mit_Shelly_Relais/57ygqq2725?form_factor=mobile>

```bash
# Jpbs für Index
php maintenance/run.php ./extensions/CirrusSearch/maintenance/CirrusNeedsToBeBuilt.php
php maintenance/run.php ./extensions/CirrusSearch/maintenance/ForceSearchIndex.php --skipLinks --indexOnSkip
php maintenance/run.php ./extensions/CirrusSearch/maintenance/ForceSearchIndex.php --skipParse
php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSuggesterIndex.php
php maintenance/run.php showJobs
php maintenance/run.php showJobs --group
php maintenance/run.php runJobs
```

## MW Setup Script

```txt
Script runner options:
    --conf <CONF>: Location of LocalSettings.php, if not default
    --globals: Output globals at the end of processing for debugging
    --help (-h): Display this help message
    --memory-limit <MEMORY-LIMIT>: Set a specific memory limit for the
        script, "max" for no limit or "default" to avoid changing it
    --profiler <PROFILER>: Profiler output format (usually "text")
    --quiet (-q): Whether to suppress non-error output
    --server <SERVER>: The protocol and server name to use in URLs, e.g.
        https://en.wikipedia.org. This is sometimes necessary because server
        name detection may fail in command line scripts.
    --wiki <WIKI>: For specifying the wiki ID

Common options:
    --dbgroupdefault <DBGROUPDEFAULT>: The default DB group to use.
    --dbpass <DBPASS>: The password for the DB user for normal
        operations
    --dbuser <DBUSER>: The user to use for normal operations (wikiuser)

Script specific options:
    --confpath <CONFPATH>: Path to write LocalSettings.php to
        (/var/www/html)
    --dbname <DBNAME>: The database name (my_wiki)
    --dbpassfile <DBPASSFILE>: An alternative way to provide dbpass
        option, as the contents of this file
    --dbpath <DBPATH>: The path for the SQLite DB ($IP/data)
    --dbport <DBPORT>: The database port; only for PostgreSQL (5432)
    --dbprefix <DBPREFIX>: Optional database table name prefix
    --dbschema <DBSCHEMA>: The schema for the MediaWiki DB in PostgreSQL
        (mediawiki)
    --dbserver <DBSERVER>: The database host (localhost)
    --dbssl: Connect to the database over SSL
    --dbtype <DBTYPE>: The type of database (mysql)
    --env-checks: Run environment checks only, don't change anything
    --extensions <EXTENSIONS>: Comma-separated list of extensions to
        install
    --installdbpass <INSTALLDBPASS>: The password for the DB user to
        install as.
    --installdbuser <INSTALLDBUSER>: The user to use for installing
        (root)
    --lang <LANG>: The language to use (en)
    --pass <PASS>: The password for the wiki administrator.
    --passfile <PASSFILE>: An alternative way to provide pass option, as
        the contents of this file
    --scriptpath <SCRIPTPATH>: The relative path of the wiki in the web
        server (/html)
    --skins <SKINS>: Comma-separated list of skins to install (default:
        all)
    --with-developmentsettings: Load DevelopmentSettings.php in
        LocalSettings.php
    --with-extensions: Detect and include extensions

Arguments:
    [name]: The name of the wiki
    [admin]: The username of the wiki administrator.

```
