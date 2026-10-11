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
  notitie: ['notitie'],
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
    } else if (gelezen.dirty || !zelfdeVolgorde_(gelezen.drinks, sorteer_(gelezen.drinks))) {
      schrijf_(sheet, gelezen.drinks);
    } else {
      stijlDataBlad_(sheet, gelezen.drinks.length);
    }
    bouwRanglijst_(ss);
    bouwUitleg_(ss);
    ordenBladen_(ss);
  } finally {
    lock.releaseLock();
  }
  melding_(
    'Klaar. Op het blad Ranglijst staat de lijst van licht naar zwaar.\n\n' +
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
    if (gelezen.dirty || !zelfdeVolgorde_(gelezen.drinks, gewenst)) {
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
  var kop = ['Naam', 'Suiker (g/100 ml)', 'Calorieën (kcal/100 ml)', 'Notitie', 'Toegevoegd', 'Rang', 'Id'];
  sheet.getRange(1, 1, 1, kop.length).setValues([kop]);
  stijlDataBlad_(sheet, 0);
}

function stijlDataBlad_(sheet, aantal) {
  sheet.setFrozenRows(1);
  sheet.setColumnWidth(1, 320);
  sheet.setColumnWidth(2, 160);
  sheet.setColumnWidth(3, 180);
  sheet.setColumnWidth(4, 320);
  sheet.setColumnWidth(5, 120);
  sheet.setColumnWidth(6, 80);
  sheet.setColumnWidth(7, 110);
  sheet.hideColumns(7);
  var kop = sheet.getRange(1, 1, 1, 7);
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
    .setRanges([sheet.getRange('B2:B500')])
    .build();
  sheet.setConditionalFormatRules([kleur]);

  if (!sheet.getFilter()) {
    sheet.getRange('A1:F500').createFilter();
  }
  vernieuwGrafiek_(sheet, aantal);
}

function schrijf_(sheet, drinks) {
  var gewenst = sorteer_(drinks);
  var laatste = Math.max(sheet.getLastRow(), 1);
  if (laatste > 1) {
    sheet.getRange(2, 1, laatste - 1, 7).clearContent();
  }
  var stijl = formuleStijl_();
  if (gewenst.length) {
    var rijen = gewenst.map(function (drank, index) {
      var row = index + 2;
      return [
        alsTekst_(drank.naam),
        drank.suiker,
        drank.kcal,
        alsTekst_(drank.notitie),
        drank.toegevoegd,
        rangFormule_(row, stijl),
        drank.id
      ];
    });
    sheet.getRange(2, 1, rijen.length, 7).setValues(rijen);
    sheet.getRange(2, 2, rijen.length, 1).setNumberFormat('0.00');
    sheet.getRange(2, 3, rijen.length, 1).setNumberFormat('0.0');
    sheet.getRange(2, 4, rijen.length, 1).setWrap(true);
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
    .addRange(sheet.getRange(1, 1, aantal + 1, 2))
    .setPosition(2, 9, 0, 0)
    .setOption('title', 'Suiker per 100 ml')
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
    'Suiker (g/100 ml)',
    'Calorieën (kcal/100 ml)',
    'Notitie',
    'Rang'
  ]]);
  var kop = blad.getRange(1, 1, 1, 5);
  kop.setBackground('#1e6a45');
  kop.setFontColor('#ffffff');
  kop.setFontWeight('bold');
  blad.setFrozenRows(1);
  blad.setColumnWidth(1, 320);
  blad.setColumnWidth(2, 160);
  blad.setColumnWidth(3, 180);
  blad.setColumnWidth(4, 320);
  blad.setColumnWidth(5, 80);
  blad.getRange('A2').setFormula(queryFormule_(formuleStijl_()));
  blad.getRange('B:C').setNumberFormat('0.00');
}

function bouwUitleg_(ss) {
  var blad = ss.getSheetByName(BLAD_UITLEG);
  if (!blad) blad = ss.insertSheet(BLAD_UITLEG);
  var regels = [
    ['Drankjes die je lekker vindt'],
    [''],
    ['Het blad Ranglijst staat altijd van licht naar zwaar. Dat blad open je op je telefoon in de Google Sheets-app.'],
    ['Nieuwe drankjes komen op het blad Drankjes, of via de webpagina.'],
    ['Vul minstens de naam en de suiker per 100 ml in. Calorieën mag leeg: dan rekent de pagina 4 kcal per gram suiker.'],
    [''],
    ['Sortering: minste suiker per 100 ml, daarna minste calorieën, daarna de naam.'],
    ['Tot 5 g per 100 ml heet lichter, tot 8 g gemiddeld, daarboven zwaar.'],
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
    var notitie = kolom.notitie === undefined ? '' : ruimte_(row[kolom.notitie]);
    if (naam.length > 80) {
      naam = naam.slice(0, 80).trim();
      dirty = true;
    }
    if (notitie.length > 200) {
      notitie = notitie.slice(0, 200).trim();
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
    drinks.push({
      id: id,
      naam: naam,
      suiker: suiker,
      kcal: kcal,
      notitie: notitie,
      toegevoegd: toegevoegd
    });
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
  var notitie = ruimte_(data.notitie || '');
  if (notitie.length > 200) throw new Error('De notitie is te lang.');
  return {
    id: bestaand ? bestaand.id : nieuwId_({}),
    naam: naam,
    suiker: suiker,
    kcal: kcal,
    notitie: notitie,
    toegevoegd: bestaand ? bestaand.toegevoegd : vandaag_()
  };
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
  var glasSuiker = rond_(drank.suiker * (GLAS_ML / 100), 2);
  var band = 'zwaar';
  if (drank.suiker <= 5) band = 'lichter';
  else if (drank.suiker <= 8) band = 'gemiddeld';
  return {
    id: drank.id,
    naam: drank.naam,
    suiker: drank.suiker,
    kcal: drank.kcal,
    notitie: drank.notitie,
    toegevoegd: drank.toegevoegd,
    rang: rang,
    band: band,
    glasMl: GLAS_ML,
    glasSuiker: glasSuiker,
    glasKcal: rond_(drank.kcal * (GLAS_ML / 100), 1),
    klontjes: rond_(glasSuiker / 4, 1)
  };
}

function voorbeeldDrankjes_() {
  var vandaag = vandaag_();
  return [
    { id: 'ice-tea', naam: 'Ice tea (Lipton Peach)', suiker: 3, kcal: 13, notitie: 'Lipton Peach: gezoet met suiker en stevia.', toegevoegd: vandaag },
    { id: 'yugen', naam: 'Yugen Kombucha Passion Fruit Elderflower', suiker: 3.8, kcal: 15, notitie: 'Gefermenteerde thee met 4% passievruchtsap.', toegevoegd: vandaag },
    { id: 'almdudler', naam: 'Almdudler', suiker: 8, kcal: 33, notitie: 'Oostenrijkse kruidenlimonade.', toegevoegd: vandaag },
    { id: 'cola', naam: 'Coca-Cola', suiker: 10.6, kcal: 42, notitie: 'Klassieke cola.', toegevoegd: vandaag }
  ];
}

function sorteer_(drinks) {
  return drinks.slice().sort(function (a, b) {
    if (a.suiker !== b.suiker) return a.suiker - b.suiker;
    if (a.kcal !== b.kcal) return a.kcal - b.kcal;
    var naam = String(a.naam).localeCompare(String(b.naam), 'nl', { sensitivity: 'base' });
    if (naam !== 0) return naam;
    return String(a.id).localeCompare(String(b.id));
  });
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
  return Math.round((getal + Number.EPSILON) * factor) / factor;
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

function rangFormule_(row, stijl) {
  if (stijl === 'nl') {
    return '=ALS(A' + row + '="";"";AANTAL.ALS.VOORWAARDEN($B$2:$B$500;"<"&B' + row + ')+AANTAL.ALS.VOORWAARDEN($B$2:$B$500;B' + row + ';$C$2:$C$500;"<"&C' + row + ')+1)';
  }
  var formula =
    '=IF(A' + row + '="","",COUNTIFS($B$2:$B$500,"<"&B' + row + ')+COUNTIFS($B$2:$B$500,B' + row + ',$C$2:$C$500,"<"&C' + row + ')+1)';
  return stijl === 'en-puntkomma' ? formula.replace(/,/g, ';') : formula;
}

function queryFormule_(stijl) {
  var query = 'select A, B, C, D, F where A is not null order by B, C, A';
  if (stijl === 'nl') return '=ALS.FOUT(QUERY(Drankjes!A2:G;"' + query + '";0);"")';
  if (stijl === 'en-puntkomma') return '=IFERROR(QUERY(Drankjes!A2:G;"' + query + '";0);"")';
  return '=IFERROR(QUERY(Drankjes!A2:G,"' + query + '",0),"")';
}

function melding_(tekst) {
  try {
    SpreadsheetApp.getUi().alert(tekst);
  } catch (err) {
    console.log(tekst);
  }
}
