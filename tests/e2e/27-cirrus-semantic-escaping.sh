#!/usr/bin/env bash
# Exercise semantic result rendering without requiring a vector search index.
set -euo pipefail

{
    # eval.php reads commands in 1024-byte chunks; read the fixture as one script.
    printf 'eval(stream_get_contents(STDIN));\n'
    cat <<'PHP'
$helper = new \CirrusSearch\Search\TitleHelper();
$builder = new \CirrusSearch\Search\SemanticSearchResultBuilder($helper, 'passages', 'text', 'section');
$cases = [
    ['<script>alert(1)</script> & Grüße', '&lt;script&gt;alert(1)&lt;/script&gt; &amp; Grüße'],
    ['<img src=x onerror=alert(1)>', '&lt;img src=x onerror=alert(1)&gt;'],
    ['Normaler Text mit Umlauten: äöü', 'Normaler Text mit Umlauten: äöü'],
    [\CirrusSearch\Searcher::HIGHLIGHT_PRE_MARKER . 'Treffer' . \CirrusSearch\Searcher::HIGHLIGHT_POST_MARKER . ' <tag>',
     \CirrusSearch\Searcher::HIGHLIGHT_PRE . 'Treffer' . \CirrusSearch\Searcher::HIGHLIGHT_POST . ' &lt;tag&gt;']
];
foreach ($cases as [$snippet, $expected]) {
    $result = new \Elastica\Result([
        '_id' => '1', '_score' => 1.0, '_explanation' => [],
        '_source' => ['namespace' => 0, 'title' => 'Escaping regression', 'timestamp' => '2026-11-22T00:00:00Z', 'text_bytes' => 10],
        'fields' => ['text.word_count' => [2]],
        'inner_hits' => ['passages' => ['hits' => ['hits' => [['_source' => ['text' => $snippet]]]]]]
    ]);
    $actual = $builder->build($result)->getTextSnippet();
    if ($actual !== $expected) {
        fwrite(STDERR, 'Semantic snippet escaping failed: ' . var_export($actual, true) . PHP_EOL);
        exit(1);
    }
}
echo 'PASS CirrusSearch semantic snippets: HTML escaped, text and highlights preserved', PHP_EOL;
PHP
} | docker compose exec -T mediawiki php maintenance/run.php eval
