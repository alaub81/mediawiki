#!/usr/bin/env bash
set -eu

: "${MW_CONFIG_FILE:=/var/www/html/LocalSettings.php}"
MW_CONFIG_FILE_PATH=$(dirname "$MW_CONFIG_FILE" 2>/dev/null || echo "/var/www/html")
if [ -n "${MW_CONFIG_FILE_PATH:-}" ]; then
  if [ ! -d "$MW_CONFIG_FILE_PATH" ]; then
    mkdir -p -- "$MW_CONFIG_FILE_PATH"
  fi
fi

cd /var/www/html
run="php maintenance/run.php"

# Determine help text once
INSTALL_HELP="$($run install --help 2>&1 || true)"

# Which flags does the installer support?
HAS_EXT=0; HAS_WITH=0
printf '%s' "$INSTALL_HELP" | grep -q -- '--extensions'       && HAS_EXT=1
printf '%s' "$INSTALL_HELP" | grep -q -- '--with-extensions'  && HAS_WITH=1

# Space → CSV from MW_ACTIVE_EXTENSIONS
EXT_CSV=""
if [ -n "${MW_ACTIVE_EXTENSIONS:-}" ]; then
  set -f
  for e in $MW_ACTIVE_EXTENSIONS; do
    if [ -z "$EXT_CSV" ]; then EXT_CSV="$e"; else EXT_CSV="$EXT_CSV,$e"; fi
  done
  set +f
fi

# Which flag to use?
EXT_FLAG=""
if [ -z "$EXT_CSV" ]; then
  if [ $HAS_WITH -eq 1 ]; then
    EXT_FLAG="--with-extensions"
  else
    echo "[install] Hinweis: --with-extensions nicht verfügbar; keine Extensions per Installer geladen." >&2
  fi
else
  if [ $HAS_EXT -eq 1 ]; then
    EXT_FLAG="--extensions $EXT_CSV"
  elif [ $HAS_WITH -eq 1 ]; then
    echo "[install] Hinweis: --extensions fehlt; benutze --with-extensions und ignoriere Liste." >&2
    EXT_FLAG="--with-extensions"
  else
    echo "[install] Hinweis: Weder --extensions noch --with-extensions verfügbar; lade Extensions nachträglich." >&2
  fi
fi

if [ -f "${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}" ]; then
  echo "${MW_CONFIG_FILE} exists → updating configuration"
else
  echo "No ${MW_CONFIG_FILE} → running install.php"

  # DB port accessible? (failsafe in addition to previous DB wait)
  end=$((SECONDS+120))
  until php -r "exit(@fsockopen(getenv(\"MW_DB_HOST\")?: \"database\", (int)(getenv(\"MW_DB_PORT\")?:3306))?0:1);"; do
    [ $SECONDS -ge $end ] && { echo "DB not reachable"; exit 1; }
    sleep 2
  done
  echo ${EXT_FLAG:+$EXT_FLAG}
  # Installation
  $run install \
    --confpath "${MW_CONFIG_FILE_PATH}" \
    --dbtype mysql \
    --dbserver  "${MW_DB_HOST:-database}:${MW_DB_PORT:-3306}" \
    --dbname    "${MW_DB_NAME:-wikidb}" \
    --dbuser    "${MW_DB_USER:-wikiuser}" \
    --dbpass    "${MW_DB_PASS:-w1k1pass}" \
    --installdbuser "${MW_DB_ADMIN_USER:-root}" \
    --installdbpass "${MARIADB_ROOT_PASSWORD:-ciRootPassw0rd}" \
    --lang      "${MW_LANG:-de}" \
    --server    "${MW_SERVER_URL:-http://localhost:8080}" \
    --scriptpath "" \
    --pass      "${MW_ADMIN_PASS:-AdminPass123}" \
    ${EXT_FLAG:+$EXT_FLAG} \
    "${MW_SITENAME:-Wiki CI}" \
    "${MW_ADMIN_USER:-Admin}"
fi

# $wgServer, $wgScriptPath and $wgArticlePath in LocalSettings.php set/place
# read LocalSettings.php
f="${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}"
  [ -f "$f" ] || { echo "Config file $f not found"; exit 1; }

# Keep the generated site name and project namespace tied to the runtime values.
want_site="\$wgSitename = getenv('MW_SITENAME') ?: \"My Own Wiki\";"
want_meta="\$wgMetaNamespace = getenv('MW_METANAMESPACE') ?: \"My_Own_Wiki\";"
tmp="$(mktemp)"
awk -v site="$want_site" -v meta="$want_meta" '
  BEGIN { found_site=0; found_meta=0 }
  /^\$wgSitename[[:space:]]*=/ { print site; found_site=1; next }
  /^\$wgMetaNamespace[[:space:]]*=/ { print meta; found_meta=1; next }
  { print }
  END {
    if (!found_site) print site
    if (!found_meta) print meta
  }
' "$f" > "$tmp" && mv "$tmp" "$f"

# Target line (exactly as shown, without quotes around the expression)
want="\$wgServer = getenv('MW_SERVER_URL') ?: 'http://localhost:8080';"

if [ -f "$f" ]; then
  tmp="$(mktemp)"
  awk -v repl="$want" '
    BEGIN{done=0}
    # Replace the existing $wgServer assignment
    /^\$wgServer[[:space:]]*=/ { print repl; done=1; next }
    { print }
    END{
      # Append the assignment if none was found
      if(!done) print "\n" repl
    }
  ' "$f" > "$tmp" && mv "$tmp" "$f"
fi

# $wgScriptPath = "";
if grep -q "^\$wgScriptPath" "$f"; then
  sed -i "s#^\$wgScriptPath[[:space:]]*=.*#\$wgScriptPath = \"\";#" "$f"
else
  if grep -q '^?>' "$f"; then
    sed -i "s#^?>#\$wgScriptPath = \"\";\\n?>#" "$f"
  else
    printf "\n\$wgScriptPath = "";\n" >> "$f"
  fi
fi

# Load Elastica/Cirrus securely (only if not already present)
if ! grep -Fq "wfLoadExtension( 'Elastica' );" "$f"; then
  printf "%s\n" "wfLoadExtension( 'Elastica' );" >> "$f"
fi
if ! grep -Fq "wfLoadExtension( 'CirrusSearch' );" "$f"; then
  printf "%s\n" "wfLoadExtension( 'CirrusSearch' );" >> "$f"
fi

# Enable uploads
sed -i "s#^\$wgEnableUploads[[:space:]]*=.*#\$wgEnableUploads = true;#" "$f"

# Append the custom LocalSettings block only once. Existing configurations may
# already contain the older, unmarked version of this block.
if grep -Fq '# --- mw-default-setup custom settings BEGIN ---' "$f" || \
   grep -Fq 'function HeadScript(' "$f"; then
  echo "[LocalSettings] Custom configuration already present; skipping append."
else
cat >>"$f" <<'PHP'
# --- mw-default-setup custom settings BEGIN ---
# End of automatically generated settings.
# Add more configuration options below.
# ShortUrls settings
$actions = [
	'edit',
	'watch',
	'unwatch',
	'delete',
	'revert',
	'rollback',
	'protect',
	'unprotect',
	'markpatrolled',
	'render',
	'submit',
	'history',
	'purge',
	'info',
];

foreach ( $actions as $action ) {
  $wgActionPaths[$action] = "/wiki/$action/$1";
}
$wgActionPaths['view'] = "/wiki/$1";
$wgArticlePath = "/wiki/$1";
# --- ShortUrls settings (auto) END ---

# Output <link rel="canonical"> on every page
$wgEnableCanonicalServerLink = true;

# --- CirrusSearch settings (auto) BEGIN ---
$wgSearchType = 'CirrusSearch';
$wgCirrusSearchServers = [ 'opensearch' ];
$wgCirrusSearchUseCompletionSuggester = true;

# Related Articles using CirrusSearch
$wgRelatedArticlesDescriptionSource = 'pagedescription';
$wgRelatedArticlesUseCirrusSearchApiUrl = '/api.php';
$wgRelatedArticlesUseCirrusSearch = true;
$wgRelatedArticlesCardLimit = 6;

# Searchable namespaces
$wgNamespacesToBeSearchedDefault = [
	NS_MAIN => true,
	NS_PROJECT => true,
	NS_FILE => true,
	NS_HELP => true,
	NS_CATEGORY => true,
];

# TopTenPages Configuration
$wgTopTenPagesStartAtOne = true;

# Apple Touch Icon
$wgAppleTouchIcon = "/favicon/apple-touch-icon.png";

# Favicon
$wgFavicon = "/favicon/favicon.ico";

$wgHeadScriptCode = <<<'START_END_MARKER'
<!-- Favicons -->
<link rel="icon" type="image/png" href="/favicon/favicon-96x96.png" sizes="96x96" />
<link rel="icon" type="image/png" href="/favicon/favicon-32x32.png" sizes="32x32" />
<link rel="icon" type="image/png" href="/favicon/favicon-16x16.png" sizes="16x16" />
<link rel="icon" type="image/svg+xml" href="/favicon/favicon.svg" />
<link rel="shortcut icon" href="/favicon/favicon.ico" />
<!-- Apple Touch -->
<link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon.png" />
<meta name="apple-mobile-web-app-title" content="LHlab" />
<!-- PWA manifest (it can also live at the root if it remains accessible) -->
<link rel="manifest" href="/favicon/site.webmanifest" />
START_END_MARKER;
$wgHeadScriptName = 'Favicon Stuff';

$wgHooks['BeforePageDisplay'][] = 'HeadScript';
function HeadScript( OutputPage &$out, Skin &$skin ) {
        global $wgHeadScriptCode, $wgHeadScriptName;
        $out->addHeadItem($wgHeadScriptName, $wgHeadScriptCode );
        return TRUE;
}

# IPv6 Ready badge: remove the /* and */ lines below to enable it.
/*
$wgFooterIcons['poweredby-ipv6'] = [
  'ipv6ready' => [
  // Local Image
  // "src" => "$wgResourceBasePath/images/button-ipv6-small.png",
  // Remote Image
  "src" => "https://ipv6-test.com/button-ipv6-small.png",
  "url" => "https://ipv6-test.com/validate.php?url=referer",
  "alt" => "ipv6 ready",
  "height" => "31",
  "width" => "88",
  ]
];
*/

# Allow to overwrite the article title
$wgAllowDisplayTitle = true;
$wgRestrictDisplayTitle = false;

# Antivirus integration (ClamAV)
$clamavEnabled = filter_var(getenv('CLAMAV_ENABLED') ?: 'false', FILTER_VALIDATE_BOOLEAN);
if ($clamavEnabled) {
    $wgAntivirus = 'clamav';
    $wgAntivirusRequired = true;
    $wgAntivirusSetup['clamav'] = [
        'command' => '/usr/bin/clamdscan --no-summary --stdout --config-file=/etc/clamav/clamd.remote.conf %f',
        'codemap' => [
            0 => AV_NO_VIRUS,
            1 => AV_VIRUS_FOUND,
            2 => AV_SCAN_FAILED,
            '*' => AV_SCAN_FAILED,
        ],
    ];
} else {
    $wgAntivirus = false;
}

# File Upload Restriction
$wgCheckFileExtensions = true;
$wgStrictFileExtensions = true;
$wgVerifyMimeType = true;
$wgFileExtensions = array_values( array_unique( array_merge(
	$wgFileExtensions,
	[
		// Documents and plain-text data
		'pdf', 'txt', 'md', 'csv', 'tsv', 'rtf',

		// Microsoft Office
		'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',

		// OpenDocument
		'odt', 'ods', 'odp', 'odg',

		// Additional raster image formats
		'bmp', 'tif', 'tiff', 'ico',

		// Audio
		'mp3', 'ogg', 'oga', 'opus', 'wav', 'flac', 'm4a',

		// Video
		'webm', 'mp4', 'm4v', 'mov', 'ogv',

		// Archives
		'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'tgz',
	]
) ) );

# Enable Wanda only when its optional Elasticsearch service is enabled.
$wandaEnabled = filter_var( getenv( 'MW_WANDA_ENABLED' ) ?: 'false', FILTER_VALIDATE_BOOLEAN );

if ( $wandaEnabled ) {
	wfLoadExtension( 'Wanda' );
	wfLoadExtension( 'WandaScore' );

	// OpenAI provider configuration.
	$wgWandaLLMProvider = 'openai';
	$wgWandaLLMApiKey = 'REPLACE_WITH_YOUR_OPENAI_API_KEY';
	$wgWandaLLMModel = 'gpt-5.2';
	$wgWandaLLMEmbeddingModel = 'text-embedding-3-small';
	$wgWandaLLMApiEndpoint = 'https://api.openai.com/v1';

	// Dedicated Elasticsearch service used only by Wanda.
	$wgWandaLLMElasticsearchUrl =
		getenv( 'MW_ELASTICSEARCH_URL' ) ?: 'http://elasticsearch:9200';

	// Interface and feature settings.
	$wgWandaShowPopup = true;
	$wgWandaEnableAttachments = false;
	$wgWandaEnableEditing = false;

	// Keep answers grounded in readable wiki content.
	$wgWandaDisabledSources = [
		'wikidata',
		'publicknowledge',
		'cargo',
		'smw',
		'externalwiki',
	];

	$wgWandaAllowedNamespaces = [
		NS_MAIN,
		NS_PROJECT,
		NS_FILE,
		NS_HELP,
		NS_CATEGORY,
	];

	# The custom prompt handles the response language dynamically.
	$wgWandaUseContentLang = false;

	# LLM and retrieval behavior.
	$wgWandaLLMMaxTokens = 4096;
	$wgWandaLLMTemperature = '0.2';
	$wgWandaLLMTimeout = 90;
	$wgWandaMaxContextChars = 24000;
	$wgWandaConversationMaxChars = 10000;
	$wgWandaVectorSearchMinScore = 1.55;

	# Use incremental hooks and run the initial full reindex manually.
	$wgWandaAutoReindex = false;
	$wgWandaMaxImageSize = 5242880;
	$wgWandaMaxImageCount = 3;

	# Ground Wanda's answers in the retrieved wiki content.
	$wgWandaCustomPrompt = <<<PROMPT
You are the knowledge assistant for {$wgSitename}.

Answer the user's question using only the supplied wiki context.

Rules:
- Give precise, complete, and clearly structured answers.
- Combine relevant information from multiple wiki pages when necessary.
- Do not invent facts that are not supported by the supplied context.
- If the available context is incomplete, ambiguous, or contradictory, state this clearly.
- Mention the relevant wiki page titles whenever they can be identified from the context.
- Preserve important technical names, version numbers, commands, paths, and warnings.
- Distinguish verified facts from conclusions or interpretations.
- Answer in the language used by the user.
- Do not expose raw wikitext.
- Do not suggest database queries or internal maintenance commands to ordinary users.
- Do not claim that information comes from {$wgSitename} unless it is present in the supplied context.
- If the supplied context does not contain enough information, say so directly instead of guessing.
PROMPT;

	$wgWandaCustomPromptTitle = '';
}
unset( $wandaEnabled );

# ReadOnly Mode
#$wgReadOnly = "<h1><b>This is a mirror. Please edit at www.example.com</b></h1><br>";
#$wgReadOnly = "<h1><b>Update Ongoing</b></h1><br>";
#$wgReadOnly = "<h1><b>Migration Ongoing</b></h1><br>";

## Debugging settings (set MW_DEBUG in the container environment).
$mwDebug = filter_var( getenv( 'MW_DEBUG' ) ?: 'false', FILTER_VALIDATE_BOOLEAN );
# Show stack traces for uncaught exceptions in the page output.
$wgShowExceptionDetails = $mwDebug;
# Show debug messages at the bottom of the page.
$wgShowDebug = $mwDebug;
# Emit warnings for deprecated features and development issues.
$wgDevelopmentWarnings = $mwDebug;
# Limit deprecation warnings to the specified MediaWiki release.
$wgDeprecationReleaseLimit = getenv( 'MW_DEPRECATION_RELEASE_LIMIT' ) ?: false;
# Disable PHP error reporting at runtime.
# error_reporting(0);
# --- mw-default-setup custom settings END ---
PHP
fi

# Load extension schema changes after the configuration has been written.
$run update
echo "[LocalSettings] LocalSettings-Konfiguration wurde in $f aktualisiert."
echo "[install] Installation/Update done."
