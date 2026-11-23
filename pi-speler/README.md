# Pi-speler

Acht momentknoppen op een Raspberry Pi 4B, plus een config-pin zonder draad. Zes knoppen spelen A en B, elk in het Nederlands, Frans en Engels. Gids zet het geluid op de andere uitgang. Stop kapt het fragment af. Elke druk op een fragmentknop stopt wat er speelt en begint dat bestand vooraan, ook als je dezelfde knop nog eens drukt terwijl hij speelt. Niets herhaalt vanzelf.

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

De buitenste rij zijn de even nummers. Tel die vanaf pin 2, naast het vierkant.

| Tel | Pin | Draad |
| --- | --- | --- |
| 8e | 16 | Gids |
| 9e | 18 | Stop |
| 10e | 20 | massa voor gids en stop |
| 11e | 22 | config, geen draad |

Elke knop is een momentdrukker. Eén pootje naar de pin, het andere naar massa. Geen weerstand, geen pluspool. De pootjes van A mogen samen op pin 9. De pootjes van B mogen samen op pin 34. Gids en stop samen op pin 20.

Pin 22 krijgt geen vaste draad. Even pin 22 tegen pin 20 wisselt welke uitgang de standaard is: USB of de jack. Die keuze blijft na een herstart. Is de jack de standaard, dan zet gids het op USB. Niet vast laten zitten.

De luidspreker gaat met een 3,5 mm-kabel in de ronde bus aan de zijkant van de USB-C-voeding, tussen die voeding en de HDMI-poorten. Voeding: USB-C, 5 V, 3 A.

Standaard gaat een fragment altijd naar de Audiophony, met een USB-datakabel aan de Pi. Hangt die er niet aan, dan is er geen geluid en staat er een fout in de log. De speler wisselt niet vanzelf naar de jack. De knoppen blijven werken. Gids zet het op de mini-jack. Nog een keer gids: terug naar de standaard. Speelt er iets, dan begint dat fragment opnieuw op de nieuwe uitgang. HDMI niet. De 12 V van de versterker blijft apart.

De knoppen doen het ook 's nachts. De Pi blijft aan en herstart niet op een klok. Komt de stroom terug, dan start hij en blijft hij aan. Stopt de speler met een fout, dan start de service hem opnieuw.

Bij elke start van de Pi speelt de speler één keer A Nederlands, A Frans en A Engels na elkaar. Dat gaat altijd naar de mini-jack, ook als de standaard USB is. Een knop breekt de reeks af en doet gewoon wat hij moet doen. Daarna gaat alles weer naar de standaard. Uitzetten: `PI_SPELER_OPSTART=uit`, of `OPSTART = False` in `config.py`.

## Groene led

De groene led op het bordje, naast de rode, knippert zolang er een fragment speelt. Geen draad nodig. Is het fragment gedaan, druk je op stop, of kapt een nieuwe knop het af, dan gaat hij uit. Een nieuw fragment laat hem meteen weer knipperen. Stopt de speler, dan doet de led weer wat de Pi gewoon doet: knipperen bij SD-gebruik.

De speler schrijft naar `/sys/class/leds/ACT` (oudere systemen: `led0`). De service draait daarom als root. `config.txt` blijft onaangeroerd. Lukt de led niet, dan staat er één regel in de log en spelen de knoppen gewoon. Uitzetten: `PI_SPELER_LED=uit`.

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

Een nieuwe versie op een kaart die al draait: Pi uit, kaart in de Mac, en hetzelfde commando met `--boot /Volumes/bootfs`. De fragmenten in `audio` blijven staan. De Pi installeert bij de volgende start opnieuw en start één keer opnieuw.

Op Linux, met de tweede partitie erbij, hoeft die regel niet:

```bash
pi-speler/sd/zet-klaar.sh --boot /mnt/boot --root /mnt/root
```

## Inloggen via wifi

Wil je zien wat de Pi doet, zet dan wifi, een gebruiker en ssh op de kaart. Pi uit, kaart in de Mac:

```bash
cd ~/freelss
git pull
pi-speler/sd/zet-klaar.sh --boot /Volumes/bootfs --wifi
```

Het script neemt het wifi-netwerk van de Mac. De Mac verbergt soms de naam; dan stelt het script een bekend netwerk voor of typ je hem zelf. Het wifi-wachtwoord komt uit de sleutelhanger. De Mac vraagt daarvoor je toestemming of je wachtwoord. Lukt dat niet, dan typ je het. Daarna vraagt het een gebruikersnaam (Enter = `gertjan`) en twee keer een wachtwoord. Je ziet niets als je typt.

Op de kaart komt geen leesbaar wachtwoord: alleen een hash en een wifi-sleutel. De Pi zet ze bij de start in het systeem, wist ze van de kaart en start één keer opnieuw. Ook bij een nieuwe kaart: `pi-speler/sd/nieuw-systeem.sh --wifi`.

Daarna, op de Mac, in hetzelfde netwerk:

```bash
ssh gertjan@pi-speler.local
journalctl -u pi-speler -f
```

Alleen WPA2 of WPA2/WPA3 samen. Een netwerk met alleen WPA3 werkt zo niet.

## Als de knoppen niets doen

Staat in de log `geen enkele knop kon openen`, dan ontbreekt meestal lgpio. Nieuwere systemen (Trixie) hebben geen `/sys/class/gpio` meer, en gpiozero heeft dan `python3-lgpio` nodig. De service zet `GPIOZERO_PIN_FACTORY=lgpio`. De log zegt welke pin-factory de knoppen gebruiken.

lgpio maakt kleine pijpjes (`.lgd-nfy*`) in de werkmap. Op de FAT-schijf `/boot/firmware` kan dat niet. De service werkt daarom in `/run/pi-speler`, met `LG_WD` op dezelfde map. `start.sh` installeert niets; pakketten komen alleen van `install.sh`. Zonder `pactl` (Lite) gaat het geluid gewoon rechtstreeks met aplay naar de kaart.

Zonder knoppen stopt de speler niet en start hij niet steeds opnieuw: de opstartreeks speelt, de log geeft de tip. Op de Pi, via ssh:

```bash
sudo apt update
sudo apt install -y python3-lgpio
sudo systemctl restart pi-speler
journalctl -u pi-speler -f
```

## Zonder knoppen

```bash
PI_SPELER_BENCH=1 python3 pi_speler.py
```

Typ `a nl`, `b frans`, `a-engels`, `gids`, `stop`, `config` of `quit`.

```bash
python3 -m unittest discover -s tests -v
```
