#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Start de speler. Installeert niets: pakketten horen bij install.sh.
# Ontbreekt iets, dan zegt de log het en loopt de speler toch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# lgpio maakt pijpjes (.lgd-nfy*) in de werkmap. Niet op de FAT-schijf.
export LG_WD="${LG_WD:-/run/pi-speler}"
mkdir -p "$LG_WD" 2>/dev/null || true
if ! cd "$LG_WD" 2>/dev/null; then
  export LG_WD=/tmp
  cd /tmp
fi

if ! /usr/bin/python3 -c "import gpiozero" 2>/dev/null; then
  echo "pi-speler: gpiozero ontbreekt. Draai: sudo bash $ROOT/install.sh" >&2
fi
if ! command -v aplay >/dev/null 2>&1; then
  echo "pi-speler: aplay ontbreekt. Draai: sudo bash $ROOT/install.sh" >&2
fi

exec /usr/bin/python3 -u "$ROOT/pi_speler.py"
