#!/bin/sh
set -eu
python "$(dirname "$0")/capture_devtools.py" "$@"
