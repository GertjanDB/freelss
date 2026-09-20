#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="/opt/marshall-radio"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Start als root: sudo $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y mpv python3

mkdir -p "$DEST"
cp -f "$ROOT/radio.html" "$ROOT/radio.py" "$ROOT/stations.json" "$ROOT/config.json" "$DEST/"
chmod +x "$DEST/radio.py"

if [[ -f /etc/marshall-radio-config.json ]]; then
  cp -f /etc/marshall-radio-config.json "$DEST/config.json"
fi

cat >/etc/systemd/system/marshall-radio.service <<EOF
[Unit]
Description=Semi-slimme Marshall-radio
After=network-online.target sound.target bluetooth.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DEST
ExecStartPre=-$DEST/bluetooth-connect.sh
ExecStart=/usr/bin/python3 $DEST/radio.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

if [[ -f "$ROOT/bluetooth-connect.sh" ]]; then
  cp -f "$ROOT/bluetooth-connect.sh" "$DEST/bluetooth-connect.sh"
  chmod +x "$DEST/bluetooth-connect.sh"
fi

systemctl daemon-reload
systemctl enable marshall-radio.service
systemctl restart marshall-radio.service

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Klaar. De radio start nu vanzelf bij het opzetten van de Pi."
echo "Zenders wisselen: http://${IP:-pi}:8088"
echo "Bronknop Acton op AUX (kabel) of Bluetooth."
echo
systemctl --no-pager --full status marshall-radio.service || true
