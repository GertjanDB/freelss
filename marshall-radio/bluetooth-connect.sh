#!/usr/bin/env bash
# Optioneel: zet het MAC-adres van de Acton in /etc/marshall-radio.mac
# na één keer koppelen met bluetoothctl. AUX-kabel is betrouwbaarder.
set -euo pipefail

MAC_FILE="/etc/marshall-radio.mac"
if [[ ! -f "$MAC_FILE" ]]; then
  exit 0
fi

MAC="$(tr -d '[:space:]' < "$MAC_FILE")"
if [[ -z "$MAC" ]] || ! command -v bluetoothctl >/dev/null 2>&1; then
  exit 0
fi

bluetoothctl power on >/dev/null 2>&1 || true
bluetoothctl connect "$MAC" >/dev/null 2>&1 || true
exit 0
