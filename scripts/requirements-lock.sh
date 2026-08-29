#!/usr/bin/env sh
set -eu

mode=${1:-check}
case "$mode" in
  check|--write) ;;
  *)
    printf '%s\n' "Usage: ./scripts/requirements-lock.sh [--write]" >&2
    exit 2
    ;;
esac

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target="$project_dir/requirements.lock"
rendered=$(mktemp "${TMPDIR:-/tmp}/size-note-requirements.XXXXXX")
trap 'rm -f -- "$rendered"' EXIT INT TERM

{
  printf '%s\n' \
    "# Generated from uv.lock and pyproject.toml." \
    "# Run ./scripts/requirements-lock.sh --write after changing dependencies."
  python3 - "$project_dir/pyproject.toml" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as source:
    project = tomllib.load(source)
for requirement in project["build-system"]["requires"]:
    print(requirement)
PY
  uv export \
    --directory "$project_dir" \
    --frozen \
    --no-dev \
    --no-emit-project \
    --no-hashes \
    --no-annotate \
    --no-header
} >"$rendered"

if [ "$mode" = "--write" ]; then
  mv -f -- "$rendered" "$target"
  trap - EXIT INT TERM
  printf 'Updated %s\n' "$target"
else
  if ! diff -u "$target" "$rendered"; then
    printf '%s\n' \
      "requirements.lock is out of date." \
      "Run ./scripts/requirements-lock.sh --write and commit the result." >&2
    exit 1
  fi
fi
