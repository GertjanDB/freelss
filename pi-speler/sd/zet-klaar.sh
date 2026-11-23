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
#
# Met --wifi (op de Mac): wifi van deze Mac, een gebruiker, ssh en de naam
# pi-speler, zodat ssh gebruiker@pi-speler.local werkt. Vraagt alles zelf.
#   ./zet-klaar.sh --boot /Volumes/bootfs --wifi
set -euo pipefail

BOOT=""
ROOT=""
WIFI=0
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
    --wifi)
      WIFI=1
      shift
      ;;
    *)
      echo "gebruik: $0 --boot MAP [--root MAP] [--wifi]" >&2
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
if [[ "$WIFI" -eq 1 && -n "$ROOT" ]]; then
  echo "--wifi gaat via de eerste start van de Pi; gebruik het zonder --root" >&2
  exit 1
fi

# --wifi: wifi van deze Mac, een gebruiker, ssh en de naam pi-speler.
# Geen wachtwoord komt op het scherm, in een log of in git.
# Op de kaart staan alleen een wachtwoord-hash en een afgeleide wifi-sleutel.
# De Pi zet ze bij de volgende start in het systeem en wist de map toegang.
ask() {
  # ask VRAAG -> antwoord op stdout. Vragen gaan naar stderr.
  local answer=""
  printf '%s' "$1" >&2
  IFS= read -r answer || true
  printf '%s' "$answer"
}

ask_secret() {
  local answer=""
  printf '%s' "$1" >&2
  IFS= read -rs answer || true
  printf '\n' >&2
  printf '%s' "$answer"
}

wifi_device() {
  networksetup -listallhardwareports 2>/dev/null \
    | awk '/^Hardware Port: (Wi-Fi|AirPort)/ { found = 1; next } found && /^Device:/ { print $2; exit }'
}

current_ssid() {
  local dev ssid
  dev="$(wifi_device)"
  [[ -n "$dev" ]] || dev=en0
  ssid="$(ipconfig getsummary "$dev" 2>/dev/null | sed -n 's/^[[:space:]]*SSID : //p' | head -1)"
  case "$ssid" in
    ""|"<redacted>"|*redacted*) ssid="" ;;
  esac
  if [[ -z "$ssid" ]]; then
    # Nieuwere macOS verbergt de naam. Dan het bovenste bekende netwerk als voorstel.
    ssid="$(networksetup -listpreferredwirelessnetworks "$dev" 2>/dev/null | sed -n '2s/^[[:space:]]*//p')"
  fi
  printf '%s' "$ssid"
}

sha512_hash() {
  # Wachtwoord via stdin, nooit als argument.
  local out=""
  out="$(openssl passwd -6 -stdin 2>/dev/null)" || out=""
  if [[ "${out:0:3}" != '$6$' ]]; then
    out=""
  fi
  printf '%s' "$out"
}

wifi_psk() {
  # WPA2-sleutel uit naam en wachtwoord (PBKDF2, zoals wpa_passphrase).
  python3 -c 'import hashlib, sys
ssid = sys.argv[1].encode("utf-8")
secret = sys.stdin.buffer.read()
print(hashlib.pbkdf2_hmac("sha1", secret, ssid, 4096, 32).hex())' "$1"
}

keyfile_escape() {
  local value="${1//\\/\\\\}"
  printf '%s' "$value"
}

setup_access() {
  local dir="$1" ssid guess wifi_pw psk user pw1 pw2 hash uuid
  guess="$(current_ssid)"
  if [[ -n "$guess" ]]; then
    ssid="$(ask "Wi-Fi-naam (Enter = $guess): ")"
    [[ -n "$ssid" ]] || ssid="$guess"
  else
    ssid="$(ask "Wi-Fi-naam (de Mac verbergt die, typ hem): ")"
  fi
  if [[ -z "$ssid" ]]; then
    echo "geen wifi-naam, ik stop" >&2
    return 1
  fi

  echo "Ik lees het wifi-wachtwoord uit de sleutelhanger. De Mac kan om toestemming of je wachtwoord vragen." >&2
  wifi_pw="$(security find-generic-password -D "AirPort network password" -a "$ssid" -w 2>/dev/null)" || wifi_pw=""
  if [[ -z "$wifi_pw" ]]; then
    wifi_pw="$(security find-generic-password -wa "$ssid" 2>/dev/null)" || wifi_pw=""
  fi
  if [[ -z "$wifi_pw" ]]; then
    wifi_pw="$(ask_secret "Niet gevonden. Wi-Fi-wachtwoord (je ziet niets als je typt): ")"
  else
    echo "Wifi-wachtwoord gevonden." >&2
  fi
  if [[ ${#wifi_pw} -lt 8 || ${#wifi_pw} -gt 63 ]]; then
    unset wifi_pw
    echo "dat wifi-wachtwoord heeft niet 8 tot 63 tekens, ik stop" >&2
    return 1
  fi
  psk="$(printf '%s' "$wifi_pw" | wifi_psk "$ssid")"
  unset wifi_pw
  if [[ ! "$psk" =~ ^[0-9a-f]{64}$ ]]; then
    echo "wifi-sleutel niet gemaakt, ik stop" >&2
    return 1
  fi

  user="$(ask "Gebruikersnaam op de Pi (Enter = gertjan): ")"
  [[ -n "$user" ]] || user=gertjan
  if [[ ! "$user" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
    echo "gebruikersnaam: kleine letters, cijfers, - of _" >&2
    return 1
  fi
  pw1="$(ask_secret "Wachtwoord voor $user op de Pi: ")"
  pw2="$(ask_secret "Nog een keer: ")"
  if [[ -z "$pw1" || "$pw1" != "$pw2" ]]; then
    unset pw1 pw2
    echo "wachtwoorden leeg of niet gelijk, ik stop" >&2
    return 1
  fi
  hash="$(printf '%s\n' "$pw1" | sha512_hash)"
  unset pw1 pw2
  if [[ -z "$hash" ]]; then
    echo "openssl passwd -6 werkt niet op deze Mac (brew install openssl), ik stop" >&2
    return 1
  fi

  uuid="$(uuidgen 2>/dev/null | tr 'A-Z' 'a-z')"
  [[ -n "$uuid" ]] || uuid="$(python3 -c 'import uuid; print(uuid.uuid4())')"

  rm -rf "$dir"
  (
    umask 077
    mkdir -p "$dir"
    printf '%s\n' pi-speler >"$dir/hostnaam"
    printf '%s\n' BE >"$dir/land"
    printf '%s:%s\n' "$user" "$hash" >"$dir/gebruiker"
    {
      printf '[connection]\nid=pi-speler-wifi\nuuid=%s\ntype=wifi\ninterface-name=wlan0\nautoconnect=true\n\n' "$uuid"
      printf '[wifi]\nmode=infrastructure\nssid=%s\n\n' "$(keyfile_escape "$ssid")"
      printf '[wifi-security]\nkey-mgmt=wpa-psk\npsk=%s\n\n' "$psk"
      printf '[ipv4]\nmethod=auto\n\n[ipv6]\nmethod=auto\n'
    } >"$dir/wifi.nmconnection"
  )
  unset hash psk
  : >"$BOOT/ssh"
  echo "Toegang klaar: wifi, gebruiker $user, ssh, naam pi-speler." >&2
  echo "Na de start: ssh $user@pi-speler.local" >&2
}

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

for file in config.py mapping.py playback.py led.py pi_speler.py install.sh start.sh toegang.sh pi-speler.service; do
  cp "$SRC/$file" "$BOOT/pi-speler/$file"
done
cp "$HERE/eenmalig.sh" "$BOOT/pi-speler/eenmalig.sh"
chmod +x "$BOOT/pi-speler/install.sh" "$BOOT/pi-speler/start.sh" "$BOOT/pi-speler/eenmalig.sh" || true

if [[ "$WIFI" -eq 1 ]]; then
  setup_access "$BOOT/pi-speler/toegang"
fi

if [[ -n "$ROOT" ]]; then
  if [[ ! -f "$ROOT/etc/os-release" || ! -d "$ROOT/etc/systemd/system" ]]; then
    echo "de root-map is geen Linux-systeem van de Pi" >&2
    exit 1
  fi
  opt="$ROOT/opt/pi-speler"
  mkdir -p "$opt/audio" "$ROOT/mnt/pi-speler" "$ROOT/etc/systemd/system/multi-user.target.wants"
  for file in config.py mapping.py playback.py led.py pi_speler.py install.sh start.sh toegang.sh; do
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
