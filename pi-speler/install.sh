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

if ! "${SUDO[@]}" apt-get update \
  || ! "${SUDO[@]}" apt-get install -y python3-gpiozero alsa-utils pulseaudio-utils; then
  echo "pi-speler: pakketten niet bijgewerkt. Bestaande python3, gpiozero en aplay blijven gelden." >&2
fi

# lgpio: gpiozero heeft dit nodig op Trixie (geen /sys/class/gpio meer).
# python3-rpi-lgpio alleen als python3-lgpio niet bestaat.
if ! /usr/bin/python3 -c "import lgpio" 2>/dev/null; then
  if ! "${SUDO[@]}" apt-get install -y python3-lgpio; then
    if apt-cache show python3-rpi-lgpio >/dev/null 2>&1; then
      "${SUDO[@]}" apt-get install -y python3-rpi-lgpio \
        || echo "pi-speler: python3-rpi-lgpio niet geïnstalleerd." >&2
    else
      echo "pi-speler: python3-lgpio niet geïnstalleerd. Knoppen werken dan niet op Trixie." >&2
    fi
  fi
fi

chmod +x "$ROOT/start.sh"

boot_audio=""
if [[ -d /boot/firmware ]]; then
  boot_audio=/boot/firmware/audio
elif [[ -f /boot/cmdline.txt ]]; then
  boot_audio=/boot/audio
fi
if [[ -n "$boot_audio" ]]; then
  "${SUDO[@]}" mkdir -p "$boot_audio"
  for wav in "$ROOT"/audio/*.wav; do
    [[ -f "$wav" ]] || continue
    name="$(basename "$wav")"
    if [[ ! -f "$boot_audio/$name" ]]; then
      "${SUDO[@]}" cp "$wav" "$boot_audio/$name"
    fi
  done
fi

"${SUDO[@]}" mkdir -p /mnt/pi-speler /var/lib/pi-speler
if [[ -f /etc/fstab ]] && ! grep -q '/mnt/pi-speler' /etc/fstab; then
  printf '%s\n' 'LABEL=AUDIO  /mnt/pi-speler  auto  defaults,nofail,x-systemd.device-timeout=5,noatime  0  0' \
    | "${SUDO[@]}" tee -a /etc/fstab >/dev/null
fi

# Wifi, gebruiker en ssh: alleen als zet-klaar.sh --wifi de map toegang maakte.
if [[ -d "$ROOT/toegang" ]]; then
  if ! "${SUDO[@]}" bash "$ROOT/toegang.sh" "$ROOT/toegang"; then
    echo "pi-speler: toegang niet helemaal gezet" >&2
  fi
fi

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
