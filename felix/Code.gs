/**
 * Webapp voor het spreadsheet "Felix eet en gewicht patroon".
 * Deploy: Uitvoeren als ik, toegang Iedereen.
 * doGet toont de pagina; saveEntry schrijft blad Registratie en vernieuwt Grafieken.
 */
var SPREADSHEET_ID = '1XQ4ZDI2sBRvFvwkXls_rV9kkRtaIq2LiiprU3FG7ouw';
var SHEET_LIST = 'Registratie';
var SHEET_CHARTS = 'Grafieken';
var HEADERS = [
  'Datum',
  'Tijdstip',
  'Start',
  'Stop',
  'Duur (min)',
  'Borst',
  'ml/cc',
  'Pipi',
  'Kaka',
  'Gewicht (g)',
  'Opmerkingen'
];

function doGet(e) {
  if (e && e.parameter && String(e.parameter.lijst || '') === '1') {
    var callback = String(e.parameter.callback || 'felixLijst').replace(/[^\w$]/g, '');
    return ContentService
      .createTextOutput(callback + '(' + JSON.stringify(listEntries()) + ')')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Felix · voeding')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

function doPost(e) {
  var data = {};
  try {
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    data = {};
  }
  var result = saveEntry(data);
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}

function saveEntry(entry) {
  var lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    var sheet = ensureListSheet(ss);
    var row = toRow(entry || {});
    sheet.appendRow(row);
    sheet.getRange(sheet.getLastRow(), 1, 1, HEADERS.length).setNumberFormats([
      ['@', '@', '@', '@', '0', '@', '0', '@', '@', '0', '@']
    ]);
    rebuildCharts(ss, sheet);
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

function listEntries() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sheet = ensureListSheet(ss);
  var last = sheet.getLastRow();
  if (last < 2) return [];
  var start = Math.max(2, last - 39);
  var values = sheet.getRange(start, 1, last - start + 1, HEADERS.length).getDisplayValues();
  var out = [];
  for (var i = values.length - 1; i >= 0; i--) {
    var r = values[i];
    if (!r[0] && !r[1] && !r[2]) continue;
    out.push({
      datum: r[0],
      tijdstip: r[1],
      start: r[2],
      stop: r[3],
      duur: r[4],
      borst: r[5],
      ml: r[6],
      pipi: r[7],
      kaka: r[8],
      gewicht: r[9],
      opmerking: r[10]
    });
  }
  return out;
}

function toRow(entry) {
  return [
    text(entry.datum),
    text(entry.tijdstip),
    text(entry.start),
    text(entry.stop),
    entry.duur === '' || entry.duur === null || entry.duur === undefined ? '' : Number(entry.duur),
    text(entry.borst),
    entry.ml === '' || entry.ml === null || entry.ml === undefined ? '' : Number(entry.ml),
    entry.pipi ? 'Ja' : '',
    entry.kaka ? 'Ja' : '',
    entry.gewicht === '' || entry.gewicht === null || entry.gewicht === undefined ? '' : Number(entry.gewicht),
    text(entry.opmerking)
  ];
}

function text(value) {
  return value === null || value === undefined ? '' : String(value);
}

function ensureListSheet(ss) {
  var sheet = ss.getSheetByName(SHEET_LIST);
  if (!sheet) {
    var first = ss.getSheets()[0];
    if (first && first.getLastRow() === 0) {
      first.setName(SHEET_LIST);
      sheet = first;
    } else {
      sheet = ss.insertSheet(SHEET_LIST, 0);
    }
  }
  if (sheet.getRange(1, 1).getValue() !== HEADERS[0]) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
    sheet.setFrozenRows(1);
    sheet.setColumnWidths(1, HEADERS.length, 110);
    sheet.setColumnWidth(11, 240);
  }
  return sheet;
}

function rebuildCharts(ss, source) {
  var chartSheet = ss.getSheetByName(SHEET_CHARTS);
  if (!chartSheet) chartSheet = ss.insertSheet(SHEET_CHARTS, 1);
  chartSheet.getCharts().forEach(function (chart) {
    chartSheet.removeChart(chart);
  });
  chartSheet.clear();

  var last = source.getLastRow();
  var rows = last < 2 ? [] : source.getRange(2, 1, last - 1, HEADERS.length).getValues();

  var weight = [['Datum', 'Tijdstip', 'Gewicht (g)']];
  var duration = [['Datum', 'Tijdstip', 'Duur (min)']];
  var feeds = {};
  var ml = {};
  var diapers = {};
  var breasts = {};

  rows.forEach(function (r) {
    var day = String(r[0] || '');
    if (!day) return;
    feeds[day] = (feeds[day] || 0) + 1;
    if (r[9] !== '' && r[9] !== null) weight.push([day, String(r[1] || ''), Number(r[9])]);
    if (r[4] !== '' && r[4] !== null) duration.push([day, String(r[1] || ''), Number(r[4])]);
    if (r[6] !== '' && r[6] !== null) ml[day] = (ml[day] || 0) + Number(r[6]);
    if (!diapers[day]) diapers[day] = { pipi: 0, kaka: 0 };
    if (r[7] === 'Ja') diapers[day].pipi += 1;
    if (r[8] === 'Ja') diapers[day].kaka += 1;
    if (r[5]) breasts[String(r[5])] = (breasts[String(r[5])] || 0) + 1;
  });

  var feedTable = [['Datum', 'Aantal']];
  Object.keys(feeds).sort().forEach(function (day) {
    feedTable.push([day, feeds[day]]);
  });
  var mlTable = [['Datum', 'ml/cc']];
  Object.keys(ml).sort().forEach(function (day) {
    mlTable.push([day, ml[day]]);
  });
  var diaperTable = [['Datum', 'Pipi', 'Kaka']];
  Object.keys(diapers).sort().forEach(function (day) {
    diaperTable.push([day, diapers[day].pipi, diapers[day].kaka]);
  });
  var breastTable = [['Borst', 'Aantal']];
  Object.keys(breasts).sort().forEach(function (key) {
    breastTable.push([key, breasts[key]]);
  });

  writeBlock(chartSheet, 1, 1, 'Gewicht', weight);
  writeBlock(chartSheet, 1, 5, 'Duur voeding', duration);
  writeBlock(chartSheet, 1, 9, 'Voedingen per dag', feedTable);
  writeBlock(chartSheet, 1, 12, 'Bijgevoed per dag', mlTable);
  writeBlock(chartSheet, 1, 15, 'Luiers per dag', diaperTable);
  writeBlock(chartSheet, 1, 19, 'Borsten', breastTable);

  var top = 20;
  addChart(chartSheet, weight, 1, 1, 'Gewicht (g)', Charts.ChartType.LINE, top, 1);
  addChart(chartSheet, duration, 1, 5, 'Duur (min)', Charts.ChartType.COLUMN, top, 8);
  addChart(chartSheet, feedTable, 1, 9, 'Voedingen per dag', Charts.ChartType.COLUMN, top + 18, 1);
  addChart(chartSheet, mlTable, 1, 12, 'ml/cc per dag', Charts.ChartType.COLUMN, top + 18, 8);
  addChart(chartSheet, diaperTable, 1, 15, 'Pipi en kaka', Charts.ChartType.COLUMN, top + 36, 1);
  addChart(chartSheet, breastTable, 1, 19, 'Borsten', Charts.ChartType.PIE, top + 36, 8);
}

function writeBlock(sheet, row, col, title, table) {
  sheet.getRange(row, col).setValue(title).setFontWeight('bold');
  if (!table.length) return;
  sheet.getRange(row + 1, col, table.length, table[0].length).setValues(table);
  sheet.getRange(row + 1, col, 1, table[0].length).setFontWeight('bold');
}

function addChart(sheet, table, row, col, title, type, anchorRow, anchorCol) {
  if (table.length < 2) return;
  var range = sheet.getRange(row + 1, col, table.length, table[0].length);
  var builder = sheet.newChart()
    .setChartType(type)
    .addRange(range)
    .setOption('title', title)
    .setOption('legend', { position: type === Charts.ChartType.PIE ? 'right' : 'bottom' })
    .setOption('height', 300)
    .setOption('width', 480)
    .setPosition(anchorRow, anchorCol, 0, 0);
  if (type !== Charts.ChartType.PIE) {
    builder.setOption('hAxis', { slantedText: true });
  }
  sheet.insertChart(builder.build());
}
