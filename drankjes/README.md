# Drankjes die je lekker vindt

Een Google Spreadsheet met een Apps Script-pagina. Je voegt drankjes toe die je lust. De lichtste blijft bovenaan, in de spreadsheet én op de pagina. Beide open je overal waar je met hetzelfde Google-account bent ingelogd.

De maat is **suiker per 100 ml**. Bij gelijke suiker telt het minste aantal calorieën, daarna de naam. Tot 5 g per 100 ml heet lichter, tot 8 g gemiddeld, daarboven zwaar.

## Eenmalig klaarzetten

1. Maak op [sheets.google.com](https://sheets.google.com) een lege spreadsheet. Noem hem `Drankjes die je lekker vindt`.
2. Kies **Extensies → Apps Script**.
3. Verwijder de voorbeeldcode in `Code.gs` en plak daar `apps-script/Code.gs`.
4. Kies het plusje → **HTML**. Maak drie bestanden, met precies deze namen: `Index`, `Styles`, `Client`. Plak in elk bestand de inhoud van het gelijknamige `.html`-bestand uit `apps-script/`.
5. Klik op het tandwiel **Projectinstellingen** en vink **`appsscript.json`-manifestbestand weergeven in editor** aan. Vervang de inhoud door `apps-script/appsscript.json`.
6. Sla op (schijf-icoon). Kies bovenaan de functie **`installeer`** en klik op **Uitvoeren**. Keur de toegang tot de spreadsheet goed.
7. Ga terug naar de spreadsheet. Er is een blad **Ranglijst** (lichtste bovenaan) en een blad **Drankjes**. Het menu **Drankjes** verschijnt na een verversing.

De vier drankjes van de lijst staan er meteen in: ice tea (Lipton Peach), Yugen kombucha, Almdudler en Coca-Cola.

## De pagina overal openen

1. In Apps Script: **Implementeren → Nieuwe implementatie**.
2. Tandwiel → **Web-app**.
3. Uitvoeren als: **Ik**. Wie heeft toegang: **Alleen ikzelf**.
4. Klik op **Implementeren** en kopieer het webadres.

Dat adres open je op je telefoon of laptop, ingelogd met hetzelfde Google-account. In de spreadsheet staat het ook onder **Drankjes → Webadres tonen**.

In de Sheets-app kijk je op het blad **Ranglijst**. Een nieuwe rij typ je op het blad **Drankjes** (naam en suiker per 100 ml). Daarna **Drankjes → Sorteren van licht naar zwaar**, of ververs de webpagina.
