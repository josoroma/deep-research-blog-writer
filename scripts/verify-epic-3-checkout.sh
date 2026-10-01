#!/bin/sh
# Reproduce EPIC-3 from committed files in a temporary clone, without local credentials.
set -eu

project_root=$(git rev-parse --show-toplevel)
checkout_root=$(mktemp -d "${TMPDIR:-/tmp}/epic3-checkout.XXXXXX")
trap 'rm -rf "$checkout_root"' EXIT HUP INT TERM

git clone --local --no-hardlinks --quiet "$project_root" "$checkout_root/project"
cd "$checkout_root/project"
printf 'Verifying committed revision: '
git rev-parse HEAD
test ! -f .env
make setup
make check
make hooks
make demo-epic-2
make demo-epic-3
make build
sh scripts/verify-epic-3-package.sh
git diff --exit-code HEAD
printf 'Fresh-checkout EPIC-3 setup, quality gates, demos, and installed-wheel checks passed.\n'
