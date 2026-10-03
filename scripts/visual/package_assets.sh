#!/usr/bin/env sh
set -eu
python "$(dirname "$0")/package_assets.py" "$@"
