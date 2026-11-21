# Pi-speler

Zes momentknoppen op een Raspberry Pi 4B. A en B, elk in het Nederlands, Frans en Engels. Elke knop speelt één fragment op de 3,5 mm-uitgang. Een nieuwe druk stopt wat er speelt en begint dat bestand vooraan. Niets herhaalt vanzelf.

```
audio/a-nederlands.wav    zegt: A. Nederlands.
audio/a-frans.wav         zegt: A. Français.
audio/a-engels.wav        zegt: A. English.
audio/b-nederlands.wav    zegt: B. Nederlands.
audio/b-frans.wav         zegt: B. Français.
audio/b-engels.wav        zegt: B. English.
```

## Aansluiten

De Pi staat uit. Pin 1 is het vierkante soldeervlak, aan het uiteinde van de header dat het dichtst bij de USB-C-voeding zit. Dat pinnetje is 3,3 V. Pin 2 en 4, ernaast op de buitenrand, zijn 5 V. Daar komt geen draad aan.

De binnenste rij, naar het midden van de print, zijn de oneven nummers. Tel daarin vanaf het vierkant.

| Tel | Pin | Draad |
| --- | --- | --- |
| 5e | 9 | massa voor A |
| 6e | 11 | A Nederlands |
| 7e | 13 | A Frans |
| 8e | 15 | A Engels |
| 15e | 29 | B Nederlands |
| 16e | 31 | B Frans |
| 17e | 33 | B Engels |

Massa voor B is pin 34: op de buitenste rij, recht naast pin 33.

Elke knop is een momentdrukker. Eén pootje naar de pin, het andere naar massa. Geen weerstand, geen pluspool. De pootjes van A mogen samen op pin 9. De pootjes van B mogen samen op pin 34.

De luidspreker gaat met een 3,5 mm-kabel in de ronde bus aan de zijkant van de USB-C-voeding, tussen die voeding en de HDMI-poorten. Voeding: USB-C, 5 V, 3 A.

## Fragmenten vervangen

Een keer per jaar is de SD-kaart in de Mac het eenvoudigst. Zet de Pi uit, steek de kaart in de Mac en open de schijf `bootfs`. Vervang een bestand in de map `audio`. Zelfde naam. Laat `config.txt` met rust. Werp uit, kaart terug, Pi aan.

De bestanden: [pi-speler/audio](https://github.com/GertjanDB/freelss/tree/cursor/pi-fragmenten-ab-50f6/pi-speler/audio).

Een schoon systeem, dat de kaart wist:

```bash
pi-speler/sd/nieuw-systeem.sh
```

Dat schrijft Raspberry Pi OS Lite en daarna de speler. Alleen op de Mac, met de kaart als `boot` of `bootfs`.

`zet-klaar.sh` zet een bestaande Raspberry Pi OS-kaart klaar zonder hem te wissen. Alleen de boot-schijf:

```bash
pi-speler/sd/zet-klaar.sh --boot /pad/naar/bootfs
```

De Pi installeert zichzelf bij de eerste start en start één keer opnieuw. Komt hij niet terug, zet `cmdline.txt.pi-speler-backup` terug als `cmdline.txt`.

Op Linux, met de tweede partitie erbij, hoeft die regel niet:

```bash
pi-speler/sd/zet-klaar.sh --boot /mnt/boot --root /mnt/root
```

## Zonder knoppen

```bash
PI_SPELER_BENCH=1 python3 pi_speler.py
```

Typ `a nl`, `b frans`, `a-engels`, `stop` of `quit`.

```bash
python3 -m unittest discover -s tests -v
```
