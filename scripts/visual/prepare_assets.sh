#!/usr/bin/env sh
set -eu
python "$(dirname "$0")/prepare_assets.py" "$@"
