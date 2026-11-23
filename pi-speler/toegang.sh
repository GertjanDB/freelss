#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Eén keer op de Pi, als root, vanuit install.sh.
# Leest de map toegang op de boot-schijf (gemaakt door zet-klaar.sh --wifi):
#   hostnaam           pi-speler
#   gebruiker          naam:wachtwoord-hash (openssl passwd -6)
#   wifi.nmconnection  NetworkManager-verbinding, sleutel al gehasht
#   land               BE
# Zet de naam, de gebruiker, ssh en wifi. Wist daarna de map.
# Drukt nooit een wachtwoord of hash af.
set -u

SRC="${1:-}"
# Alleen voor de tests: een nep-systeem in een tijdelijke map.
DOEL="${PI_SPELER_DOEL:-}"

say() { echo "pi-speler toegang: $*"; }

if [[ -z "$SRC" || ! -d "$SRC" ]]; then
  exit 0
fi

# Een bestand vervangen zonder sed -i (werkt ook in de tests op de Mac).
replace_file() {
  local target="$1" tmp="$1.pi-speler-tmp"
  cat >"$tmp" && mv "$tmp" "$target"
}

# Naam op het netwerk: pi-speler.local
if [[ -f "$SRC/hostnaam" ]]; then
  name="$(tr -cd 'a-z0-9-' <"$SRC/hostnaam")"
  if [[ -n "$name" ]]; then
    mkdir -p "$DOEL/etc"
    printf '%s\n' "$name" >"$DOEL/etc/hostname"
    hosts="$DOEL/etc/hosts"
    if [[ -f "$hosts" ]] && grep -q '^127\.0\.1\.1' "$hosts"; then
      awk -v n="$name" '/^127\.0\.1\.1/ { print "127.0.1.1\t" n; next } { print }' "$hosts" | replace_file "$hosts"
    else
      printf '127.0.1.1\t%s\n' "$name" >>"$hosts"
    fi
    # Trixie: cloud-init mag de naam niet terugzetten.
    if [[ -d "$DOEL/etc/cloud" ]]; then
      mkdir -p "$DOEL/etc/cloud/cloud.cfg.d"
      printf 'preserve_hostname: true\n' >"$DOEL/etc/cloud/cloud.cfg.d/99-pi-speler.cfg"
    fi
    say "naam $name"
  fi
fi

# Gebruiker met wachtwoord. Bestaat hij al, dan krijgt hij het nieuwe wachtwoord.
if [[ -f "$SRC/gebruiker" ]]; then
  line="$(head -n 1 "$SRC/gebruiker" | tr -d '\r')"
  user="${line%%:*}"
  hash="${line#*:}"
  if [[ ! "$user" =~ ^[a-z_][a-z0-9_-]{0,31}$ || "${hash:0:3}" != '$6$' ]]; then
    say "gebruiker ongeldig, overgeslagen"
  else
    if id "$user" >/dev/null 2>&1; then
      say "gebruiker $user bestaat al"
    else
      groups=""
      for group in sudo adm audio video plugdev gpio netdev dialout input users render spi i2c; do
        if getent group "$group" >/dev/null 2>&1; then
          groups="${groups:+$groups,}$group"
        fi
      done
      if useradd -m -s /bin/bash ${groups:+-G "$groups"} "$user"; then
        say "gebruiker $user gemaakt"
      else
        say "gebruiker $user niet gemaakt"
      fi
    fi
    # Hash via stdin, niet op de opdrachtregel.
    if printf '%s:%s\n' "$user" "$hash" | chpasswd -e; then
      say "wachtwoord gezet voor $user"
    else
      say "wachtwoord niet gezet voor $user"
    fi
    # De eerste-start-wizard van Bookworm hoeft niet meer: er is een gebruiker.
    if systemctl disable userconfig.service >/dev/null 2>&1; then
      systemctl enable getty@tty1.service >/dev/null 2>&1 || true
    fi
  fi
  unset line hash
fi

# SSH aan.
systemctl enable ssh.service >/dev/null 2>&1 || systemctl enable ssh >/dev/null 2>&1 || true
say "ssh aan"

# Wifi via NetworkManager (Bookworm en Trixie).
if [[ -f "$SRC/wifi.nmconnection" ]]; then
  dir="$DOEL/etc/NetworkManager/system-connections"
  mkdir -p "$dir"
  target="$dir/pi-speler-wifi.nmconnection"
  ( umask 077; cp "$SRC/wifi.nmconnection" "$target" )
  chmod 600 "$target"
  chown root:root "$target" 2>/dev/null || true

  # Wifi-radio aan bij de volgende start van NetworkManager.
  state="$DOEL/var/lib/NetworkManager/NetworkManager.state"
  if [[ -f "$state" ]]; then
    if grep -q '^WirelessEnabled=' "$state"; then
      awk '/^WirelessEnabled=/ { print "WirelessEnabled=true"; next } { print }' "$state" | replace_file "$state"
    else
      printf 'WirelessEnabled=true\n' >>"$state"
    fi
  fi

  # rfkill: de Pi houdt wifi geblokkeerd tot er een land is.
  for saved in "$DOEL"/var/lib/systemd/rfkill/*wlan*; do
    [[ -f "$saved" ]] && printf '0\n' >"$saved"
  done
  rfkill unblock wifi >/dev/null 2>&1 || true

  country="BE"
  if [[ -f "$SRC/land" ]]; then
    country="$(tr -cd 'A-Z' <"$SRC/land")"
    [[ ${#country} -eq 2 ]] || country="BE"
  fi
  if ! raspi-config nonint do_wifi_country "$country" >/dev/null 2>&1; then
    cmdline="$DOEL/boot/firmware/cmdline.txt"
    [[ -f "$cmdline" ]] || cmdline="$DOEL/boot/cmdline.txt"
    if [[ -f "$cmdline" ]] && ! grep -q 'cfg80211.ieee80211_regdom=' "$cmdline"; then
      awk -v c="$country" 'NR == 1 { print $0 " cfg80211.ieee80211_regdom=" c; next } { print }' "$cmdline" | replace_file "$cmdline"
    fi
  fi
  say "wifi klaar, land $country"
fi

# Geen geheimen laten liggen op de boot-schijf.
rm -rf "$SRC"
say "map toegang gewist"
exit 0
