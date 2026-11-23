#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Zet de speler en de fragmenten op een SD-kaart met Raspberry Pi OS.
# Wist de kaart niet.
#
# Alleen de schijf die Windows en de Mac zien (bootfs):
#   ./zet-klaar.sh --boot /pad/naar/bootfs
# De Pi installeert zichzelf bij de volgende start en start daarna opnieuw.
#
# Linux, met ook de tweede partitie:
#   ./zet-klaar.sh --boot /mnt/boot --root /mnt/root
# Dan staat de service meteen aan, zonder cmdline.txt te wijzigen.
set -euo pipefail

BOOT=""
ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --boot)
      BOOT="${2:-}"
      shift 2
      ;;
    --root)
      ROOT="${2:-}"
      shift 2
      ;;
    *)
      echo "gebruik: $0 --boot MAP [--root MAP]" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$BOOT" || ! -d "$BOOT" ]]; then
  echo "geef de boot-map, bijvoorbeeld --boot /Volumes/bootfs" >&2
  exit 1
fi
if [[ ! -f "$BOOT/config.txt" || ! -f "$BOOT/cmdline.txt" ]]; then
  echo "dit is geen Raspberry Pi boot-map: config.txt of cmdline.txt ontbreekt" >&2
  exit 1
fi

# Lege regels tellen niet. Op een Mac eindigt cmdline.txt soms op een extra lege regel.
cmdline_lines=()
while IFS= read -r row || [[ -n "$row" ]]; do
  trimmed="${row#"${row%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  trimmed="${trimmed//$'\r'/}"
  [[ -z "$trimmed" ]] && continue
  cmdline_lines+=("$trimmed")
done < "$BOOT/cmdline.txt"
cmdline_count="${#cmdline_lines[@]}"

# Bookworm en nieuwer hangen deze schijf op /boot/firmware. Oudere images op /boot.
pi_prefix=/boot
if grep -q 'auto_initramfs=1' "$BOOT/config.txt"; then
  pi_prefix=/boot/firmware
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/.." && pwd)"

mkdir -p "$BOOT/audio" "$BOOT/pi-speler"
for name in a-nederlands a-frans a-engels b-nederlands b-frans b-engels; do
  dest="$BOOT/audio/$name.wav"
  if [[ -f "$dest" ]]; then
    echo "laat staan: audio/$name.wav"
  else
    cp "$SRC/audio/$name.wav" "$dest"
  fi
done
cp "$SRC/audio/LEESMIJ.txt" "$BOOT/audio/LEESMIJ.txt"
cp "$HERE/AUDIO-LEESMIJ.txt" "$BOOT/AUDIO-LEESMIJ.txt"

for file in config.py mapping.py playback.py led.py pi_speler.py install.sh start.sh pi-speler.service; do
  cp "$SRC/$file" "$BOOT/pi-speler/$file"
done
cp "$HERE/eenmalig.sh" "$BOOT/pi-speler/eenmalig.sh"
chmod +x "$BOOT/pi-speler/install.sh" "$BOOT/pi-speler/start.sh" "$BOOT/pi-speler/eenmalig.sh" || true

if [[ -n "$ROOT" ]]; then
  if [[ ! -f "$ROOT/etc/os-release" || ! -d "$ROOT/etc/systemd/system" ]]; then
    echo "de root-map is geen Linux-systeem van de Pi" >&2
    exit 1
  fi
  opt="$ROOT/opt/pi-speler"
  mkdir -p "$opt/audio" "$ROOT/mnt/pi-speler" "$ROOT/etc/systemd/system/multi-user.target.wants"
  for file in config.py mapping.py playback.py led.py pi_speler.py install.sh start.sh; do
    cp "$SRC/$file" "$opt/$file"
  done
  chmod +x "$opt/install.sh" "$opt/start.sh"
  for name in a-nederlands a-frans a-engels b-nederlands b-frans b-engels; do
    if [[ ! -f "$opt/audio/$name.wav" ]]; then
      cp "$SRC/audio/$name.wav" "$opt/audio/$name.wav"
    fi
  done
  content="$(<"$SRC/pi-speler.service")"
  content="${content//@DIR@//opt/pi-speler}"
  printf '%s\n' "$content" >"$ROOT/etc/systemd/system/pi-speler.service"
  ln -sfn /etc/systemd/system/pi-speler.service \
    "$ROOT/etc/systemd/system/multi-user.target.wants/pi-speler.service"
  if [[ -f "$ROOT/etc/fstab" ]] && ! grep -q '/mnt/pi-speler' "$ROOT/etc/fstab"; then
    printf '%s\n' 'LABEL=AUDIO  /mnt/pi-speler  auto  defaults,nofail,x-systemd.device-timeout=5,noatime  0  0' \
      >>"$ROOT/etc/fstab"
  fi
  if grep -q 'pi-speler/eenmalig.sh' "$BOOT/cmdline.txt"; then
    backup="$BOOT/cmdline.txt.pi-speler-backup"
    if [[ -f "$backup" ]] && ! grep -q 'systemd.run=' "$backup"; then
      cp "$backup" "$BOOT/cmdline.txt"
    else
      sed -i \
        -e 's| systemd.run=/boot/firmware/pi-speler/eenmalig.sh||g' \
        -e 's| systemd.run_success_action=reboot||g' \
        -e 's| systemd.unit=kernel-command-line.target||g' \
        "$BOOT/cmdline.txt"
    fi
    echo "Eenmalige startregel uit cmdline.txt gehaald. De service staat al op de Linux-partitie."
  else
    echo "Service staat klaar op de Linux-partitie. cmdline.txt is niet gewijzigd."
  fi
  exit 0
fi

if [[ "$cmdline_count" -eq 0 ]]; then
  echo "De fragmenten staan in $BOOT/audio. cmdline.txt is leeg, die heb ik niet aangeraakt." >&2
  exit 1
fi

if grep -q 'systemd.run=' "$BOOT/cmdline.txt"; then
  echo "cmdline.txt heeft al een startscript. Die regel blijft staan."
  if [[ -f "$BOOT/firstrun.sh" ]] && ! grep -q 'pi-speler/install.sh' "$BOOT/firstrun.sh"; then
    printf '\nbash %s/pi-speler/install.sh\n' "$pi_prefix" >>"$BOOT/firstrun.sh"
    echo "installatie toegevoegd aan firstrun.sh"
  fi
  exit 0
fi

# De Pi leest alleen de eerste regel. Staat root= pas op een latere regel,
# dan horen die regels bij elkaar en maken we er weer één regel van.
first="${cmdline_lines[0]}"
keep_rest=1
if [[ "$first" != *root=* && "$cmdline_count" -gt 1 ]]; then
  i=1
  while [[ "$i" -lt "$cmdline_count" ]]; do
    first="$first ${cmdline_lines[$i]}"
    i=$((i + 1))
  done
  keep_rest=0
fi

backup="$BOOT/cmdline.txt.pi-speler-backup"
if [[ ! -f "$backup" ]]; then
  cp "$BOOT/cmdline.txt" "$backup"
fi
{
  printf '%s\n' "${first} systemd.run=${pi_prefix}/pi-speler/eenmalig.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
  if [[ "$keep_rest" -eq 1 && "$cmdline_count" -gt 1 ]]; then
    i=1
    while [[ "$i" -lt "$cmdline_count" ]]; do
      printf '%s\n' "${cmdline_lines[$i]}"
      i=$((i + 1))
    done
  fi
} >"$BOOT/cmdline.txt"
echo "Klaar. Zet de kaart in de Pi. Die installeert zichzelf en start één keer opnieuw."
echo "Komt hij niet terug, zet cmdline.txt.pi-speler-backup terug als cmdline.txt."
