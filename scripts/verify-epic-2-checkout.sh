#!/bin/sh
# Reproduce EPIC-2 from committed files in a temporary clone, without local credentials.
set -eu

project_root=$(git rev-parse --show-toplevel)
checkout_root=$(mktemp -d "${TMPDIR:-/tmp}/epic2-checkout.XXXXXX")
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
make build
sh scripts/verify-epic-2-package.sh
git diff --exit-code HEAD
printf 'Fresh-checkout EPIC-2 setup, quality gates, demo, and installed-wheel checks passed.\n'
