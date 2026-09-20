# Semi-slim Marshall

De **Acton Multi-Room** uit de doos heeft geen Google Home nodig. Bluetooth en AUX werken met de knoppen op de speaker. Deze map maakt er een radio van die je **aanzet en die speelt** — zonder gsm.

## Elke dag

1. Speaker aan.
2. Bronknop op **AUX** (kabel) of **Bluetooth**.
3. Radio speelt. Klaar.

Geen Marshall-app. Geen Google Home. Geen telefoon.

## Eerste keer — kies één weg

### A. Computer (snelst, 2 minuten)

1. Zet de bronknop van de Acton op **Bluetooth**.
2. Duw de knop **3 seconden** in tot het lampje knippert.
3. Koppel op de computer met **Acton Multi-room**.
4. Open `radio.html` in Chrome of Edge (slepen mag).
5. Tik een zender. Geluid gaat naar de speaker.

Of: AUX-kabel in de Acton, bronknop op **AUX**, dezelfde pagina openen.

### B. Raspberry Pi (gewoon opzetten, daarna nooit meer)

Pi en speaker samen aan het stekkerblok. Kabel is het stevigst (3,5 mm van de Pi naar AUX op de Acton).

```
cd marshall-radio
sudo ./install.sh
```

Daarna: `http://<ip-van-de-pi>:8088` als je toch eens van zender wilt wisselen — vanaf een computer op hetzelfde wifi-netwerk. Dagelijks: niks. De Pi start Radio 2 vanzelf.

Standaardzender en volume staan in `config.json`.

## Wat je níét moet doen

De doos zegt Google Home + Marshall-app. Dat is alleen voor wifi, Chromecast en de 7 wifi-presets op de bronknop. Voor radio via deze setup mag die hele circus overgeslagen worden.

Wil je later tóch die native knop-presets op de speaker zelf: één keer Google Home, daarna internetradio op stand 1–7 zetten, daarna weer zonder gsm. Niet nodig voor semi-slim.
