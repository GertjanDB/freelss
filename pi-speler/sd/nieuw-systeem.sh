#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Draait op de Mac. Wist de SD-kaart die nu als /Volumes/boot of
# /Volumes/bootfs zichtbaar is, en zet er een nieuwe Raspberry Pi OS op
# met de speler en de zes fragmenten.
#   ./nieuw-systeem.sh          alleen de speler
#   ./nieuw-systeem.sh --wifi   ook wifi van deze Mac, een gebruiker en ssh
set -euo pipefail

EXTRA=()
for arg in "$@"; do
  case "$arg" in
    --wifi) EXTRA=(--wifi) ;;
    *)
      echo "gebruik: $0 [--wifi]" >&2
      exit 1
      ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="https://downloads.raspberrypi.com/raspios_lite_arm64_latest"
WORK="$HOME/freelss-image"
MAX_BYTES=549755813888

MOUNT=""
if [[ -d /Volumes/boot && -d /Volumes/bootfs ]]; then
  echo "Er hangen twee kaarten aan (boot en bootfs). Haal de andere eruit." >&2
  exit 1
fi
if [[ -f /Volumes/boot/cmdline.txt ]]; then
  MOUNT=/Volumes/boot
elif [[ -f /Volumes/bootfs/cmdline.txt ]]; then
  MOUNT=/Volumes/bootfs
else
  echo "Steek de SD-kaart in. Ik verwacht de schijf boot of bootfs." >&2
  exit 1
fi

volinfo="$(diskutil info "$MOUNT")"
whole="$(printf '%s\n' "$volinfo" | sed -n 's/^[[:space:]]*Part of Whole:[[:space:]]*//p' | head -1 | tr -d '[:space:]')"
if [[ -z "$whole" ]]; then
  echo "Ik kan de kaart niet herkennen." >&2
  exit 1
fi
diskinfo="$(diskutil info "$whole")"
sys="$(diskutil info / | sed -n 's/^[[:space:]]*Part of Whole:[[:space:]]*//p' | head -1 | tr -d '[:space:]')"
if [[ "$whole" == "$sys" ]]; then
  echo "Dit is de schijf van de Mac. Ik stop." >&2
  exit 1
fi
if printf '%s\n' "$diskinfo" | grep -Eq 'Internal:[[:space:]]*Yes|Device Location:[[:space:]]*Internal'; then
  echo "Dit is een interne schijf. Ik stop." >&2
  exit 1
fi
bytes="$(printf '%s\n' "$diskinfo" | sed -n 's/.*(\([0-9][0-9]*\) Bytes).*/\1/p' | head -1)"
if [[ -z "$bytes" || "$bytes" -gt "$MAX_BYTES" ]]; then
  echo "Deze schijf is te groot of de grootte is onduidelijk. Ik stop." >&2
  exit 1
fi

echo "Dit wist de hele kaart /dev/$whole."
printf '%s\n' "$diskinfo" | sed -n 's/^[[:space:]]*Device \/ Media Name:[[:space:]]*//p; s/^[[:space:]]*Disk Size:[[:space:]]*//p' | head -2
echo "Daarna staat er een nieuwe Raspberry Pi OS op, met de speler en de zes fragmenten."
echo "Downloaden begint eerst. De kaart blijft tot daarna onaangeroerd."

mkdir -p "$WORK"
xzfile="$WORK/raspios.img.xz"
img="$WORK/raspios.img"
if [[ ! -f "$xzfile" ]]; then
  curl -L --fail --retry 3 -o "$xzfile.partial" "$URL"
  mv "$xzfile.partial" "$xzfile"
fi
if [[ ! -f "$img" ]]; then
  if command -v xz >/dev/null 2>&1; then
    xz -dkf "$xzfile"
  else
    python3 - "$xzfile" "$img" <<'PY'
import lzma, sys
src, dst = sys.argv[1], sys.argv[2]
with lzma.open(src) as infile, open(dst, "wb") as outfile:
    while True:
        chunk = infile.read(1024 * 1024)
        if not chunk:
            break
        outfile.write(chunk)
PY
  fi
fi
if [[ ! -f "$img" ]]; then
  echo "Het systeem-bestand ontbreekt na het uitpakken." >&2
  exit 1
fi

echo "De Mac vraagt nu je wachtwoord om de kaart te beschrijven. Dit duurt een paar minuten."
diskutil unmountDisk force "/dev/$whole"
sudo dd if="$img" of="/dev/r$whole" bs=4194304
sync
diskutil mountDisk "/dev/$whole" || true

newmount=""
i=0
while [[ "$i" -lt 24 ]]; do
  if [[ -f /Volumes/bootfs/cmdline.txt ]]; then
    newmount=/Volumes/bootfs
    break
  fi
  if [[ -f /Volumes/boot/cmdline.txt ]]; then
    newmount=/Volumes/boot
    break
  fi
  sleep 5
  diskutil mountDisk "/dev/$whole" >/dev/null 2>&1 || true
  i=$((i + 1))
done
if [[ -z "$newmount" ]]; then
  echo "Het systeem staat op de kaart. Haal hem eruit, steek hem opnieuw in, en draai dan:" >&2
  echo "  $HERE/zet-klaar.sh --boot /Volumes/bootfs ${EXTRA[*]:-}" >&2
  exit 1
fi

"$HERE/zet-klaar.sh" --boot "$newmount" ${EXTRA[@]+"${EXTRA[@]}"}
echo "Klaar. Werp de schijf uit en zet de kaart in de Pi."
echo "De eerste start duurt een minuut. De Pi start zichzelf één keer opnieuw. Daarna doet een knop het geluid."
