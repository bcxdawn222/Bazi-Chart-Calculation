#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
python3 "${SCRIPT_DIR}/analyze_apks.py" "$@" --output "${ROOT_DIR}/reports/apk-analysis.json" --log "${ROOT_DIR}/logs/apk-analysis.log"
