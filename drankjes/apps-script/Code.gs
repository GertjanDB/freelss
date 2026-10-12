/**
 * Drankjes die je lekker vindt.
 * Eerste keer: kies de functie installeer en klik op Uitvoeren.
 * Daarna: Implementeren → Nieuwe implementatie → Web-app.
 */

var BLAD_DATA = 'Drankjes';
var BLAD_RANG = 'Ranglijst';
var BLAD_UITLEG = 'Uitleg';
var MAX_DRANKJES = 200;
var GLAS_ML = 250;

var KOLOMMEN = {
  naam: ['naam'],
  suiker: ['suiker (g/100 ml)', 'suiker', 'suiker per 100 ml'],
  kcal: ['calorieën (kcal/100 ml)', 'calorieen (kcal/100 ml)', 'calorieën', 'calorieen', 'kcal'],
  ingredienten: ['ingrediënten', 'ingredienten'],
  toelichting: ['toelichting', 'notitie'],
  weging: ['weging'],
  toegevoegd: ['toegevoegd'],
  rang: ['rang'],
  id: ['id']
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Drankjes')
    .addItem('Lijst openen', 'openLijst')
    .addItem('Webadres tonen', 'toonLink')
    .addItem('Sorteren van licht naar zwaar', 'sorteerLijst')
    .addSeparator()
    .addItem('Blad klaarzetten', 'installeer')
    .addToUi();
}

function doGet() {
  return pagina_();
}

function openLijst() {
  var html = pagina_().setWidth(1100).setHeight(780);
  SpreadsheetApp.getUi().showModalDialog(html, 'Drankjes die je lekker vindt');
}

function toonLink() {
  var url = '';
  try {
    url = ScriptApp.getService().getUrl();
  } catch (err) {
    url = '';
  }
  if (!url) {
    melding_(
      'De web-app is nog niet gepubliceerd.\n\n' +
        'Kies Implementeren → Nieuwe implementatie → Web-app.\n' +
        'Uitvoeren als: Ik. Wie heeft toegang: Alleen ikzelf.'
    );
    return;
  }
  melding_('Open deze link op je telefoon of laptop. Je moet ingelogd zijn met dit Google-account.\n\n' + url);
}

function installeer() {
  var lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    var ss = SpreadsheetApp.getActive();
    ss.setSpreadsheetLocale('nl_NL');
    ss.setSpreadsheetTimeZone('Europe/Amsterdam');
    PropertiesService.getDocumentProperties().deleteProperty('formuleStijl');
    var sheet = zorgVoorDataBlad_(ss);
    var gelezen = lees_(sheet);
    if (!gelezen.kopOk) {
      if (!bladIsLeeg_(sheet)) {
        throw new Error('Het blad Drankjes heeft al andere inhoud. Maak een lege spreadsheet, of leeg dat blad, en voer installeer opnieuw uit.');
      }
      schrijfKop_(sheet);
      schrijf_(sheet, voorbeeldDrankjes_());
    } else {
      if (!kopActueel_(sheet)) schrijfKop_(sheet);
      schrijf_(sheet, gelezen.drinks);
    }
    bouwRanglijst_(ss);
    bouwUitleg_(ss);
    ordenBladen_(ss);
  } finally {
    lock.releaseLock();
  }
  melding_(
    'Klaar. Op het blad Ranglijst staat de lijst van licht naar zwaar. Lager weging is lichter.\n\n' +
      'Publiceer daarna de web-app via Implementeren → Nieuwe implementatie → Web-app, ' +
      'als je de pagina ook buiten de spreadsheet wilt openen.'
  );
}

function sorteerLijst() {
  metLock_(function () {
    var sheet = dataBlad_();
    var gelezen = lees_(sheet);
    if (!gelezen.kopOk) {
      throw new Error('Zet het blad eerst klaar via Drankjes → Blad klaarzetten.');
    }
    schrijf_(sheet, gelezen.drinks);
    bouwRanglijst_(SpreadsheetApp.getActive());
  });
}

function lijstOphalen() {
  return metLock_(function () {
    var ss = SpreadsheetApp.getActive();
    var sheet = dataBlad_();
    var gelezen = lees_(sheet);
    if (!gelezen.kopOk) {
      throw new Error('Zet het blad eerst klaar. Kies in de spreadsheet Drankjes → Blad klaarzetten.');
    }
    var gewenst = sorteer_(gelezen.drinks);
    if (!kopActueel_(sheet) || gelezen.dirty || !zelfdeVolgorde_(gelezen.drinks, gewenst)) {
      if (!kopActueel_(sheet)) schrijfKop_(sheet);
      schrijf_(sheet, gewenst);
      bouwRanglijst_(ss);
    }
    return antwoord_(gewenst, gelezen.warnings);
  });
}

function drankjeOpslaan(data) {
  return metLock_(function () {
    var sheet = dataBlad_();
    var gelezen = lees_(sheet);
    if (!gelezen.kopOk) {
      throw new Error('Zet het blad eerst klaar. Kies in de spreadsheet Drankjes → Blad klaarzetten.');
    }
    var bestaand = null;
    if (data && data.id) {
      bestaand = zoek_(gelezen.drinks, String(data.id));
      if (!bestaand) {
        throw new Error('Dit drankje staat niet meer op de lijst. Ververs de pagina.');
      }
    } else if (gelezen.drinks.length >= MAX_DRANKJES) {
      throw new Error('De lijst is vol (' + MAX_DRANKJES + ' drankjes).');
    }
    var drank = leesInvoer_(data, bestaand);
    var drinks = gelezen.drinks.slice();
    if (bestaand) {
      drinks = drinks.map(function (item) {
        return item.id === bestaand.id ? drank : item;
      });
    } else {
      var bezet = {};
      drinks.forEach(function (item) {
        bezet[item.id] = true;
      });
      while (bezet[drank.id]) drank.id = nieuwId_(bezet);
      drinks.push(drank);
    }
    var gewenst = sorteer_(drinks);
    schrijf_(sheet, gewenst);
    bouwRanglijst_(SpreadsheetApp.getActive());
    var payload = antwoord_(gewenst, []);
    payload.savedId = drank.id;
    return payload;
  });
}

function drankjeWeghalen(id) {
  return metLock_(function () {
    var sheet = dataBlad_();
    var gelezen = lees_(sheet);
    if (!gelezen.kopOk) {
      throw new Error('Zet het blad eerst klaar. Kies in de spreadsheet Drankjes → Blad klaarzetten.');
    }
    if (!zoek_(gelezen.drinks, String(id))) {
      throw new Error('Dit drankje staat niet meer op de lijst. Ververs de pagina.');
    }
    var drinks = gelezen.drinks.filter(function (item) {
      return item.id !== String(id);
    });
    schrijf_(sheet, drinks);
    bouwRanglijst_(SpreadsheetApp.getActive());
    return antwoord_(sorteer_(drinks), []);
  });
}

function pagina_() {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('Drankjes die je lekker vindt')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(naam) {
  return HtmlService.createHtmlOutputFromFile(naam).getContent();
}

function metLock_(fn) {
  var lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    return fn();
  } finally {
    lock.releaseLock();
  }
}

function dataBlad_() {
  var sheet = SpreadsheetApp.getActive().getSheetByName(BLAD_DATA);
  if (!sheet) {
    throw new Error('Het blad Drankjes ontbreekt. Kies Drankjes → Blad klaarzetten.');
  }
  return sheet;
}

function zorgVoorDataBlad_(ss) {
  var sheet = ss.getSheetByName(BLAD_DATA);
  if (sheet) return sheet;
  var bladen = ss.getSheets();
  if (bladen.length === 1 && bladIsLeeg_(bladen[0])) {
    bladen[0].setName(BLAD_DATA);
    return bladen[0];
  }
  return ss.insertSheet(BLAD_DATA);
}

function bladIsLeeg_(sheet) {
  var values = sheet.getDataRange().getValues();
  return values.every(function (row) {
    return row.every(function (cell) {
      return cell === '' || cell === null;
    });
  });
}

function schrijfKop_(sheet) {
  var kop = ['Naam', 'Suiker (g/100 ml)', 'Calorieën (kcal/100 ml)', 'Ingrediënten', 'Toelichting', 'Weging', 'Toegevoegd', 'Id'];
  sheet.getRange(1, 1, 1, kop.length).setValues([kop]);
  stijlDataBlad_(sheet, 0);
}

function kopActueel_(sheet) {
  var kop = sheet.getRange(1, 1, 1, 8).getValues()[0];
  return kop.map(sleutelVanKop_).join('|') === 'naam|suiker|kcal|ingredienten|toelichting|weging|toegevoegd|id';
}

function stijlDataBlad_(sheet, aantal) {
  sheet.setFrozenRows(1);
  sheet.setColumnWidth(1, 280);
  sheet.setColumnWidth(2, 140);
  sheet.setColumnWidth(3, 160);
  sheet.setColumnWidth(4, 360);
  sheet.setColumnWidth(5, 360);
  sheet.setColumnWidth(6, 90);
  sheet.setColumnWidth(7, 120);
  sheet.setColumnWidth(8, 110);
  sheet.hideColumns(8);
  var kop = sheet.getRange(1, 1, 1, 8);
  kop.setBackground('#1e6a45');
  kop.setFontColor('#ffffff');
  kop.setFontWeight('bold');
  kop.setHorizontalAlignment('center');
  kop.setWrap(true);
  kop.setVerticalAlignment('middle');
  sheet.setRowHeight(1, 32);

  var suikerRegel = SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThanOrEqualTo(0)
    .setAllowInvalid(true)
    .setHelpText('Suiker per 100 ml, 0 of hoger.')
    .build();
  var kcalRegel = SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThanOrEqualTo(0)
    .setAllowInvalid(true)
    .setHelpText('Calorieën per 100 ml, 0 of hoger.')
    .build();
  sheet.getRange('B2:B500').setDataValidation(suikerRegel);
  sheet.getRange('C2:C500').setDataValidation(kcalRegel);

  var kleur = SpreadsheetApp.newConditionalFormatRule()
    .setGradientMinpoint('#1e6a45')
    .setGradientMidpointWithValue('#e6c36a', SpreadsheetApp.InterpolationType.PERCENTILE, '50')
    .setGradientMaxpoint('#9d3a32')
    .setRanges([sheet.getRange('F2:F500')])
    .build();
  sheet.setConditionalFormatRules([kleur]);

  if (!sheet.getFilter()) {
    sheet.getRange('A1:G500').createFilter();
  }
  vernieuwGrafiek_(sheet, aantal);
}

function schrijf_(sheet, drinks) {
  var gewenst = sorteer_(drinks);
  var laatste = Math.max(sheet.getLastRow(), 1);
  if (laatste > 1) {
    sheet.getRange(2, 1, laatste - 1, 8).clearContent();
  }
  if (gewenst.length) {
    var rijen = gewenst.map(function (drank) {
      var beoordeeld = metOordeel_(drank);
      return [
        alsTekst_(beoordeeld.naam),
        beoordeeld.suiker,
        beoordeeld.kcal,
        alsTekst_(beoordeeld.ingredienten || ''),
        alsTekst_(beoordeeld.toelichting || ''),
        beoordeeld.weging,
        beoordeeld.toegevoegd,
        beoordeeld.id
      ];
    });
    sheet.getRange(2, 1, rijen.length, 8).setValues(rijen);
    sheet.getRange(2, 2, rijen.length, 2).setNumberFormat('0.00');
    sheet.getRange(2, 6, rijen.length, 1).setNumberFormat('0.0');
    sheet.getRange(2, 4, rijen.length, 2).setWrap(true);
  }
  stijlDataBlad_(sheet, gewenst.length);
}

function vernieuwGrafiek_(sheet, aantal) {
  sheet.getCharts().forEach(function (chart) {
    sheet.removeChart(chart);
  });
  if (!aantal) return;
  var grafiek = sheet
    .newChart()
    .setChartType(Charts.ChartType.BAR)
    .addRange(sheet.getRange(1, 1, aantal + 1, 1))
    .addRange(sheet.getRange(1, 6, aantal + 1, 1))
    .setPosition(2, 10, 0, 0)
    .setOption('title', 'Weging, lager is lichter')
    .setOption('legend', { position: 'none' })
    .setOption('height', 320)
    .setOption('width', 520)
    .build();
  sheet.insertChart(grafiek);
}

function bouwRanglijst_(ss) {
  var blad = ss.getSheetByName(BLAD_RANG);
  if (!blad) blad = ss.insertSheet(BLAD_RANG);
  blad.clear();
  blad.getCharts().forEach(function (chart) {
    blad.removeChart(chart);
  });
  blad.getRange(1, 1, 1, 5).setValues([[
    'Naam',
    'Weging',
    'Suiker (g/100 ml)',
    'Calorieën (kcal/100 ml)',
    'Toelichting'
  ]]);
  var kop = blad.getRange(1, 1, 1, 5);
  kop.setBackground('#1e6a45');
  kop.setFontColor('#ffffff');
  kop.setFontWeight('bold');
  blad.setFrozenRows(1);
  blad.setColumnWidth(1, 280);
  blad.setColumnWidth(2, 90);
  blad.setColumnWidth(3, 150);
  blad.setColumnWidth(4, 180);
  blad.setColumnWidth(5, 420);
  blad.getRange('A2').setFormula(queryFormule_(formuleStijl_()));
  blad.getRange('A:A').setWrap(true);
  blad.getRange('B:B').setNumberFormat('0.0');
  blad.getRange('C:D').setNumberFormat('0.00');
  blad.getRange('E:E').setWrap(true);
}

function bouwUitleg_(ss) {
  var blad = ss.getSheetByName(BLAD_UITLEG);
  if (!blad) blad = ss.insertSheet(BLAD_UITLEG);
  var regels = [
    ['Drankjes die je lekker vindt'],
    [''],
    ['Het blad Ranglijst staat van licht naar zwaar. Dat blad open je op je telefoon in de Google Sheets-app.'],
    ['Een nieuwe drank typ je op de webpagina. Die zoekt het etiket op en vult suiker, calorieën en ingrediënten in.'],
    [''],
    ['De weging start bij de suiker per 100 ml. Zoetstof, kleurstof E150d, fosforzuur en een thee-extract onder 1% maken de weging hoger. Kombucha en minstens 1% sap maken hem lager.'],
    ['Lager is lichter. Tot 4 is lichter, tot 8 gemiddeld, daarboven zwaar.'],
    [''],
    ['De webpagina publiceer je eenmalig via Implementeren → Nieuwe implementatie → Web-app.'],
    ['Uitvoeren als: Ik. Wie heeft toegang: Alleen ikzelf. Het webadres staat daarna onder Drankjes → Webadres tonen.']
  ];
  blad.clear();
  blad.getRange(1, 1, regels.length, 1).setValues(regels);
  blad.getRange(1, 1).setFontSize(16).setFontWeight('bold');
  blad.setColumnWidth(1, 720);
  blad.getRange(1, 1, regels.length, 1).setWrap(true);
}

function ordenBladen_(ss) {
  var namen = [BLAD_RANG, BLAD_DATA, BLAD_UITLEG];
  namen.forEach(function (naam, index) {
    var blad = ss.getSheetByName(naam);
    if (blad) ss.setActiveSheet(blad);
    if (blad) ss.moveActiveSheet(index + 1);
  });
  var rang = ss.getSheetByName(BLAD_RANG);
  if (rang) ss.setActiveSheet(rang);
}

function zoekDranken(term) {
  var zoek = ruimte_(term);
  if (zoek.length < 2) return { treffers: [], fout: 'Typ minstens twee letters.' };
  var treffers = profielTreffers_(zoek);
  var opgezocht = leesZoekantwoord_(zoek);
  var fout = opgezocht.fout && !treffers.length ? opgezocht.fout : '';
  if (opgezocht.products) {
    var gezien = {};
    var gevonden = [];
    opgezocht.products.forEach(function (product) {
      var treffer = trefferVanProduct_(zoek, product);
      if (!treffer) return;
      if (treffer.code && gezien[treffer.code]) return;
      if (treffer.code) gezien[treffer.code] = true;
      gevonden.push(treffer);
    });
    gevonden.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.suiker - b.suiker;
    });
    treffers = treffers.concat(gevonden);
  }
  if (!fout && !treffers.length) fout = 'Geen etiket gevonden. Vul de suiker zelf in.';
  return {
    treffers: treffers.slice(0, 5).map(function (item) {
      return {
        naam: item.naam,
        merk: item.merk || '',
        suiker: item.suiker,
        kcal: item.kcal,
        ingredienten: item.ingredienten,
        weging: item.weging,
        toelichting: item.toelichting,
        url: item.url || '',
        bron: item.bron || 'openfoodfacts'
      };
    }),
    fout: fout
  };
}

function leesZoekantwoord_(zoek) {
  var query = 'search_terms=' + encodeURIComponent(zoek)
    + '&search_simple=1&action=process&json=1&page_size=8'
    + '&fields=code,product_name,brands,ingredients_text,ingredients_text_nl,nutriments,countries_tags';
  var urls = [
    'https://world.openfoodfacts.org/cgi/search.pl?' + query,
    'https://world.openfoodfacts.net/cgi/search.pl?' + query
  ];
  var fout = 'De drank is niet opgezocht. Vul de suiker zelf in.';
  for (var i = 0; i < urls.length; i++) {
    try {
      var response = UrlFetchApp.fetch(urls[i], {
        muteHttpExceptions: true,
        headers: { 'User-Agent': 'Drankjeslijst/1.0 (personal spreadsheet)' }
      });
      if (response.getResponseCode() !== 200) {
        fout = 'De opzoekdienst antwoordt niet. Vul de suiker zelf in.';
        continue;
      }
      var data = JSON.parse(response.getContentText() || '{}');
      if (!data || !Array.isArray(data.products)) {
        fout = 'De opzoekdienst antwoordt niet. Vul de suiker zelf in.';
        continue;
      }
      return { products: data.products, fout: '' };
    } catch (err) {
      fout = 'De drank is niet opgezocht. Vul de suiker zelf in.';
    }
  }
  return { products: [], fout: fout };
}

function scoringJs() {
  var functies = [
    rond_, norm_, tekstGetal_, heeftZoetstof_, heeftE150d_, heeftFosforzuur_,
    heeftToegevoegdeCafeine_, heeftKombucha_, procenten_, venster_, isTheeVenster_,
    theeExtractOnderEen_, sapMinstensEen_, wegingVan_, bandVan_, profielen_,
    profielPast_, bekendProfiel_, metOordeel_
  ];
  return functies.map(function (fn) { return fn.toString(); }).join('\n');
}

function lees_(sheet) {
  var values = sheet.getDataRange().getValues();
  if (!values.length) return { kopOk: false, drinks: [], warnings: [], dirty: false };
  var kolom = {};
  values[0].forEach(function (kop, index) {
    var sleutel = sleutelVanKop_(kop);
    if (sleutel) kolom[sleutel] = index;
  });
  if (kolom.naam === undefined || kolom.suiker === undefined) {
    return { kopOk: false, drinks: [], warnings: [], dirty: false };
  }
  var drinks = [];
  var warnings = [];
  var dirty = false;
  var gezien = {};
  var vandaag = vandaag_();
  for (var r = 1; r < values.length; r++) {
    var row = values[r];
    if (rijLeeg_(row, kolom)) continue;
    var naam = ruimte_(row[kolom.naam]);
    if (!naam) {
      warnings.push('Rij ' + (r + 1) + ' heeft geen naam en telt niet mee.');
      continue;
    }
    var suiker = getalVanCel_(row[kolom.suiker]);
    if (suiker === null) {
      warnings.push('Rij ' + (r + 1) + ' (' + naam + ') heeft geen bruikbare suiker en telt niet mee.');
      continue;
    }
    if (suiker < 0 || suiker > 100) {
      warnings.push('Rij ' + (r + 1) + ' (' + naam + ') heeft een suikerwaarde buiten 0 tot 100 en telt niet mee.');
      continue;
    }
    suiker = rond_(suiker, 2);
    var kcalRuwe = kolom.kcal === undefined ? '' : row[kolom.kcal];
    var kcal = getalVanCel_(kcalRuwe);
    if (kcalRuwe === '' || kcalRuwe === null) {
      kcal = rond_(suiker * 4, 1);
      dirty = true;
    } else if (kcal === null || kcal < 0 || kcal > 900) {
      warnings.push('Rij ' + (r + 1) + ' (' + naam + ') heeft calorieën buiten bereik en telt niet mee.');
      continue;
    } else {
      kcal = rond_(kcal, 1);
    }
    var ingredienten = kolom.ingredienten === undefined ? '' : ruimte_(row[kolom.ingredienten]);
    if (naam.length > 80) {
      naam = naam.slice(0, 80).trim();
      dirty = true;
    }
    if (ingredienten.length > 500) {
      ingredienten = ingredienten.slice(0, 500).trim();
      dirty = true;
    }
    var id = kolom.id === undefined ? '' : ruimte_(row[kolom.id]);
    if (!id || id.charAt(0) === '=' || gezien[id]) {
      id = nieuwId_(gezien);
      dirty = true;
    }
    gezien[id] = true;
    var toegevoegd = kolom.toegevoegd === undefined ? '' : datumTekst_(row[kolom.toegevoegd]);
    if (!toegevoegd) {
      toegevoegd = vandaag;
      dirty = true;
    }
    var beoordeeld = metOordeel_({
      id: id,
      naam: naam,
      suiker: suiker,
      kcal: kcal,
      ingredienten: ingredienten,
      toegevoegd: toegevoegd
    });
    var opgeslagen = kolom.weging === undefined ? null : getalVanCel_(row[kolom.weging]);
    if (opgeslagen === null || Math.abs(opgeslagen - beoordeeld.weging) > 0.05) dirty = true;
    if (ingredienten !== beoordeeld.ingredienten) dirty = true;
    drinks.push(beoordeeld);
    if (drinks.length > MAX_DRANKJES) {
      throw new Error('De lijst heeft meer dan ' + MAX_DRANKJES + ' drankjes.');
    }
  }
  return { kopOk: true, drinks: drinks, warnings: warnings, dirty: dirty };
}

function leesInvoer_(data, bestaand) {
  if (!data || typeof data !== 'object') throw new Error('De invoer klopt niet.');
  var naam = ruimte_(data.naam);
  if (!naam) throw new Error('Vul een naam in.');
  if (naam.length > 80) throw new Error('De naam is te lang.');
  if (data.suiker === undefined || data.suiker === null || String(data.suiker).trim() === '') {
    throw new Error('Vul de suiker per 100 ml in. Die staat op het etiket.');
  }
  var suiker = getalVanCel_(data.suiker);
  if (suiker === null) throw new Error('Suiker moet een getal zijn, bijvoorbeeld 3,8.');
  if (suiker < 0) throw new Error('Suiker kan niet onder nul.');
  if (suiker > 100) throw new Error('Meer dan 100 g suiker per 100 ml klopt meestal niet. Controleer de komma.');
  suiker = rond_(suiker, 2);
  var kcal;
  if (data.kcal === undefined || data.kcal === null || String(data.kcal).trim() === '') {
    kcal = rond_(suiker * 4, 1);
  } else {
    kcal = getalVanCel_(data.kcal);
    if (kcal === null) throw new Error('Calorieën moeten een getal zijn.');
    if (kcal < 0) throw new Error('Calorieën kunnen niet onder nul.');
    if (kcal > 900) throw new Error('Dat zijn wel heel veel calorieën per 100 ml. Controleer de komma.');
    kcal = rond_(kcal, 1);
  }
  var ingredienten = ruimte_(data.ingredienten || '');
  if (ingredienten.length > 500) throw new Error('De ingrediënten zijn te lang.');
  return metOordeel_({
    id: bestaand ? bestaand.id : nieuwId_({}),
    naam: naam,
    suiker: suiker,
    kcal: kcal,
    ingredienten: ingredienten,
    toegevoegd: bestaand ? bestaand.toegevoegd : vandaag_()
  });
}

function antwoord_(drinks, warnings) {
  var ss = SpreadsheetApp.getActive();
  var gewenst = sorteer_(drinks);
  return {
    spreadsheet: ss.getName(),
    spreadsheetUrl: ss.getUrl(),
    gewijzigd: new Date().toISOString(),
    warnings: warnings || [],
    drinks: gewenst.map(function (drank, index) {
      return verrijk_(drank, index + 1);
    })
  };
}

function verrijk_(drank, rang) {
  var beoordeeld = metOordeel_(drank);
  var glasSuiker = rond_(beoordeeld.suiker * (GLAS_ML / 100), 2);
  return {
    id: beoordeeld.id,
    naam: beoordeeld.naam,
    suiker: beoordeeld.suiker,
    kcal: beoordeeld.kcal,
    ingredienten: beoordeeld.ingredienten,
    toelichting: beoordeeld.toelichting,
    notitie: beoordeeld.toelichting,
    weging: beoordeeld.weging,
    toegevoegd: beoordeeld.toegevoegd,
    rang: rang,
    band: bandVan_(beoordeeld.weging),
    glasMl: GLAS_ML,
    glasSuiker: glasSuiker,
    glasKcal: rond_(beoordeeld.kcal * (GLAS_ML / 100), 1),
    klontjes: rond_(glasSuiker / 4, 1)
  };
}

function voorbeeldDrankjes_() {
  var vandaag = vandaag_();
  return ['lipton', 'yugen', 'almdudler', 'cola'].map(function (sleutel) {
    var profiel = profielOpSleutel_(sleutel);
    return {
      id: sleutel === 'lipton' ? 'ice-tea' : sleutel,
      naam: profiel.naam,
      suiker: profiel.suiker,
      kcal: profiel.kcal,
      ingredienten: profiel.ingredienten,
      toegevoegd: vandaag
    };
  });
}

function sorteer_(drinks) {
  return drinks.slice().sort(function (a, b) {
    var wa = wegingGetal_(a);
    var wb = wegingGetal_(b);
    if (wa !== wb) return wa - wb;
    if (a.suiker !== b.suiker) return a.suiker - b.suiker;
    if (a.kcal !== b.kcal) return a.kcal - b.kcal;
    var naam = String(a.naam).localeCompare(String(b.naam), 'nl', { sensitivity: 'base' });
    if (naam !== 0) return naam;
    return String(a.id).localeCompare(String(b.id));
  });
}

function wegingGetal_(drank) {
  var weging = getalVanCel_(drank.weging);
  if (weging === null) weging = wegingVan_(drank.suiker, drank.ingredienten || '').weging;
  return weging;
}

function zelfdeVolgorde_(huidig, gewenst) {
  if (huidig.length !== gewenst.length) return false;
  for (var i = 0; i < huidig.length; i++) {
    if (huidig[i].id !== gewenst[i].id) return false;
  }
  return true;
}

function zoek_(drinks, id) {
  for (var i = 0; i < drinks.length; i++) {
    if (drinks[i].id === id) return drinks[i];
  }
  return null;
}

function sleutelVanKop_(waarde) {
  var tekst = ruimte_(waarde).toLowerCase();
  var sleutels = Object.keys(KOLOMMEN);
  for (var i = 0; i < sleutels.length; i++) {
    var aliassen = KOLOMMEN[sleutels[i]];
    if (aliassen.indexOf(tekst) !== -1) return sleutels[i];
  }
  return '';
}

function rijLeeg_(row, kolom) {
  var sleutels = Object.keys(kolom);
  for (var i = 0; i < sleutels.length; i++) {
    if (sleutels[i] === 'rang') continue;
    var waarde = row[kolom[sleutels[i]]];
    if (waarde !== '' && waarde !== null && waarde !== undefined) return false;
  }
  return true;
}

function getalVanCel_(waarde) {
  if (waarde === '' || waarde === null || waarde === undefined) return null;
  if (typeof waarde === 'boolean') return null;
  if (Object.prototype.toString.call(waarde) === '[object Date]') return null;
  if (typeof waarde === 'number') return isFinite(waarde) ? waarde : null;
  var tekst = String(waarde).trim().replace(/\s/g, '').replace(',', '.');
  if (!tekst || tekst.charAt(0) === '=') return null;
  var getal = Number(tekst);
  return isFinite(getal) ? getal : null;
}

function datumTekst_(waarde) {
  if (waarde === '' || waarde === null || waarde === undefined) return '';
  if (Object.prototype.toString.call(waarde) === '[object Date]' && !isNaN(waarde.getTime())) {
    return Utilities.formatDate(waarde, 'Europe/Amsterdam', 'yyyy-MM-dd');
  }
  return ruimte_(waarde);
}

function ruimte_(waarde) {
  return String(waarde === null || waarde === undefined ? '' : waarde).replace(/\s+/g, ' ').trim();
}

function alsTekst_(waarde) {
  var tekst = String(waarde || '');
  if (/^[=+\-@]/.test(tekst)) return "'" + tekst;
  return tekst;
}

function rond_(getal, plaatsen) {
  var factor = Math.pow(10, plaatsen);
  return Math.round((Number(getal) + Number.EPSILON) * factor) / factor;
}

function nieuwId_(bezet) {
  var id;
  do {
    id = Utilities.getUuid().replace(/-/g, '').slice(0, 8);
  } while (bezet[id]);
  return id;
}

function vandaag_() {
  return Utilities.formatDate(new Date(), 'Europe/Amsterdam', 'yyyy-MM-dd');
}

function formuleStijl_() {
  var props = PropertiesService.getDocumentProperties();
  var bewaard = props.getProperty('formuleStijl');
  if (bewaard === 'en-komma' || bewaard === 'en-puntkomma' || bewaard === 'nl') return bewaard;
  var stijl = proefFormuleStijl_();
  props.setProperty('formuleStijl', stijl);
  return stijl;
}

function proefFormuleStijl_() {
  var ss = SpreadsheetApp.getActive();
  var actief = ss.getActiveSheet();
  var scratch = ss.insertSheet('_probe');
  try {
    var cell = scratch.getRange('A1');
    var pogingen = [
      ['en-komma', '=SUM(1,2)'],
      ['en-puntkomma', '=SUM(1;2)'],
      ['nl', '=SOM(1;2)']
    ];
    for (var i = 0; i < pogingen.length; i++) {
      cell.setFormula(pogingen[i][1]);
      SpreadsheetApp.flush();
      if (cell.getValue() === 3) return pogingen[i][0];
    }
    return 'en-komma';
  } finally {
    ss.deleteSheet(scratch);
    ss.setActiveSheet(actief);
  }
}

function queryFormule_(stijl) {
  var query = 'select A, F, B, C, E where A is not null order by F, B, C, A';
  if (stijl === 'nl') return '=ALS.FOUT(QUERY(Drankjes!A2:H;"' + query + '";0);"")';
  if (stijl === 'en-puntkomma') return '=IFERROR(QUERY(Drankjes!A2:H;"' + query + '";0);"")';
  return '=IFERROR(QUERY(Drankjes!A2:H,"' + query + '",0),"")';
}

function melding_(tekst) {
  try {
    SpreadsheetApp.getUi().alert(tekst);
  } catch (err) {
    console.log(tekst);
  }
}

function norm_(waarde) {
  return String(waarde || '')
    .toLowerCase()
    .replace(/ß/g, 'ss')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function tekstGetal_(getal, plaatsen) {
  return rond_(getal, plaatsen).toFixed(plaatsen).replace(/\.?0+$/, '').replace('.', ',');
}

function heeftZoetstof_(tekst) {
  return /stevia|steviol|aspartam|acesulfa|cyclama|sucralose|sacharin/.test(tekst)
    || /e\s*960|e\s*951|e\s*950|e\s*952|e\s*955|e\s*954/.test(tekst);
}

function heeftE150d_(tekst) {
  return /e\s*150\s*d|ammoniumsulfiet|ammoniumsulfit|ammoniaksulfit|zuckerkulor|ammonium\s+sulfiet|ammonium\s+sulfit|sulfite\s+ammonia|ammonia\s+sulfite/.test(tekst);
}

function heeftFosforzuur_(tekst) {
  return /fosforzuur|phosphoric|phosphorique|phosphorsaure|e\s*338/.test(tekst);
}

function heeftToegevoegdeCafeine_(tekst) {
  return /arom\w*\s+cafeine|cafeine\s+arom|arom\w*\s+caffeine|caffeine\s+arom|waaronder\s+cafeine|waaronder\s+caffeine/.test(tekst);
}

function heeftKombucha_(tekst) {
  return /kombucha|scoby/.test(tekst);
}

function procenten_(tekst) {
  var re = /(\d+(?:[.,]\d+)?)\s*%/g;
  var hits = [];
  var match;
  while ((match = re.exec(tekst))) {
    hits.push({
      waarde: parseFloat(match[1].replace(',', '.')),
      index: match.index,
      lengte: match[0].length
    });
  }
  return hits;
}

function venster_(tekst, hit) {
  var start = Math.max(0, hit.index - 40);
  var end = Math.min(tekst.length, hit.index + hit.lengte + 40);
  return tekst.slice(start, end);
}

function isTheeVenster_(stuk) {
  return /thee|tea extract|tea-extract|black tea|extrait de the|tee-extrakt|tee extrakt|teeextrakt|zwarte thee|groene thee|thee-extract|thee extract/.test(stuk);
}

function theeExtractOnderEen_(tekst) {
  var hits = procenten_(tekst);
  var laag = false;
  for (var i = 0; i < hits.length; i++) {
    var stuk = venster_(tekst, hits[i]);
    if (!isTheeVenster_(stuk)) continue;
    if (hits[i].waarde >= 1) return false;
    laag = true;
  }
  return laag;
}

function sapMinstensEen_(tekst) {
  var hits = procenten_(tekst);
  for (var i = 0; i < hits.length; i++) {
    if (hits[i].waarde < 1) continue;
    if (/sap|jus|juice|passie|vrucht|fruit/.test(venster_(tekst, hits[i]))) return true;
  }
  return false;
}

function wegingVan_(suiker, ingredienten) {
  var basis = rond_(Number(suiker), 2);
  var tekst = norm_(ingredienten);
  if (!tekst) {
    return {
      weging: rond_(basis, 1),
      toelichting: 'Alleen de suiker telt mee. De ingrediënten zijn niet opgezocht.'
    };
  }
  var weging = basis;
  var delen = [];
  if (heeftZoetstof_(tekst)) {
    weging += 2;
    delen.push('zoetstof +2');
  }
  if (heeftE150d_(tekst)) {
    weging += 1.5;
    delen.push('E150d +1,5');
  }
  if (heeftFosforzuur_(tekst)) {
    weging += 1.5;
    delen.push('fosforzuur +1,5');
  }
  if (heeftToegevoegdeCafeine_(tekst)) {
    weging += 0.5;
    delen.push('cafeïne +0,5');
  }
  if (heeftKombucha_(tekst)) {
    weging -= 1.5;
    delen.push('kombucha −1,5');
  } else if (theeExtractOnderEen_(tekst)) {
    weging += 1;
    delen.push('weinig thee +1');
  }
  if (sapMinstensEen_(tekst)) {
    weging -= 0.5;
    delen.push('sap −0,5');
  }
  weging = rond_(weging, 1);
  var kern = 'Weging ' + tekstGetal_(weging, 1) + ': suiker ' + tekstGetal_(basis, 2);
  var toelichting = delen.length ? kern + ', ' + delen.join(', ') + '.' : kern + '.';
  if (toelichting.length > 280) toelichting = toelichting.slice(0, 277).trim() + '...';
  return { weging: weging, toelichting: toelichting };
}

function bandVan_(weging) {
  if (weging <= 4) return 'lichter';
  if (weging <= 8) return 'gemiddeld';
  return 'zwaar';
}

function profielen_() {
  return [
    {
      sleutel: 'yugen',
      naam: 'Yugen Kombucha Passion Fruit Elderflower',
      merk: 'Yugen',
      suiker: 3.8,
      kcal: 15,
      ingredienten: 'Water, kombuchacultuur, biologische groene en zwarte thee, biologische suiker, biologische kruideninfusie (vlierbloesem, aardbei, limoen, nootmuskaat), biologisch passievruchtsap (4%).'
    },
    {
      sleutel: 'lipton',
      naam: 'Ice tea (Lipton Peach)',
      merk: 'Lipton',
      suiker: 3,
      kcal: 13,
      ingredienten: "Water, suiker, fructose, voedingszuren (appelzuur, citroenzuur), thee-extract (0,12%), perziksap uit concentraat (0,1%), aroma's, zoetstof (steviolglycosiden van stevia)."
    },
    {
      sleutel: 'almdudler',
      naam: 'Almdudler',
      merk: 'Almdudler',
      suiker: 8,
      kcal: 33,
      ingredienten: 'Water, suiker, koolzuur, citroenzuur, kleurstof ammoniumsulfiet-karamel (E150d), natuurlijke kruidenextracten.'
    },
    {
      sleutel: 'cola',
      naam: 'Coca-Cola',
      merk: 'Coca-Cola',
      suiker: 10.6,
      kcal: 42,
      ingredienten: "Sprankelend water, suiker, kleurstof E150d, voedingszuur fosforzuur (E338), natuurlijke aroma's, aroma cafeïne."
    }
  ];
}

function profielOpSleutel_(sleutel) {
  var lijst = profielen_();
  for (var i = 0; i < lijst.length; i++) {
    if (lijst[i].sleutel === sleutel) return lijst[i];
  }
  return null;
}

function profielPast_(sleutel, n) {
  if (sleutel === 'yugen') {
    if (n.indexOf('yugen') !== -1) return true;
    var kombucha = n.indexOf('kombucha') !== -1;
    var smaak = n.indexOf('passion') !== -1 || n.indexOf('passie') !== -1 || n.indexOf('elder') !== -1 || n.indexOf('vlier') !== -1;
    return kombucha && smaak;
  }
  if (sleutel === 'lipton') {
    if (n.indexOf('lipton') === -1) return false;
    return n.indexOf('ice') !== -1 || n.indexOf('ijs') !== -1 || n.indexOf('peach') !== -1 || n.indexOf('perzik') !== -1 || n.indexOf('thee') !== -1 || n.indexOf('tea') !== -1;
  }
  if (sleutel === 'almdudler') {
    if (n.indexOf('almdudler') === -1) return false;
    return n.indexOf('light') === -1 && n.indexOf('zero') === -1 && n.indexOf('zuckerfrei') === -1 && n.indexOf('suikervrij') === -1;
  }
  if (sleutel === 'cola') {
    var cola = n.indexOf('coca-cola') !== -1 || n.indexOf('coca cola') !== -1 || n.indexOf('cocacola') !== -1;
    if (!cola) return false;
    return n.indexOf('zero') === -1 && n.indexOf('light') === -1 && n.indexOf('diet') === -1;
  }
  return false;
}

function bekendProfiel_(naam) {
  var n = norm_(naam);
  var lijst = profielen_();
  for (var i = 0; i < lijst.length; i++) {
    if (profielPast_(lijst[i].sleutel, n)) return lijst[i];
  }
  return null;
}

function metOordeel_(drank) {
  var ingredienten = String(drank.ingredienten || '').replace(/\s+/g, ' ').trim();
  var naam = String(drank.naam || '').replace(/\s+/g, ' ').trim();
  var profiel = bekendProfiel_(naam);
  if (profiel && ingredienten.length < 40) ingredienten = profiel.ingredienten;
  if (ingredienten.length > 500) ingredienten = ingredienten.slice(0, 500).trim();
  var oordeel = wegingVan_(drank.suiker, ingredienten);
  var toelichting = oordeel.toelichting;
  if (toelichting.length > 280) toelichting = toelichting.slice(0, 277).trim() + '...';
  return {
    id: drank.id,
    naam: naam,
    suiker: drank.suiker,
    kcal: drank.kcal,
    ingredienten: ingredienten,
    toelichting: toelichting,
    weging: oordeel.weging,
    toegevoegd: drank.toegevoegd
  };
}

function profielTreffers_(zoek) {
  var n = norm_(zoek);
  return profielen_().filter(function (profiel) {
    return profielPast_(profiel.sleutel, n);
  }).map(profielTreffer_);
}

function profielTreffer_(profiel) {
  var oordeel = wegingVan_(profiel.suiker, profiel.ingredienten);
  return {
    naam: profiel.naam,
    merk: profiel.merk,
    suiker: profiel.suiker,
    kcal: profiel.kcal,
    ingredienten: profiel.ingredienten,
    weging: oordeel.weging,
    toelichting: oordeel.toelichting,
    url: '',
    bron: 'bekend',
    score: 2
  };
}

function trefferVanProduct_(zoek, product) {
  if (!product) return null;
  var naam = ruimte_(product.product_name || '');
  if (!naam) return null;
  if (naam.length > 80) naam = naam.slice(0, 80).trim();
  var nutriments = product.nutriments || {};
  var suiker = getalVanCel_(nutriments.sugars_100g);
  if (suiker === null || suiker < 0 || suiker > 100) return null;
  suiker = rond_(suiker, 2);
  var kcal = getalVanCel_(nutriments['energy-kcal_100g']);
  if (kcal === null || kcal < 0 || kcal > 900) kcal = rond_(suiker * 4, 1);
  else kcal = rond_(kcal, 1);
  var ingredienten = ruimte_(product.ingredients_text_nl || product.ingredients_text || '');
  if (ingredienten.length > 500) ingredienten = ingredienten.slice(0, 500).trim();
  var score = overlapScore_(zoek, naam, product.brands, product.countries_tags, ingredienten);
  if (score <= 0) return null;
  var oordeel = wegingVan_(suiker, ingredienten);
  var merk = ruimte_(product.brands || '');
  if (merk.length > 40) merk = merk.slice(0, 40).trim();
  var code = ruimte_(product.code || '');
  return {
    code: code,
    naam: naam,
    merk: merk,
    suiker: suiker,
    kcal: kcal,
    ingredienten: ingredienten,
    weging: oordeel.weging,
    toelichting: oordeel.toelichting,
    url: code ? 'https://world.openfoodfacts.org/product/' + code : '',
    bron: 'openfoodfacts',
    score: score
  };
}

function overlapScore_(zoek, naam, merk, landen, ingredienten) {
  var tokens = norm_(zoek).split(/[^a-z0-9]+/).filter(function (token) {
    return token.length > 1;
  });
  if (!tokens.length) return 0;
  var naamNorm = norm_(naam);
  var merkNorm = norm_(merk || '');
  var nameHits = 0;
  var extra = 0;
  tokens.forEach(function (token) {
    if (naamNorm.indexOf(token) !== -1) nameHits++;
    else if (merkNorm.indexOf(token) !== -1) extra++;
  });
  if (!nameHits) return 0;
  var score = nameHits / tokens.length;
  if (extra) score += 0.15;
  var tags = Array.isArray(landen) ? landen.join(' ') : String(landen || '');
  if (/en:netherlands|en:belgium/.test(tags)) score += 0.3;
  else if (/en:germany|en:france|en:austria/.test(tags)) score += 0.15;
  if (ingredienten) score += 0.15;
  return rond_(score, 3);
}
