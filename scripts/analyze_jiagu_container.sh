#!/usr/bin/env bash
set -euo pipefail
python3 "$(dirname "$0")/analyze_jiagu_container.py" "$@"
