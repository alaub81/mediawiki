#!/usr/bin/env python3
"""Read-only MediaWiki extension audit (Python 3.10+, standard library only)."""

import argparse
from datetime import datetime, timezone
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


# Only narrow, content-oriented rules may produce provisional candidates.
TAGS = {
    "Cite": "ref|references",
    "Math": "math|chem|ce",
    "SyntaxHighlight": "syntaxhighlight|source",
    "ImageMap": "imagemap",
    "InputBox": "inputbox",
    "Poem": "poem",
    "TemplateData": "templatedata",
    "TemplateStyles": "templatestyles",
    "DynamicPageList": "DynamicPageList",
}
ALIASES = {"SyntaxHighlight_GeSHi": "SyntaxHighlight", "intersection": "DynamicPageList"}
EXTRA = {
    "Scribunto": r"\{\{\s*#invoke\s*:",
    "ParserFunctions": r"\{\{\s*#(?:if|ifeq|iferror|ifexpr|ifexist|expr|switch|time|timel|rel2abs|titleparts)\s*:",
    "CategoryTree": r"<\s*categorytree\b|\{\{\s*#categorytree\s*:",
    "WikiSEO": r"\{\{\s*#seo\s*:",
    "ExternalData": r"\{\{\s*#(?:get_[a-z_]+_data|external_value|for_external_table|external_table|store_external_table)\s*:",
}
HINTS = {
    "CirrusSearch": "Suchbackend und Suchkonfiguration prüfen.",
    "Elastica": "Abhängigkeit von CirrusSearch; nicht isoliert deaktivieren.",
    "VisualEditor": "Editor-Nutzung und Bearbeitungs-Tags prüfen.",
    "WikiEditor": "Editor-Einstellungen und Benutzerpräferenzen prüfen.",
    "CodeEditor": "Bearbeitung von JavaScript/CSS prüfen.",
    "AbuseFilter": "Aktive Filter und Filterprotokoll prüfen.",
    "CheckUser": "Administratives Werkzeug; seltene Nutzung ist kein Entfernungskriterium.",
    "OATHAuth": "Registrierte Zwei-Faktor-Verfahren prüfen.",
    "PdfHandler": "PDF-Dateien und Vorschau-Konfiguration prüfen.",
    "Gadgets": "MediaWiki:Gadgets-definition und Benutzerpräferenzen prüfen.",
    "Wanda": "Such-/KI-Konfiguration und externe Indizes prüfen.",
    "WandaScore": "Abhängigkeiten und Wanda-Konfiguration prüfen.",
}


class AuditError(Exception):
    """An incomplete scan must never produce removal candidates."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AuditError("API leitet um; bitte die endgültige API-URL angeben.")


class Client:
    def __init__(self, url, cookie_file=None, delay=0.1):
        parsed = urllib.parse.urlsplit(url)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise AuditError(
                "API-URL muss http(s) verwenden, ohne Zugangsdaten, Query oder Fragment."
            )
        if cookie_file and parsed.scheme != "https":
            raise AuditError("Session-Cookies werden ausschließlich über HTTPS gesendet.")
        self.url = url
        self.delay = delay
        jar = http.cookiejar.MozillaCookieJar()
        if cookie_file:
            jar.load(cookie_file, ignore_discard=True)
        # Never save cookies; refuse redirects so credentials cannot leave the endpoint.
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(jar)
        )

    def query(self, **params):
        if "action" in params:
            raise AuditError("Nur action=query ist erlaubt.")
        query = urllib.parse.urlencode(
            {
                **params,
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "maxlag": 5,
            }
        )
        request = urllib.request.Request(
            self.url + "?" + query, headers={"User-Agent": "MediaWikiExtensionAudit/1.0"}
        )
        time.sleep(self.delay)
        try:
            with self.opener.open(request, timeout=60) as response:
                data = json.load(response)
        except (urllib.error.URLError, ValueError) as error:
            raise AuditError("API nicht erreichbar oder ungültige JSON-Antwort.") from error
        if "error" in data or "errors" in data or "warnings" in data:
            raise AuditError("API meldet Fehler/Warnungen; Scan abgebrochen, keine Kandidaten.")
        return data


def batches(client, **params):
    continuation = {}
    seen = set()
    while True:
        data = client.query(**params, **continuation)
        yield data.get("query", {})
        continuation = data.get("continue")
        if not continuation:
            return
        key = json.dumps(continuation, sort_keys=True)
        if key in seen:
            raise AuditError("API wiederholt einen Fortsetzungsmarker.")
        seen.add(key)


def audit(client, full_read_access=False):
    info = client.query(meta="siteinfo", siprop="extensions|namespaces")["query"]
    extensions = sorted({entry["name"] for entry in info["extensions"]})
    namespaces = sorted(int(n) for n in info["namespaces"] if int(n) >= 0)
    rules = {
        name: re.compile(
            r"<\s*(?:" + tags + r")\b|\{\{\s*#tag\s*:\s*(?:" + tags + r")\s*[|}]", re.I
        )
        for name, tags in TAGS.items()
    }
    rules.update({name: re.compile(pattern, re.I) for name, pattern in EXTRA.items()})
    hits = {name: {"pages": 0, "examples": []} for name in rules}
    scanned = 0
    dynamic = False
    for namespace in namespaces:
        print(f"Prüfe Namensraum {namespace} …", file=sys.stderr)
        for batch in batches(client, list="allpages", apnamespace=namespace, aplimit=50):
            pages = batch["allpages"]
            if not pages:
                continue
            expected = {page["pageid"] for page in pages}
            data = client.query(
                prop="revisions",
                pageids="|".join(map(str, sorted(expected))),
                rvprop="content|contentmodel|ids",
                rvslots="*",
            )
            if data.get("continue"):
                raise AuditError("Unvollständige Revisionsantwort; keine Kandidaten.")
            revisions = data.get("query", {}).get("pages", [])
            if {page.get("pageid") for page in revisions} != expected:
                raise AuditError("Seiten fehlen in der Antwort; keine Kandidaten.")
            for page in revisions:
                revs = page.get("revisions", [])
                if not revs or not revs[0].get("slots"):
                    raise AuditError("Revision nicht lesbar; keine Kandidaten.")
                matched = set()
                for slot in revs[0]["slots"].values():
                    content = slot.get("content")
                    if not isinstance(content, str):
                        raise AuditError("Seiteninhalt verborgen/nicht lesbar; keine Kandidaten.")
                    # Scan raw source conservatively: comments and examples count as evidence.
                    # Lua and computed #tag names may generate otherwise invisible syntax.
                    dynamic |= slot.get("contentmodel") == "Scribunto"
                    dynamic |= bool(
                        re.search(r"\{\{\s*#(?:invoke\s*:|tag\s*:\s*\{)", content, re.I)
                    )
                    for name, rule in rules.items():
                        if rule.search(content):
                            matched.add(name)
                    if slot.get("contentmodel") == "Scribunto":
                        matched.add("Scribunto")
                scanned += 1
                for name in matched:
                    hits[name]["pages"] += 1
                    if len(hits[name]["examples"]) < 5:
                        hits[name]["examples"].append(page["title"])
    results = []
    for extension in extensions:
        name = ALIASES.get(extension, extension)
        evidence = hits.get(name, {"pages": 0, "examples": []})
        if evidence["pages"]:
            status = "Quelltext-Beleg"
            reason = "Syntax/Modell gefunden; kann auch Dokumentation oder unbenutzte Vorlage sein."
        elif name in TAGS and full_read_access and not dynamic:
            status = "Möglicher Kandidat"
            reason = "Keine bekannte Syntax gefunden; Abhängigkeiten und Konfiguration vor Deaktivierung prüfen."
        else:
            status = "Manuell prüfen"
            reason = HINTS.get(
                name,
                "Keine vollständige Nutzungsprüfung für diese Extension; Einstellungen, Logs und Abhängigkeiten prüfen.",
            )
            if name in TAGS:
                reason = (
                    "Keine Syntax gefunden; Kandidaten unterdrückt wegen dynamischer Inhalte."
                    if dynamic
                    else "Keine Syntax gefunden; vollständiger Lesezugriff nicht bestätigt."
                )
        results.append({"extension": extension, "status": status, "reason": reason, **evidence})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Aktuelle, API-sichtbare Revisionen aller nichtvirtuellen Namensräume und aller Slots.",
        "pages_scanned": scanned,
        "namespaces": namespaces,
        "full_read_access_asserted": full_read_access,
        "dynamic_content_detected": dynamic,
        "limitations": [
            "Keine Historie, gelöschten Seiten, Nutzungslogs, Datenbank-Einstellungen oder externen API-Clients geprüft.",
            "API-Zugriffsfilter können Seiten unbemerkt ausblenden; vollständige Sicht ist nicht automatisch beweisbar.",
            "Quelltext-Belege sind keine Aufrufstatistik. Dynamische Syntax und lokalisierte Aliase können fehlen.",
            "Kein atomarer Snapshot: Änderungen während des Laufs können das Ergebnis beeinflussen.",
            "Kandidaten sind vorläufig: Erweiterungsabhängigkeiten und Nutzung außerhalb von Seiten manuell prüfen.",
        ],
        "extensions": results,
    }


def render(report):
    lines = [
        "MediaWiki Extension-Audit",
        f"Seiten geprüft: {report['pages_scanned']}",
        report["scope"],
        "",
    ]
    for status in ("Möglicher Kandidat", "Quelltext-Beleg", "Manuell prüfen"):
        lines.append(status + ":")
        entries = [item for item in report["extensions"] if item["status"] == status]
        if not entries:
            lines.append("  Keine.")
        for item in entries:
            lines.append(f"  {item['extension']}: {item['reason']}")
            if item["pages"]:
                lines.append(
                    f"    {item['pages']} Seite(n); Beispiele: " + ", ".join(item["examples"])
                )
        lines.append("")
    lines.extend(report["limitations"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True, help="Vollständige URL zu api.php")
    parser.add_argument(
        "--cookie-file", help="Vorhandene Netscape-Cookie-Datei für ein privates Wiki (nur HTTPS)"
    )
    parser.add_argument(
        "--confirm-full-read-access",
        action="store_true",
        help="Bestätigt Sicht auf alle Namensräume/Seiten; ermöglicht vorläufige Kandidaten",
    )
    parser.add_argument("--json", action="store_true", help="JSON statt Text auf stdout")
    args = parser.parse_args()
    try:
        report = audit(Client(args.api, args.cookie_file), args.confirm_full_read_access)
    except (AuditError, OSError, KeyError, TypeError) as error:
        print(
            f"Audit abgebrochen ({type(error).__name__}). Kein vollständiger Bericht. "
            + (
                str(error)
                if isinstance(error, AuditError)
                else "API-Struktur oder lokale Eingaben prüfen."
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
