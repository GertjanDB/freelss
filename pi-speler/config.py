# SPDX-License-Identifier: GPL-3.0-or-later
"""Instellingen die je op de Pi mag aanpassen.

USB_MOUNT is het koppelpunt van een stick met de map audio/.
Staat een fragment daar, dan wint dat van het bestand op de SD-kaart.
"""

from __future__ import annotations

from pathlib import Path

# Koppelpunt van de USB-stick. De stick bevat audio/a-nederlands.wav enzovoort.
USB_MOUNT = "/mnt/pi-speler"

# Vast volume van de jack. Geen knop; de versterker regel je aan de speaker.
VOLUME = "100%"

# gpiozero bounce_time is in seconden. 0,04 s = 40 ms.
BOUNCE_TIME = 0.04

# Actief laag: interne pull-up, knop naar GND. when_pressed is de vallende flank.
BUTTON_KWARGS = {"pull_up": True, "bounce_time": BOUNCE_TIME}

# PipeWire-sink van de analoge 3,5 mm-jack op een Pi 4 met Bookworm.
# HDMI heeft een andere naam (platform-...hdmi...) en wordt hier niet gezet.
ANALOG_SINK = "alsa_output.platform-bcm2835_audio.stereo-fallback"

# ALSA-kaart van diezelfde jack. vc4hdmi0 / vc4hdmi1 zijn de HDMI-poorten.
APLAY_DEVICE = "plughw:CARD=Headphones,DEV=0"

# De groene ACT-led op het bordje knippert zolang er een fragment speelt.
# Seconden aan, dan evenveel uit. Uitzetten: PI_SPELER_LED=uit.
LED_BLINK_S = 0.25

# Bij elke start van de speler: A Nederlands, A Frans, A Engels na elkaar,
# één keer, altijd op de mini-jack. Een knop breekt de reeks af.
# Uitzetten: OPSTART = False, of PI_SPELER_OPSTART=uit.
OPSTART = True
# Stilte tussen twee fragmenten van de reeks, in seconden.
OPSTART_PAUZE_S = 0.3

# usb of jack. De geheime config-pin draait dit om. Blijft staan na een herstart.
STATE_PATH = Path("/var/lib/pi-speler/standaard")


def force_analog_command() -> list[str]:
    """Commando dat de standaarduitgang van PipeWire op de jack zet.

    pactl set-default-sink alsa_output.platform-bcm2835_audio.stereo-fallback
    """

    return ["pactl", "set-default-sink", ANALOG_SINK]


def volume_command() -> list[str]:
    return ["amixer", "-c", "Headphones", "sset", "PCM", VOLUME, "unmute"]
