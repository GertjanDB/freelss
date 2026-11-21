#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Eén keer bij de volgende start. Haalt zichzelf uit cmdline.txt en zet de service aan.
set +e

CMDLINE=/boot/firmware/cmdline.txt
if [ ! -f "$CMDLINE" ]; then
  CMDLINE=/boot/cmdline.txt
fi

if [ -f "$CMDLINE" ]; then
  sed -i \
    -e 's| systemd.run=/boot/firmware/pi-speler/eenmalig.sh||g' \
    -e 's| systemd.run=/boot/pi-speler/eenmalig.sh||g' \
    -e 's| systemd.run_success_action=reboot||g' \
    -e 's| systemd.unit=kernel-command-line.target||g' \
    "$CMDLINE"
fi

BOOT="$(cd "$(dirname "$CMDLINE")" && pwd)"
if [ -f "$BOOT/pi-speler/install.sh" ]; then
  bash "$BOOT/pi-speler/install.sh"
fi
exit 0
