# Drankjes die je lekker vindt

Een kleine site met een spreadsheet eronder. Je voegt drankjes toe die je lust, en de lijst zet de lichtste bovenaan.

De maat is **suiker per 100 ml**. Bij gelijke suiker telt het minste aantal calorieën, daarna de naam. Tot 5 g per 100 ml heet lichter, tot 8 g gemiddeld, daarboven zwaar.

## Starten

```bash
cd drankjes
python3 -m pip install -r requirements.txt
python3 server.py
```

Open daarna http://127.0.0.1:8765

De bron is `data/drankjes.xlsx`. Wat je op de site toevoegt, wijzigt of weghaalt, staat meteen in dat bestand. Je kunt het bestand ook in Excel of LibreOffice openen, een rij toevoegen (naam en suiker per 100 ml) en de site verversen.

Een download via de site is een kopie. Die loopt niet vanzelf mee. Bewerk `data/drankjes.xlsx`, of gebruik het formulier.

## Testen

```bash
cd drankjes
python3 -m unittest test_drankjes.py
```
