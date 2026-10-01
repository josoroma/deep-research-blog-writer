#!/bin/sh
# Install and verify the committed foundation in a clean temporary local clone.
set -eu

project_root=$(git rev-parse --show-toplevel)
checkout_root=$(mktemp -d "${TMPDIR:-/tmp}/epic1-checkout.XXXXXX")
trap 'rm -rf "$checkout_root"' EXIT HUP INT TERM

git clone --local --no-hardlinks --quiet "$project_root" "$checkout_root/project"
cd "$checkout_root/project"
printf 'Verifying committed revision: '
git rev-parse HEAD
make setup
make demo
make hooks
make build
git diff --exit-code HEAD
printf 'Fresh-checkout installation and all foundation checks passed.\n'
