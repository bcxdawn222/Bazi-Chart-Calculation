#!/usr/bin/env bash
set -euo pipefail

python3 "$(dirname "$0")/frida_dump_dex.py" "$@"
