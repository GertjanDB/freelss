const FALLBACK = {
  location: "Jette",
  station: "Ukkel (KMI)",
  condition: "Zwaar bewolkt, droog",
  bulletin:
    "Deze namiddag is het vaak zwaarbewolkt en aanvankelijk nog overwegend droog. In de loop van de namiddag trekt een storing het land in vanaf de kust met regen. In de latere namiddag en vooravond bereikt de regen het centrum van het land. De maxima schommelen tussen 15 en 20 graden bij een matige zuidwestelijke wind.",
  observedAt: "2026-09-17T12:00:00+02:00",
  temp: 17.2,
  feelsLike: 13.8,
  humidity: 64,
  cloudinessOctas: 7,
  windKmh: 22,
  windGustKmh: 38,
  windDirection: 222,
  precipMm: 0,
  raining: false,
  rainSoon: true,
  todayMin: 12,
  todayMax: 19,
  hourly: [
    { time: "2026-09-17T13:00", temp: 16.6, rainChance: 13, windKmh: 19 },
    { time: "2026-09-17T14:00", temp: 17.3, rainChance: 22, windKmh: 22 },
    { time: "2026-09-17T15:00", temp: 18.3, rainChance: 31, windKmh: 21 },
    { time: "2026-09-17T16:00", temp: 18.0, rainChance: 40, windKmh: 21 },
    { time: "2026-09-17T17:00", temp: 17.5, rainChance: 51, windKmh: 20 },
    { time: "2026-09-17T18:00", temp: 15.7, rainChance: 68, windKmh: 18 },
    { time: "2026-09-17T19:00", temp: 15.6, rainChance: 86, windKmh: 17 },
    { time: "2026-09-17T20:00", temp: 15.2, rainChance: 90, windKmh: 18 },
  ],
};

const COPY = {
  yes: {
    stamp: "Mutsje op",
    headline: "Ja. Mutsje op, schat.",
    lead: "Eerste meters buiten na de materniteit: een pasgeboren koppie verliest snel warmte.",
  },
  "yes-wind": {
    stamp: "Mutsje op",
    headline: "Ja. Die wind pikt aan de oortjes.",
    lead: "Het KMI meet een matige zuidwestenwind. Mutsje over de oortjes, dekentje erbij.",
  },
  "yes-rain": {
    stamp: "Mutsje + hoes",
    headline: "Ja. Mutsje én regenhoes.",
    lead: "Het is al koel, en de storing vanaf de kust komt eraan. Droog én warm houden.",
  },
  "yes-cold": {
    stamp: "Warm mutsje",
    headline: "Ja. Warm mutsje, oortjes in.",
    lead: "Te koud voor een bloot hoofdje. Extra laagje, handjes weg, snel naar de auto.",
  },
  light: {
    stamp: "Dun mutsje mag",
    headline: "Twijfel. Een dun mutsje is fijn.",
    lead: "Het is zacht, maar een newborn blijft gevoelig. Dun mutsje tot je in de auto zit.",
  },
  no: {
    stamp: "Hoofdje vrij",
    headline: "Nee. Hoofdje mag bloot.",
    lead: "Het is zacht genoeg. Let op oververhitting — in de auto altijd mutsje af.",
  },
};

function round1(value) {
  return Math.round(Number(value));
}

function compass(degree) {
  if (degree == null || Number.isNaN(Number(degree))) return "";
  const dirs = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"];
  return dirs[Math.round(Number(degree) / 45) % 8];
}

function windWord(kmh) {
  if (kmh < 12) return "zwak";
  if (kmh < 20) return "matig";
  if (kmh < 29) return "matig tot vrij krachtig";
  return "krachtig";
}

function brusselsNow() {
  return new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Brussels" }));
}

function formatClock(date) {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

function hourLabel(stamp) {
  const date = new Date(stamp);
  if (Number.isNaN(date.getTime())) return stamp;
  return `${String(date.getHours()).padStart(2, "0")}u`;
}

function hatFor(temp, feelsLike, windKmh, raining, rainSoon) {
  const feel = feelsLike ?? temp;
  if (temp >= 24 && feel >= 22 && windKmh < 15 && !raining) return "no";
  if (temp >= 20 && feel >= 19 && windKmh < 18 && !raining && !rainSoon) return "light";
  if (raining || (rainSoon && feel < 18)) return "yes-rain";
  if (feel < 10 || temp < 10) return "yes-cold";
  if (windKmh >= 18 && feel < 20) return "yes-wind";
  return "yes";
}

function extraLead(weather, advice) {
  const feel = round1(weather.feelsLike ?? weather.temp);
  const temp = round1(weather.temp);
  const wind = `${windWord(weather.windKmh || 0)} ${compass(weather.windDirection)}-wind`.trim();
  if (advice.level.startsWith("yes")) {
    return `Het KMI meet ${temp}° in Jette, maar het voelt als ${feel}° met een ${wind}. ${advice.lead}`;
  }
  return advice.lead;
}

function decide(weather) {
  const level = hatFor(
    weather.temp,
    weather.feelsLike,
    weather.windKmh || 0,
    Boolean(weather.raining),
    Boolean(weather.rainSoon)
  );
  return { level, ...COPY[level] };
}

function tips(weather, level) {
  const items = [];
  if (level.startsWith("yes") || level === "light") {
    items.push("Mosterdgeel (of eender welk) mutsje over de oortjes tot je in de auto zit.");
  } else {
    items.push("Buiten mag het hoofdje bloot. Neem toch een mutsje mee in de luiertas.");
  }
  items.push("In het autostoeltje: mutsje áf. Daar wordt het snel te warm.");
  if (weather.rainSoon || weather.raining) {
    items.push("Regenhoes of maxicosi-cover klaar: storing vanaf de kust deze namiddag.");
  } else {
    items.push("Een dun dekentje over de maxi-cosi tot de deur van de auto.");
  }
  if ((weather.windKmh || 0) >= 18) {
    items.push("Windzijde van het ziekenhuis: baby tegen je borst, niet in de wind houden.");
  }
  items.push("Check nekje na 10 minuten: koud = extra laag, klam = iets uit.");
  return items;
}

function renderHours(hourly) {
  const root = document.getElementById("hours");
  root.innerHTML = "";
  (hourly || []).slice(0, 8).forEach((item) => {
    const raining = (item.precipMm || 0) > 0 || (item.rainChance || 0) >= 50;
    const level = hatFor(item.temp, item.feelsLike ?? item.temp, item.windKmh || 0, raining, raining);
    const hat = level === "no" ? "vrij" : level === "light" ? "dun" : "muts";
    const el = document.createElement("div");
    el.className = "hour";
    el.innerHTML = `<div class="t">${hourLabel(item.time)}</div><div class="d">${round1(item.temp)}°</div><div class="hat">${hat}</div>`;
    root.appendChild(el);
  });
}

function render(weather) {
  const advice = decide(weather);
  const hero = document.getElementById("hero");
  const img = document.getElementById("hero-img");
  const needsHat = advice.level !== "no";
  hero.classList.toggle("no-hat", !needsHat);
  img.src = needsHat ? "img/hero.png" : "img/baby-no-hat.png";
  img.alt = needsHat
    ? "Slapende baby met mosterdgeel mutsje voor de bewolkte lucht van Jette"
    : "Slapende baby zonder mutsje, ingebakerd in een creme deken";

  const verdict = document.getElementById("verdict");
  verdict.className = `verdict ${advice.level.startsWith("yes") ? "yes" : advice.level}`;
  document.getElementById("stamp").textContent = advice.stamp;
  document.getElementById("headline").textContent = advice.headline;
  document.getElementById("lead").textContent = extraLead(weather, advice);
  document.getElementById("temp").innerHTML = `${round1(weather.temp)}<small>°</small>`;
  const station = weather.station ? ` · ${weather.station}` : "";
  document.getElementById("condition").innerHTML = `${weather.condition || "Jette"}<br>Jette${station}`;
  document.getElementById("feels").textContent = `${round1(weather.feelsLike ?? weather.temp)}°`;
  document.getElementById("wind").textContent = `${compass(weather.windDirection)} ${round1(weather.windKmh)}`.trim();
  document.getElementById("range").textContent = `${round1(weather.todayMin)}–${round1(weather.todayMax)}°`;
  document.getElementById("bulletin").textContent = weather.bulletin;
  const list = document.getElementById("tips");
  list.innerHTML = "";
  tips(weather, advice.level).forEach((text, index) => {
    const li = document.createElement("li");
    if (text.toLowerCase().includes("autostoeltje")) li.className = "warn";
    li.textContent = text;
    list.appendChild(li);
  });
  renderHours(weather.hourly);
}

async function liveOpenMeteo() {
  const url =
    "https://api.open-meteo.com/v1/forecast?latitude=50.8754&longitude=4.3246&current=temperature_2m,apparent_temperature,relative_humidity_2m,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min&timezone=Europe%2FBrussels&forecast_days=2";
  const data = await fetch(url).then((res) => res.json());
  const current = data.current || {};
  const hourly = data.hourly || {};
  const now = brusselsNow();
  const rows = [];
  (hourly.time || []).forEach((stamp, index) => {
    const date = new Date(stamp);
    if (date < now) return;
    rows.push({
      time: stamp,
      temp: hourly.temperature_2m[index],
      feelsLike: hourly.apparent_temperature[index],
      rainChance: hourly.precipitation_probability[index],
      precipMm: hourly.precipitation[index],
      windKmh: hourly.wind_speed_10m[index],
    });
  });
  const soon = rows.slice(0, 6);
  return {
    ...FALLBACK,
    temp: current.temperature_2m ?? FALLBACK.temp,
    feelsLike: current.apparent_temperature ?? FALLBACK.feelsLike,
    humidity: current.relative_humidity_2m ?? FALLBACK.humidity,
    windKmh: current.wind_speed_10m ?? FALLBACK.windKmh,
    windGustKmh: current.wind_gusts_10m ?? FALLBACK.windGustKmh,
    windDirection: current.wind_direction_10m ?? FALLBACK.windDirection,
    precipMm: current.precipitation || 0,
    raining: (current.precipitation || 0) > 0,
    rainSoon: soon.some((item) => (item.rainChance || 0) >= 40 || (item.precipMm || 0) > 0),
    todayMin: (data.daily && data.daily.temperature_2m_min && data.daily.temperature_2m_min[0]) || FALLBACK.todayMin,
    todayMax: (data.daily && data.daily.temperature_2m_max && data.daily.temperature_2m_max[0]) || FALLBACK.todayMax,
    hourly: rows.slice(0, 10),
    source: "KMI-bulletin + live meting Jette",
  };
}

async function loadWeather() {
  try {
    const local = await fetch("/api/weather", { cache: "no-store" }).then((res) => {
      if (!res.ok) throw new Error("api");
      return res.json();
    });
    if (local && local.temp != null) return local;
  } catch (_error) {
    /* fall through */
  }
  try {
    return await liveOpenMeteo();
  } catch (_error) {
    return FALLBACK;
  }
}

function wireChrome() {
  const clock = document.getElementById("clock");
  const tick = () => {
    if (document.activeElement !== clock) clock.value = formatClock(brusselsNow());
  };
  tick();
  setInterval(tick, 1000);

  clock.addEventListener("focus", () => {
    clock.value = "";
  });
  clock.addEventListener("input", () => {
    const digits = clock.value.replace(/\D/g, "").slice(0, 4);
    clock.value = digits.length > 2 ? `${digits.slice(0, 2)}:${digits.slice(2)}` : digits;
  });

  document.getElementById("btn-home").addEventListener("click", () => {
    document.getElementById("app").scrollTo({ top: 0, behavior: "smooth" });
  });
  document.getElementById("btn-back").addEventListener("click", () => {
    clock.blur();
    clock.value = formatClock(brusselsNow());
    document.getElementById("app").scrollTo({ top: 0, behavior: "smooth" });
  });
  document.getElementById("btn-recents").addEventListener("click", () => {
    document.getElementById("headline").scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

wireChrome();
loadWeather().then(render);
