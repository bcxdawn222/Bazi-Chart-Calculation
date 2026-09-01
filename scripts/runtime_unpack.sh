#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
python3 "${SCRIPT_DIR}/runtime_unpack.py" --output "${ROOT_DIR}/artifacts/runtime" "$@"
