#!/usr/bin/env bash
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
exec py -3.13 "$ROOT/scripts/report_base_runtime_sources.py" "$@"
