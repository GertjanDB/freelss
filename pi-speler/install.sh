#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Installeert pakketten en zet de service aan. Mag vaker draaien.
# Wist geen audiobestanden en haalt geen pakketten weg.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DEBIAN_FRONTEND=noninteractive

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y python3-gpiozero alsa-utils pulseaudio-utils

mkdir -p "$ROOT/audio/nl" "$ROOT/audio/fr" "$ROOT/audio/en"
"${SUDO[@]}" mkdir -p /mnt/pi-speler

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
content="$(<"$ROOT/pi-speler.service")"
content="${content//@DIR@/$ROOT}"
printf '%s\n' "$content" >"$tmp"
"${SUDO[@]}" cp "$tmp" /etc/systemd/system/pi-speler.service

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable pi-speler.service
if ! "${SUDO[@]}" systemctl restart pi-speler.service; then
  echo "pi-speler: service staat aan, herstart gaf een fout. Zie: journalctl -u pi-speler -n 50" >&2
fi

echo "Klaar. Logs: journalctl -u pi-speler -f"
