#!/bin/bash
# Test of de Apache RewriteRule (zie onderaan) elke dcat:downloadURL uit de catalog.ttl-bestanden
# correct doorvertaalt naar een werkende raw.githubusercontent.com-URL.
#
# Gebruik: ./testRewriteRule.sh
# Output:  rewrite_test_results.tsv (status<TAB>originele_url<TAB>herschreven_url) + samenvatting op stdout.
#
# RewriteRule ^/be\.vlaanderen\.omgeving\.data\.id\.distribution\.codelijst-(csor-([^\.-]+)(?:-([^\.-]+))?)\.(.*)\.[^\.]+\.([^\.]+)$ https://raw.githubusercontent.com/milieuinfo/codelijst-$1/codelijst-$1-$4/src/main/resources/be/vlaanderen/omgeving/data/id/conceptscheme/csor/$2$3/$2$3.$5 [L,R]

set -euo pipefail
cd "$(dirname "$0")"

OUT="rewrite_test_results.tsv"

pushd ../../.. > /dev/null
downloadUrls=(`find | grep catalog.ttl$ | xargs grep dcat:downloadURL | tr ' ' '\n' | grep http | sed -e 's/<//' | sed -e 's/>.//' | grep 'distribution\.codelijst' | sort -u`)
popd > /dev/null

echo -e "status\toriginal_url\trewritten_url" > "$OUT"

for url in "${downloadUrls[@]}"; do
    path="/${url#*://*/}"

    target=$(printf '%s' "$path" | perl -pe 's#^/be\.vlaanderen\.omgeving\.data\.id\.distribution\.codelijst-(csor-([^.-]+)(?:-([^.-]+))?)\.(.*)\.[^.]+\.([^.]+)$#https://raw.githubusercontent.com/milieuinfo/codelijst-$1/codelijst-$1-$4/src/main/resources/be/vlaanderen/omgeving/data/id/conceptscheme/csor/$2$3/$2$3.$5#')

    if [ "$target" = "$path" ]; then
        echo -e "NO_MATCH\t$url\t(regex matchte niet)" >> "$OUT"
        continue
    fi

    code=$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 10 "$target")
    echo -e "$code\t$url\t$target" >> "$OUT"
done

echo
echo "=== Statusverdeling ==="
cut -f1 "$OUT" | tail -n +2 | sort | uniq -c | sort -rn
echo
echo "Volledige resultaten: $OUT"
