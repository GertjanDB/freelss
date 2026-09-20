# Semi-slim Marshall over wifi

De Pi speelt radio **over wifi** naar de Acton (Chromecast). **AUX blijft vrij voor de platenspeler. Bluetooth blijft vrij voor de gsm.**

## Elke dag

1. Acton aan, bronknop op **wifi**.
2. Pi aan (of laten staan).
3. Radio speelt. Platenspeler mag in AUX. Gsm koppelt gewoon over Bluetooth.

## Eerste keer

### 1. Acton één keer op wifi

Dat kan de speaker zelf niet. Eén keer Google Home op een telefoon of tablet: Acton op het huisnetwerk zetten. Daarna die app weer vergeten.

### 2. Pi op hetzelfde netwerk

Wifi of kabel, maakt niet uit — zolang Pi en Acton in hetzelfde huisnetwerk zitten.

```
sudo raspi-config
```

Systeemopties → Draadloos LAN, wifi-naam en wachtwoord. Of: ethernetkabel in de Pi.

### 3. Radio installeren

```
cd marshall-radio
sudo ./install.sh
```

Bronknop van de Acton op **wifi**. Radio 2 start vanzelf.

Zenders wisselen vanaf een computer: `http://<ip-van-de-pi>:8088`

Speakers op het netwerk:

```
sudo /opt/marshall-radio/venv/bin/python3 /opt/marshall-radio/radio.py --discover
```

Als de naam niet “Acton” bevat, zet in `config.json` bij `device` de naam die `--discover` toont. Optioneel `host` op het IP van de speaker als zoeken hapert.

## Wat vrij blijft

| Bron op de Acton | Voor |
| --- | --- |
| Wifi | Radio vanaf de Pi |
| AUX | Platenspeler |
| Bluetooth | Gsm |

## Computer zonder Pi

`radio.html` openen kan nog. Dan speelt deze computer zelf, en moet je die wél met Bluetooth of AUX aan de Acton hangen. Voor platenspeler + gsm tegelijk heb je de Pi-over-wifi-weg nodig.
