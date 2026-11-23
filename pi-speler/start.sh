#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Start de speler. Ontbrekende pakketten worden één keer geïnstalleerd
# als de Pi netwerk heeft. Zonder netwerk blijven gpiozero en aplay,
# als die al op de image staan, gewoon werken.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! /usr/bin/python3 -c "import gpiozero" 2>/dev/null || ! command -v aplay >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  /usr/bin/apt-get update
  /usr/bin/apt-get install -y python3-gpiozero alsa-utils
fi

# lgpio voor de knoppen. Mislukt het, dan start de speler toch (opstartreeks, led).
if ! /usr/bin/python3 -c "import lgpio" 2>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  /usr/bin/apt-get install -y python3-lgpio \
    || echo "pi-speler: python3-lgpio ontbreekt, knoppen werken niet" >&2
fi

exec /usr/bin/python3 -u "$ROOT/pi_speler.py"
