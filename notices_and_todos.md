# ToDos

- [?] MARIADB_VARS doch setzen und wiki DB anlegen lassen? testen
- [!] !!nicht machen!! - MW_SITEMAP_IDENTIFIER=wiki und $wgArticlePath = "/wiki/$1"; kann noch in die redirects und in die shortURLs?
- [?] ExternalContent Extension wenn für 1.44 verfügbar [ExternalContent](https://www.mediawiki.org/wiki/Extension:External_Content)
- [!] !!nicht machen!! - Database Port kann weg beim mw-default installer!
- [!] !!geht nicht als default!! copy bei SyntaxHighlight
- [?] Artikel kleinschreiben

  ```php
  // Make first character of page titles case-sensitive globally
  $wgCapitalLinks = false; // Changes canonical titles. Test on staging first!
  // Override just the main namespace to allow lowercase first letters
  $wgCapitalLinkOverrides[NS_MAIN] = false; // Only main namespace is affected
  ```

- [x] Umbau auf optionale secrets Dateien. LocalSettings.php muss beides nehmen
- [x] Testen aller drei Installations Möglichkeiten
- [x] Prüfen ob die Datenbank Variablen benötigt werden, oder ob sie gar zum Standard werden sollen
- [ ] Kategorien aufräumen --> Unterkategorien --> bei den Haupt Categorien Logos und Text
- [ ] Page Speed Results umsetzen
- [ ] Wenn Google Adsense geht: CSP aktivieren und Header Prüfen, Pagespeed tests
    <https://securityheaders.com/?q=https%3A%2F%2Flhlab.wiki&followRedirects=on>
    <https://pagespeed.web.dev/analysis/https-lhlab-wiki-wiki-Dimplex_Wärmepumpe_Smart-Grid_mit_Shelly_Relais/57ygqq2725?form_factor=mobile>

- [ ] Update des Wiki Artikel
- [ ] docker compose dateien --> example als basis, alle weiteren als addon bauen
- [ ] BIND_ADDRESS=127.0.0.1 einbauen

```bash
php maintenance/run.php /var/www/html/extensions/Wanda/maintenance/ReindexAllPages.php

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

## Installationen

1. szenario: Setup mit mw-defaultsetup.sh
    - aktivieren von .en.mwsetup
    - die andere LocalSettings im compose file
    - compose up -d
    - mw-default-setup.sh starten

2. Setup via LocalSettings.php.example
    - ohne .en.mwsetup
    - normale LocalSettings.php was eine kopie der example ist
    - compose up -d
    - `php maintenance/run.php installPreConfigured --conf /var/www/html/LocalSettings.php'`

3. Setup via Web Config generator
    - starten des compose stacks ohne LocalSettings.php (auskommentieren)
    - `http://localhost:8080`
    - Setup Assistenten durchlaufen und minimum die Datenbank Konfigurationen aus der .env verwenden.

## Code- und README-Review vom 27.09.2026

Statische Prüfung des aktuellen Arbeitsstands. `./linter-check.sh`, `bash -n`, JSON-Prüfung von `renovate.json` und `docker compose config --quiet` für Beispiel-, Entwicklungs- und Secrets-Konfiguration waren erfolgreich. Ein echter Container- und E2E-Test war nicht möglich, da der Zugriff auf den lokalen Docker-Daemon verweigert wurde. Die bestehenden, teils noch nicht committeten Änderungen wurden nicht überschrieben.

### P0 – Installation, Betrieb und Sicherheit

- [ ] **Konfigurationspfad einheitlich machen.** `.env.mwsetup` und CI installieren nach `/var/www/html/conf/LocalSettings.php`, aber der Installer-Parameter `--confpath` erstellt keinen Einstiegspunkt unter `/var/www/html/LocalSettings.php`. `mediawiki-entrypoint.sh`, `mw-default-setup.sh` (`$run update`), CirrusSearch- und RottenLinks-Skripte rufen Wartung ohne `--conf` auf; nur `generate-sitemap.sh` berücksichtigt `MW_CONFIG_FILE`. Entweder die Datei am Standardpfad bereitstellen oder Web- und sämtliche Wartungsaufrufe nachweislich auf denselben Pfad ausrichten. Danach Neuinstallation, Neustart, Schema-Update und Cronjobs testen. Quellen: `.env.mwsetup:6`, `resources/mediawiki/mw-default-setup.sh:95,543`, `resources/mediawiki/mediawiki-entrypoint.sh:55`, [MediaWiki-Installationshandbuch](https://www.mediawiki.org/wiki/Manual:Install.php), [run.php-Handbuch](https://www.mediawiki.org/wiki/Manual:Run.php).
- [x] **Elastica/CirrusSearch-Ladereihenfolge dokumentieren.** Die Ladereihenfolge ist unerheblich. Die README nennt das jetzt ausdrücklich und zeigt dieselbe Reihenfolge wie `LocalSettings.php.example`; die Konfigurationen bleiben unverändert.
- [ ] **Quickstart für eine neue Wiki vollständig beschreiben und ausführbar machen.** `README.md` nennt `env_file` und ein beschreibbares Konfigurationsverzeichnis, aber `docker-compose.example.yml` aktiviert weder das Env-File noch einen Konfigurations-Mount; der Entrypoint ruft `mw-default-setup.sh` nicht auf. Die Schritte müssen den Setup-Aufruf, die Dateirechte, das persistente Ablegen von `LocalSettings.php` und die Umstellung auf einen schreibgeschützten Mount konkret zeigen. Danach den Ablauf mit einem frischen Compose-Projekt testen. Quellen: `README.md` Abschnitt „Quick start“, `docker-compose.example.yml:55-69`, `resources/mediawiki/mediawiki-entrypoint.sh`.
- [ ] **CI-Installation an denselben Konfigurationsablauf anbinden.** CI schreibt `MW_CONFIG_FILE=/var/www/html/conf/LocalSettings.php` und startet das Setup als `www-data`, während die aufgelöste CI-Compose-Konfiguration nur `/var/www/html/images` mountet. Schreibrechte und Persistenz des Konfigurationsverzeichnisses prüfen; dann den CI-Ablauf mit einem leeren Volume und nach Container-Neuerstellung nachstellen. Quellen: `.github/workflows/ci.yml:137,205-209`, `docker-compose.ci.yml`, `docker-compose.example.yml:58-69`.
- [ ] **Beispielwerte sicher und startfähig machen.** `.env.example` aktiviert `MW_WANDA_ENABLED=true` mit einem Platzhalter-API-Key, setzt `MW_AUTO_UPDATE=true` dauerhaft und enthält bekannte Admin-, Datenbank- und MemcachePHP-Passwörter. Sichere Defaults wählen, echte Zugangsdaten als verpflichtenden Setup-Schritt dokumentieren und die abweichenden README-Beispiele angleichen. Quellen: `.env.example:17,83-89,100-102`, `.env.mwsetup:11`, `README.md` Abschnitte „Quick start“ und „Debugging“.
- [ ] **Statische MediaWiki-Schlüssel aus der Beispielkonfiguration entfernen.** `LocalSettings.php.example` enthält einen konkreten `$wgSecretKey` und `$wgUpgradeKey`. Platzhalter bzw. eine dokumentierte Generierung verwenden; prüfen, ob die Werte jemals live verwendet wurden, und sie dann rotieren. Quelle: `data/mediawiki/conf/LocalSettings.php.example:129-136`.

### P1 – Logik und Testaussage

- [x] **MemcachePHP trotz bestehender Basic Auth gegen XSS und unerwünschte Schreibaktionen absichern.** Cache-Schlüssel, Werte und Servernamen werden bei der HTML-Ausgabe escaped; dekodierte Schlüssel und Serverindizes werden vor Memcached-Befehlen geprüft. `delete` und `flush_all` verwenden POST-Formulare mit serverseitigem Session-CSRF-Token. Der isolierte Docker-Integrationstest `tests/memcachephp_security_test.py` prüft 401 ohne Auth, abgewiesene GET- und ungültige POST-Aktionen, gültiges Löschen/Flush, HTML-Ausgabe als Text und abgewiesene CR/LF-Schlüssel.
- [ ] **CirrusSearch-Bootstrap vom periodischen Job trennen.** `update-cirrussearch-index.sh` wertet jeden fehlgeschlagenen Alias-Request als fehlenden Index und startet dann `UpdateSearchIndexConfig --startOver` samt Vollindexierung. Erreichbarkeit, Konfigurationsfehler und tatsächlich fehlende Aliase getrennt behandeln; automatische destruktive Rebuilds vermeiden und benutzerdefinierten Index-Basisnamen aus der MediaWiki-Konfiguration lesen. Quelle: `resources/mediawiki/update-cirrussearch-index.sh:9-32`.
- [x] **CI-Test der MemcachePHP-UI reparieren.** Der bestehende Proxy-Schritt prüft die UI unter `/memcacheui/` mit Basic Auth, HTTP 200 nach Retries und Inhaltskontrolle. Den vorgeschalteten, wirkungslosen Test auf dem nicht veröffentlichten Port 8097 und die zugehörige Env-Variable entfernt. Die 200-Prüfung verwendet jetzt GET statt HEAD, passend zur gehärteten UI; der MemcachePHP-Port bleibt intern. Quelle: `.github/workflows/ci.yml` Abschnitt „E2E — MemcachePHP über MediaWiki-Proxy“.
- [x] **Irreführende CI-Erfolge beseitigen.** Der Skin-Vergleich läuft jetzt in der aktuellen Bash und gibt fehlende Skins zuverlässig als Fehler zurück. Siteinfo wird mit `jq` ausgewertet und ein abweichender Sitename beendet den Schritt. Das CI-Env setzt `CLAMAV_ENABLED`; der Virenscan prüft Variable und Containerwert sowie einen verbindlichen ClamAV-Timeout. Der DB-Wartecode verwendet einen POSIX-kompatiblen Versuchszähler mit 120-Sekunden-Grenze statt `SECONDS` unter `sh`. Lokale Negativtests für fehlendes Skin, falschen Sitename und abgelaufenen Zähler lieferten jeweils Status 1. Quelle: `.github/workflows/ci.yml`.
- [x] **CI um reale Suche, Compose-Profile und Workflow-Linting erweitern.** Die angelegte Testseite enthält einen eindeutigen Suchbegriff und muss nach dem CirrusSearch-Bootstrap über die MediaWiki-Such-API auffindbar sein. Eine Matrix validiert Basis-, ClamAV-, Elasticsearch/Wanda- und Vollprofil mit `docker compose config` und kontrolliert die jeweils enthaltenen Dienste. `actionlint` prüft zusätzlich die GitHub-Actions-Syntax, Ausdrücke und Job-Abhängigkeiten. Der bestehende EICAR-Test bleibt als verbindlicher ClamAV-Funktionstest bestehen. Quelle: `.github/workflows/ci.yml`.
- [ ] **Build-Argumente für Erweiterungen und Skins klären.** `docker-compose.dev.yml` und `docker-compose.ci.yml` übergeben `MW_INSTALL_EXTENSIONS`/`MW_INSTALL_SKINS` als Build-Args, aber `Dockerfile-mediawiki` deklariert keine entsprechenden `ARG` und setzt feste `ENV`-Listen. Entweder `ARG` korrekt verdrahten oder die wirkungslosen Optionen entfernen; zusätzlich `MW_EXTRA_EXTENSIONS` mit der tatsächlich geklonten Liste abgleichen. Quellen: `Dockerfile-mediawiki:1-8`, `docker-compose.dev.yml:5-10`, `.github/workflows/ci.yml:458-489`.
- [ ] **Versionsstrategie für Erweiterungen festlegen.** `clone_with_fallback` weicht bei fehlendem `REL1_46` still auf `main` bzw. Default-HEAD aus. Das widerspricht der README-Aussage, nur passende Release-Branches zu verwenden, und macht Builds zeitabhängig. Für notwendige Erweiterungen inkompatible Branches als Build-Fehler behandeln oder getestete Commits pinnen. Quellen: `Dockerfile-mediawiki:30-56`, `README.md` Abschnitt „Updating MediaWiki“.
- [ ] **Wartungsjobs mit einheitlichen Rechten und Konfiguration starten.** Supercronic läuft als Root und `runJobs` sowie die CirrusSearch-Skripte starten PHP als Root, während Sitemap/RottenLinks `www-data` verwenden. Mit schreibgeschützten Konfigurationsdateien und Upload-Volume prüfen und nach Möglichkeit alle MediaWiki-Jobs als `www-data` ausführen. Quellen: `resources/mediawiki/mediawiki-entrypoint.sh:150-158`, `resources/mediawiki/generate-opensearch-index.sh`, `resources/mediawiki/generate-sitemap.sh`.
- [ ] **Secrets-Anleitung für einen frischen Clone vervollständigen.** `README.md` verweist auf `docker-compose.secrets.yml`, `.env.secrets` und `secrets_example/`; aktuell sind Overlay und Beispieldateien untracked, `.env.secrets` ist ignoriert. Einen versionierten, bereinigten Overlay- und Template-Satz bereitstellen, Kopier- und Rechtebefehle dokumentieren und den Start ohne vorhandene lokale Geheimnisse testen. Keine echten Secret-Dateien committen. Quellen: `README.md` Abschnitt „Use password files“, `.gitignore`, aktueller `git status`.
- [ ] **Ressourcenverbrauch des Stacks optimieren.** Nach den getrennten Messungen für Basis- und Vollprofil die größten Verbraucher priorisieren (Momentaufnahme: OpenSearch 1,44 GiB, Elasticsearch 1,26 GiB, ClamAV 0,99 GiB). Prüfen, welche optionalen Dienste tatsächlich gebraucht werden, ob JVM-Heaps und ClamAV-Konfiguration zur Last passen und ob kleinere Einstellungen ohne Funktionsverlust möglich sind. Jede Änderung einzeln unter vergleichbarer Last messen; Antwortzeiten, Indexierung, Virenscan und OOM/Swap kontrollieren. Vorher-/Nachher-Werte und gewählte Defaults in der README dokumentieren. Quellen: `.env.example` Abschnitte „Optional Docker Services“, „OpenSearch Configuration“ und „Elasticsearch Configuration“, `docker-compose.example.yml`.

### P2 – Dokumentation und Wartbarkeit

- [ ] **Favicon-Verweise korrigieren.** `LocalSettings.php.example` und `mw-default-setup.sh` referenzieren `favicon-16x16.png` und `favicon-32x32.png`, die unter `resources/favicon/` fehlen. Dateien ergänzen oder die Links entfernen; HTTP-Antworten prüfen. Quellen: `data/mediawiki/conf/LocalSettings.php.example:276-288`, `resources/mediawiki/mw-default-setup.sh:351-363`.
- [x] **`SECURITY.md` auf dieses Repository umschreiben.** Projekt, unterstützte Versionslinie, privater GitHub-Meldeweg mit Fallback, Geltungsbereich und realistische Reaktionsaussage sind aktualisiert; fremde Komponenten und Links sind entfernt.
- [x] **Veraltete Release- und Dependency-Automation prüfen.** Fremden `LOGANALYZER_VERSION`-Regex entfernt und Renovate-Automerge auf gültige `matchUpdateTypes` begrenzt. `docker/metadata-action` erzeugte `latest` bei SemVer-Tags implizit; dies ist jetzt deaktiviert. Nur das höchste stabile Tag erhält `1.46`, `1` und `latest`; ältere Tags erhalten nur ihren vollständigen Versions-Tag. Lokaler Dry-Run mit `v1.46.5` und `v1.46.4` erfolgreich. Quellen: `renovate.json`, `.github/workflows/release.yml`.
- [x] **README-Ressourcenbedarf und Profile nachmessen.** Basisprofil separat gestartet und zwei Minuten gemessen: höchster erfasster Wert 1,57 GiB. Vollprofil durch Zuschalten von ClamAV und Elasticsearch vier Minuten gemessen: 3,61 GiB; eine frühere Vollprofil-Momentaufnahme lag bei 4,07 GiB. Je Profil 120 lesende API-Anfragen erfolgreich. Indexlauf verarbeitete nur eine Seite; das DB-Update fand keine ausstehenden Änderungen. Kein OOM, Neustart oder cgroup-Swap am Ende der Messung. README enthält diese Messwerte und vorläufige Planungswerte von 3/6 GiB. Auf Wunsch bleiben die Werte vorläufig; für belastbare Mindestwerte einer größeren Wiki wären Messungen mit repräsentativem Datenbestand nötig. Quellen: `README.md` Abschnitt „Requirements“, `.env.example:90-114`, `docker-compose.example.yml`.

### Optionale CI-Erweiterungen

- [ ] **Optional: MemcachePHP-Sicherheitstest in der CI ausführen.** `tests/memcachephp_security_test.py` als isolierten Job oder Schritt starten, damit Regressionen bei HTML-Escaping, CSRF-Schutz, GET-Schreibschutz, Schlüsselvalidierung und Basic Auth automatisch erkannt werden. Quelle: `tests/memcachephp_security_test.py`.
- [ ] **Optional: Installation und Update auf Idempotenz prüfen.** Nach der Erstinstallation `mw-default-setup.sh` beziehungsweise den Updatepfad erneut ausführen und auf Fehler sowie doppelte Konfigurationszeilen prüfen. Container-Neuerstellung und Konfigurationspersistenz bleiben Teil der weiter oben aufgeführten P0-Punkte. Quellen: `.github/workflows/ci.yml`, `resources/mediawiki/mw-default-setup.sh`.
- [ ] **Optional: Secrets-Overlay in die Compose-Matrix aufnehmen.** Temporäre Test-Secrets erzeugen, das Overlay mit `docker compose config --quiet` validieren und später einen Starttest ergänzen. Die bereinigten Beispiel- und Overlay-Dateien müssen dafür zuerst wie im offenen P1-Punkt beschrieben versioniert sein. Quellen: `docker-compose.secrets.yml`, `.env.secrets`, `secrets_example/`.
- [ ] **Optional: Wanda/Elasticsearch gezielt testen.** Der Vollprofil-Lauf startet Elasticsearch, prüft aber keine Wanda-Funktion. Mindestens Elasticsearch-Verbindung und Wanda-Konfiguration kontrollieren; einen Test gegen die externe KI-API nur mit ausdrücklich dafür vorgesehenem Secret und separatem optionalem Job ausführen. Quellen: `.github/workflows/ci.yml`, `docker-compose.example.yml`, `.env.example`.
- [ ] **Optional: Datenbank-Authentifizierung verpflichtend prüfen.** Den aktuellen optionalen `mysqladmin`/`mariadb-admin`-Test so gestalten, dass ein fehlender Client oder ungültige Zugangsdaten den E2E-Lauf beendet. Damit prüft die CI neben dem offenen TCP-Port auch die tatsächlich konfigurierte Anmeldung. Quelle: `.github/workflows/ci.yml` Schritt „Verify DB auth if client exists“.
- [ ] **Optional: Trivy-Gate explizit festlegen.** Dokumentieren und konfigurieren, welche Schweregrade den Build abbrechen sollen, statt sich auf den Standardwert der Action zu verlassen. SARIF weiterhin hochladen, damit gefundene Schwachstellen unabhängig vom Gate sichtbar bleiben. Quelle: `.github/workflows/ci.yml` Schritt „Trivy scan“.
- [ ] **Optional: Fehlerdiagnose des E2E-Jobs verbessern.** Bei jedem fehlgeschlagenen Schritt aktuelle `docker compose ps`- und begrenzte `docker compose logs`-Ausgaben sammeln und als Artefakt bereitstellen. Dadurch werden Fehler außerhalb des API-Warteschritts ebenfalls nachvollziehbar. Quelle: `.github/workflows/ci.yml`.
