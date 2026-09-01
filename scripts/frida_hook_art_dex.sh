#!/usr/bin/env bash
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="${1:?output directory required}"
shift
exec py -3.13 "$ROOT/scripts/frida_hook_art_dex.py" --package yiqi.bazi --output "$OUT" "$@"
