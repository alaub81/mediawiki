#!/bin/sh
set -eu

cd /var/www/html
required=$(php -r 'echo json_decode(file_get_contents("composer.json"), true, 512, JSON_THROW_ON_ERROR)["require"]["wikimedia/parsoid"];')
installed=$(php -r 'require "vendor/autoload.php"; echo Composer\InstalledVersions::getPrettyVersion("wikimedia/parsoid");')
if [ "$required" != "0.23.3" ] || [ "${installed#v}" != "0.23.2" ]; then
    exit 0
fi

# The affected tarball already ships every runtime change from this vendor commit.
# Only update Composer's records once the code matches those files byte for byte.
cd vendor
sha256sum -c <<'SUMS'
46511c85432e584ba5ca58ce8329b7c2c3bdad0993964eca2f18cf1d3af266b5  wikimedia/parsoid/src/Core/Sanitizer.php
7260b878db7bd4b135bee04cc88a977ae4f17c8a944e13e113893d7a07cea784  wikimedia/parsoid/src/Wt2Html/DOM/Handlers/TableFixups.php
b52be2dcfdd15f50f1585bddf430b007f4b3242dd84e95d671c9f48d674f4945  wikimedia/parsoid/src/Wt2Html/TT/AttributeExpander.php
SUMS

# composer.json and composer.lock here belong to Wikimedia's vendor distribution.
git apply /tmp/parsoid-vendor-metadata.patch
