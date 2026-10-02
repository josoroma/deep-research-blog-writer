#!/bin/sh
# Reproduce the committed EPIC-9 delivery without local secrets or untracked files.
set -eu
project_root=$(git rev-parse --show-toplevel)
checkout_root=$(mktemp -d "${TMPDIR:-/tmp}/epic9-checkout.XXXXXX")
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
make demo-epic-4
make demo-epic-5
make demo-epic-6
make demo-epic-7
make demo-epic-8
make demo-epic-9
make build
sh scripts/verify-epic-9-package.sh
git diff --exit-code HEAD
printf 'Fresh-checkout EPIC-9 setup, gates, hooks, prior demos, build and installed-wheel checks passed.\n'
