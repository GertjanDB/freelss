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
apt-get install -y python3 python3-venv python3-pip avahi-daemon
systemctl enable --now avahi-daemon >/dev/null 2>&1 || true

mkdir -p "$DEST"
cp -f "$ROOT/radio.html" "$ROOT/radio.py" "$ROOT/stations.json" "$ROOT/config.json" "$ROOT/requirements.txt" "$DEST/"
chmod +x "$DEST/radio.py"

if [[ -f /etc/marshall-radio-config.json ]]; then
  cp -f /etc/marshall-radio-config.json "$DEST/config.json"
fi

python3 -m venv "$DEST/venv"
"$DEST/venv/bin/pip" install --upgrade pip
"$DEST/venv/bin/pip" install -r "$DEST/requirements.txt"

cat >/etc/systemd/system/marshall-radio.service <<EOF
[Unit]
Description=Semi-slimme Marshall-radio over wifi
After=network-online.target avahi-daemon.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DEST
ExecStart=$DEST/venv/bin/python3 $DEST/radio.py
Restart=on-failure
RestartSec=8

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable marshall-radio.service
systemctl restart marshall-radio.service

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Klaar. De Pi stuurt radio over wifi naar de Acton."
echo "AUX blijft vrij voor de platenspeler, Bluetooth voor de gsm."
echo "Bronknop Acton op wifi."
echo "Zenders wisselen: http://${IP:-pi}:8088"
echo "Speakers zoeken: $DEST/venv/bin/python3 $DEST/radio.py --discover"
echo
systemctl --no-pager --full status marshall-radio.service || true
