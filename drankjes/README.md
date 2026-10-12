# Drankjes die je lekker vindt

Een Google Spreadsheet met een Apps Script-pagina. Je zoekt een drank op, de pagina leest het etiket, en de lichtste blijft bovenaan. De lijst staat in de spreadsheet én op de pagina. Beide open je overal waar je met hetzelfde Google-account bent ingelogd.

De volgorde volgt de **weging**. Die start bij de suiker per 100 ml. Daarna telt mee wat erin zit:

- zoetstof, zoals stevia: +2
- kleurstof E150d: +1,5
- fosforzuur: +1,5
- cafeïne als aroma: +0,5
- thee-extract onder 1%: +1
- kombucha: −1,5
- minstens 1% sap: −0,5

Lager is lichter. Tot 4 is lichter, tot 8 gemiddeld, daarboven zwaar. Bij een gelijke weging telt daarna de minste suiker, dan de minste calorieën, dan de naam.

Van de vier voorbeelddrankjes is Yugen kombucha het lichtst (weging 1,8), daarna ice tea van Lipton (6), Almdudler (9,5) en Coca-Cola (14,1).

## Eenmalig klaarzetten

1. Maak op [sheets.google.com](https://sheets.google.com) een lege spreadsheet. Noem hem `Drankjes die je lekker vindt`.
2. Kies **Extensies → Apps Script**.
3. Verwijder de voorbeeldcode in `Code.gs` en plak daar `apps-script/Code.gs`.
4. Kies het plusje → **HTML**. Maak drie bestanden, met precies deze namen: `Index`, `Styles`, `Client`. Plak in elk bestand de inhoud van het gelijknamige `.html`-bestand uit `apps-script/`.
5. Klik op het tandwiel **Projectinstellingen** en vink **`appsscript.json`-manifestbestand weergeven in editor** aan. Vervang de inhoud door `apps-script/appsscript.json`.
6. Sla op (schijf-icoon). Kies bovenaan de functie **`installeer`** en klik op **Uitvoeren**. Keur de toegang goed, ook de verbinding om etiketten op te zoeken.
7. Ga terug naar de spreadsheet. Er is een blad **Ranglijst** (lichtste bovenaan) en een blad **Drankjes**. Het menu **Drankjes** verschijnt na een verversing.

Stond de lijst er al, alleen op suiker? Plak de nieuwe `Code.gs`, `Index`, `Styles` en `Client` over de oude bestanden en voer **`installeer`** opnieuw uit. Bestaande rijen krijgen een weging. Korte notities bij de vier voorbeeldnamen worden aangevuld met het opgezochte etiket.

## De pagina overal openen

1. In Apps Script: **Implementeren → Nieuwe implementatie**.
2. Tandwiel → **Web-app**.
3. Uitvoeren als: **Ik**. Wie heeft toegang: **Alleen ikzelf**.
4. Klik op **Implementeren** en kopieer het webadres.

Heb je de pagina al eerder gepubliceerd, kies dan **Implementatie beheren** en maak een nieuwe versie, anders blijft het oude scherm open.

Dat adres open je op je telefoon of laptop, ingelogd met hetzelfde Google-account. In de spreadsheet staat het ook onder **Drankjes → Webadres tonen**.

Op de pagina typ je een naam en kies je **Zoek op**. Je krijgt een paar etiketten; kies er een en zet hem op de lijst. Levert de zoekactie niets op, dan vul je de suiker zelf in. Zonder ingrediënten telt alleen de suiker.

In de Sheets-app kijk je op het blad **Ranglijst**.
