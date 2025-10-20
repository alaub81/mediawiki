#!/usr/bin/env bash
# helper script to get commit hash
set -euo pipefail

MW_SPECIAL_EXTENSIONS="WikiCategoryTagCloud CookieConsent"
BRANCH="master"  # oder master, wenn du das willst

for special in $MW_SPECIAL_EXTENSIONS; do
  url="https://gerrit.wikimedia.org/r/mediawiki/extensions/$special";
  REF=$(git ls-remote "$url" "refs/heads/$BRANCH" | awk '{print $1}')
  echo "$special last Commit is: $REF"
done;

# RottenLinks
url="https://github.com/miraheze/RottenLinks.git";
REF=$(git ls-remote "$url" "refs/heads/main" | awk '{print $1}')
echo "RottenLinks last Commit is: $REF"
