# Pi-speler

Achttien momentknoppen op een Raspberry Pi 4B. Elke knop speelt één WAV op de 3,5 mm-koptelefoonuitgang. Zes versies, drie talen (Nederlands, Frans, Engels). Een nieuwe druk stopt wat er speelt en begint dat bestand vooraan. Geen lus, geen lampjes, vast volume.

Zelfde nummer = dezelfde inhoud:

```
audio/nl/1.wav   audio/fr/1.wav   audio/en/1.wav
… tot en met 6.wav
```

## Aansluiten

Knop tussen de GPIO-pin en GND. Interne pull-up, actief laag. GND mag gedeeld: headerpinnen 6, 9, 14, 20, 25, 30, 34 of 39. Laat pin 1, 2, 4 en 17 leeg (voeding). Laat SPI uit: pin 26 is een knop.

| Versie | Taal | BCM | Pin |
| --- | --- | --- | --- |
| 1 | NL | 17 | 11 |
| 1 | FR | 27 | 13 |
| 1 | EN | 22 | 15 |
| 2 | NL | 5 | 29 |
| 2 | FR | 6 | 31 |
| 2 | EN | 13 | 33 |
| 3 | NL | 19 | 35 |
| 3 | FR | 26 | 37 |
| 3 | EN | 23 | 16 |
| 4 | NL | 24 | 18 |
| 4 | FR | 25 | 22 |
| 4 | EN | 12 | 32 |
| 5 | NL | 16 | 36 |
| 5 | FR | 20 | 38 |
| 5 | EN | 21 | 40 |
| 6 | NL | 4 | 7 |
| 6 | FR | 18 | 12 |
| 6 | EN | 7 | 26 |

Luidspreker of bestaande doos in de analoge 3,5 mm-jack.

## Geluid

Bij elke start:

```bash
pactl set-default-sink alsa_output.platform-bcm2835_audio.stereo-fallback
```

Elk bestand:

```bash
aplay -D plughw:CARD=Headphones,DEV=0 bestand.wav
```

`Headphones` is de jack. `vc4hdmi0` en `vc4hdmi1` worden niet geopend.

## Installeren op de Pi

Bookworm, Python 3. Vanuit deze map:

```bash
sudo ./install.sh
```

Dat zet `python3-gpiozero`, `alsa-utils` en `pulseaudio-utils` erop en zet de service `pi-speler` aan. De service start na `sound.target`, opnieuw bij een crash, en bij elke boot. Audiobestanden en `/boot/config.txt` blijven staan.

`USB_MOUNT` in `config.py` is `/mnt/pi-speler`. Staat op die stick `audio/nl`, `audio/fr` én `audio/en`, dan gelden die bestanden. Anders de map `audio/` naast het programma.

Logs als een knop stil blijft:

```bash
journalctl -u pi-speler -f
```

## Zonder Pi-pinnen

```bash
PI_SPELER_BENCH=1 python3 pi_speler.py
```

Typ `nl 1`, `fr 3`, `en 6`, `stop` of `quit`.

Test:

```bash
python3 -m unittest discover -s tests -v
```
