#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
python3 "${SCRIPT_DIR}/recover_sources.py" --output "${ROOT_DIR}/artifacts/recovered" "$@"
