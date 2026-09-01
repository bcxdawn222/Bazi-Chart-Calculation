#!/usr/bin/env sh
set -eu
python "$(dirname "$0")/analyze_native_x86_64.py" "$@"
