# SPDX-License-Identifier: GPL-3.0-or-later
"""Instellingen die je op de Pi mag aanpassen.

USB_MOUNT is de enige plek voor het stick-pad. Staat op die stick
audio/nl, audio/fr én audio/en, dan speelt de speler dáárvandaan.
"""

from __future__ import annotations

# Koppelpunt van de USB-stick. Niet de map audio/ zelf:
# de stick moet audio/nl, audio/fr en audio/en bevatten.
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


def force_analog_command() -> list[str]:
    """Commando dat de standaarduitgang van PipeWire op de jack zet.

    pactl set-default-sink alsa_output.platform-bcm2835_audio.stereo-fallback
    """

    return ["pactl", "set-default-sink", ANALOG_SINK]


def volume_command() -> list[str]:
    return ["amixer", "-c", "Headphones", "sset", "PCM", VOLUME, "unmute"]
