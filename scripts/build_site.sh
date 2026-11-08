#!/usr/bin/env bash
# Rebuild the two pages in docs/ (served by GitHub Pages) from data/ns-cone.json.
# Run from the repository root. Regenerate ns-cone.json first if it is missing:
#   xz -dk data/ns-decls.json.xz
#   python3 -I analysis/spine.py data/ns-decls.json data/ns-cone.json
set -euo pipefail
cone=${1:-data/ns-cone.json}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

python3 -I analysis/build_explorer.py "$cone" --template analysis/atlas-template.html --out "$tmp/atlas.html"
python3 -I analysis/blueprint/build_blueprint.py "$cone" --template analysis/blueprint/template.html --out "$tmp/blueprint.html"

# The templates are page bodies (the form claude.ai artifacts take); give each a
# full document so it renders in standards mode on GitHub Pages.
for page in atlas blueprint; do
  {
    printf '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    printf '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    printf '<style>html{color-scheme:light}body{margin:0;font-size:14px;font-family:system-ui,sans-serif}img{max-width:100%%}[hidden]{display:none!important}</style>\n'
    printf '</head>\n<body>\n'
    cat "$tmp/$page.html"
    printf '\n</body>\n</html>\n'
  } > "docs/$page.html"
  echo "docs/$page.html"
done
