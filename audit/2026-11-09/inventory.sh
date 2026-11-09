#!/usr/bin/env bash
# REQUISITO PREVIO: enumerar TODA la org y clonar TODOS los repos accesibles.
# Idempotente: si el repo ya existe, no lo vuelve a clonar.
#
#   ORG=bifrost-platform DEST=/home/user/audit/repos ./inventory.sh
#
# Requiere `gh` autenticado (o un token en GH_TOKEN).
set -uo pipefail

ORG="${ORG:-bifrost-platform}"
DEST="${DEST:-/home/user/audit/repos}"
mkdir -p "$DEST"

echo "## enumeracion (API paginada: el default de 30/100 enmascara repos)"
gh api "orgs/$ORG/repos?per_page=100" --paginate \
  --jq '.[] | [.name, .private, .archived, (.language // "-"), .pushed_at] | @tsv' \
  | sort > "$DEST/.repos.tsv"
awk -F'\t' '{p[$2]++} END {printf "total=%d privados=%d\n", NR, p["true"]+0}' "$DEST/.repos.tsv"
cat "$DEST/.repos.tsv"

echo
echo "## privados visibles con este token"
gh api "orgs/$ORG/repos?type=private&per_page=100" --paginate --jq 'length' || true

echo
echo "## clonado (--depth 1 + submodulos)"
while IFS=$'\t' read -r name _private _archived _lang _pushed; do
  [ -d "$DEST/$name/.git" ] && continue
  echo "-> $name"
  git clone -q --depth 1 "https://github.com/$ORG/$name" "$DEST/$name" \
    && (cd "$DEST/$name" && git submodule update --init --depth 1 -q 2>/dev/null || true)
done < "$DEST/.repos.tsv"

echo
echo "## inventario de commits (HEAD de cada clon)"
while IFS=$'\t' read -r name _rest; do
  head=$(git -C "$DEST/$name" rev-parse --short HEAD 2>/dev/null || echo "NO-CLONADO")
  printf "%-34s %s\n" "$name" "$head"
done < "$DEST/.repos.tsv"

echo
echo "## artefactos del despliegue presentes en los clones"
grep -rlis --include='*.json' -e 'd551f33ca8ecb0be83d8799d9c68a368ba36dd52' \
  -e 'd85eb87cab9041ad00764b95796702b1104f42d7' "$DEST" 2>/dev/null | head
echo "(si no aparece ningun .sol/.bin/bytecode, el codigo de los contratos"
echo " desplegados NO esta en los repos: ver seccion de cobertura del informe)"
