#!/usr/bin/env sh
set -eu
python "$(dirname "$0")/scan_android_memory.py" "$@"
