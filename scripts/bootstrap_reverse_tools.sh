#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
python3 "${SCRIPT_DIR}/bootstrap_reverse_tools.py" --root "${ROOT_DIR}/.tools/reverse" --log "${ROOT_DIR}/logs/bootstrap-reverse-tools.log" "$@"
