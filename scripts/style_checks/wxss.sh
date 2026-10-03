#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."
python scripts/style_checks/wxss.py "$@"
