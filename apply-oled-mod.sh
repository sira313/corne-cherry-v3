#!/usr/bin/env bash
# Re-apply the strata OLED display mod after a fresh west checkout/update
# usage: ./apply-oled-mod.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/app/app"
PATCH="$ROOT/patches/oled-strata.patch"

if git -C "$APP" apply --reverse --check "$PATCH" 2>/dev/null; then
  echo "OLED strata mod already applied."
  exit 0
fi

git -C "$APP" am --3way "$PATCH"
echo "OLED strata mod applied. Now run: ./build.sh all"
