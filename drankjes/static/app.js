const listEl = document.querySelector("#list");
const summaryEl = document.querySelector("#summary");
const warningsEl = document.querySelector("#warnings");
const form = document.querySelector("#form");
const formTitle = document.querySelector("#form-title");
const submitButton = document.querySelector("#submit");
const cancelButton = document.querySelector("#cancel");
const previewEl = document.querySelector("#preview");
const errorEl = document.querySelector("#form-error");
const pathEl = document.querySelector("#sheet-path");
const timeEl = document.querySelector("#sheet-time");
const refreshButton = document.querySelector("#refresh");

const naamInput = document.querySelector("#naam");
const suikerInput = document.querySelector("#suiker");
const kcalInput = document.querySelector("#kcal");
const notitieInput = document.querySelector("#notitie");

const BAND = { lichter: "Lichter", gemiddeld: "Gemiddeld", zwaar: "Zwaar" };

let drinks = [];
let editingId = null;
let pendingDeleteId = null;
let savedId = null;

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([key, value]) => {
    if (value === null || value === undefined || value === false) return;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  });
  (children || []).forEach((child) => {
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  });
  return node;
}

function formatAmount(value) {
  return Number(value).toLocaleString("nl-NL", { maximumFractionDigits: 2 });
}

function parseNl(raw) {
  const text = String(raw ?? "").trim().replace(/\s/g, "").replace(",", ".");
  if (!text) return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

function klontjesWoord(value) {
  return value > 0 && value <= 1 ? "klontje" : "klontjes";
}

function kicker(drink) {
  if (drink.rang !== 1) return BAND[drink.band] || "";
  if (drink.band === "lichter") return "Lichtste keuze";
  return `Lichtste van deze lijst · ${BAND[drink.band]}`;
}

function versus(drink, lightest) {
  if (!lightest || drink.id === lightest.id) return "Minste suiker per 100 ml";
  const diff = Math.round((drink.suiker - lightest.suiker) * 100) / 100;
  return `${formatAmount(diff)} g meer suiker dan ${lightest.naam}`;
}

function compare(a, b) {
  if (a.suiker !== b.suiker) return a.suiker - b.suiker;
  if (a.kcal !== b.kcal) return a.kcal - b.kcal;
  const name = a.naam.localeCompare(b.naam, "nl", { sensitivity: "base" });
  if (name !== 0) return name;
  return String(a.id).localeCompare(String(b.id));
}

function showError(message) {
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function setEditing(drink) {
  editingId = drink ? drink.id : null;
  pendingDeleteId = null;
  formTitle.textContent = drink ? "Drankje aanpassen" : "Drankje toevoegen";
  submitButton.textContent = drink ? "Opslaan" : "Op de lijst";
  cancelButton.hidden = !drink;
  if (!drink) {
    form.reset();
  } else {
    naamInput.value = drink.naam;
    suikerInput.value = formatAmount(drink.suiker);
    kcalInput.value = formatAmount(drink.kcal);
    notitieInput.value = drink.notitie || "";
  }
  updatePreview();
  render();
}

async function api(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || "Er ging iets mis. Probeer het opnieuw.");
  }
  return payload;
}

function payloadFromForm() {
  const suiker = parseNl(suikerInput.value);
  const kcalText = kcalInput.value.trim();
  const data = {
    naam: naamInput.value,
    suiker: suikerInput.value.trim(),
    notitie: notitieInput.value,
  };
  if (kcalText) data.kcal = kcalText;
  if (suiker === null && suikerInput.value.trim()) {
    throw new Error("Suiker moet een getal zijn, bijvoorbeeld 3,8.");
  }
  if (kcalText && parseNl(kcalText) === null) {
    throw new Error("Calorieën moeten een getal zijn.");
  }
  return data;
}

function updatePreview() {
  const suiker = parseNl(suikerInput.value);
  if (suiker === null || suiker < 0) {
    previewEl.textContent = "";
    return;
  }
  const kcal = parseNl(kcalInput.value);
  const candidate = {
    id: editingId || "__nieuw__",
    naam: naamInput.value.trim() || "Dit drankje",
    suiker,
    kcal: kcal === null ? suiker * 4 : kcal,
  };
  const others = drinks.filter((drink) => drink.id !== editingId);
  const ordered = [...others, candidate].sort(compare);
  const place = ordered.findIndex((drink) => drink.id === candidate.id) + 1;
  previewEl.textContent = `${candidate.naam} komt op plek ${place} van ${ordered.length}.`;
}

function render() {
  const lightest = drinks[0];
  if (!drinks.length) {
    summaryEl.textContent = "Nog niets op de lijst. Voeg een drankje toe dat je lekker vindt.";
  } else if (drinks.length === 1) {
    summaryEl.textContent = `${lightest.naam} staat alleen op de lijst, met ${formatAmount(lightest.suiker)} g suiker per 100 ml.`;
  } else {
    summaryEl.textContent = `${lightest.naam} is de lichtste van je ${drinks.length} drankjes: ${formatAmount(lightest.suiker)} g suiker per 100 ml.`;
  }

  listEl.replaceChildren();
  if (!drinks.length) {
    listEl.append(el("li", { class: "empty" }, ["De lijst is leeg."]));
    return;
  }

  const scale = Math.max(12, ...drinks.map((drink) => drink.suiker));
  drinks.forEach((drink) => {
    const width = scale === 0 ? 0 : Math.min(100, (drink.suiker / scale) * 100);
    const card = el("article", {
      class: `drink band-${drink.band}${drink.rang === 1 ? " is-first" : ""}${drink.id === savedId ? " is-fresh" : ""}`,
    });
    card.append(el("p", { class: "rank" }, [String(drink.rang)]));
    const main = el("div", { class: "main" });
    const title = el("div", { class: "title-row" });
    title.append(el("div", {}, [
      el("p", { class: "kicker" }, [kicker(drink)]),
      el("h3", {}, [drink.naam]),
    ]));
    title.append(el("p", { class: "sugar" }, [
      el("strong", {}, [formatAmount(drink.suiker)]),
      el("span", {}, ["g suiker / 100 ml"]),
    ]));
    main.append(title);
    main.append(el("p", { class: "versus" }, [versus(drink, lightest)]));
    if (drink.notitie) main.append(el("p", { class: "note" }, [drink.notitie]));
    const meter = el("div", { class: "meter", "aria-hidden": "true" });
    const bar = el("span");
    bar.style.width = `${width}%`;
    meter.append(bar);
    main.append(meter);
    main.append(el("p", { class: "meta" }, [
      el("span", {}, [`${formatAmount(drink.kcal)} kcal / 100 ml`]),
      el("span", {}, [
        `Glas ${drink.glasMl} ml: ${formatAmount(drink.glasSuiker)} g · ${formatAmount(drink.klontjes)} ${klontjesWoord(drink.klontjes)}`,
      ]),
    ]));

    if (pendingDeleteId === drink.id) {
      main.append(el("p", { class: "confirm" }, ["Weghalen uit de lijst?"]));
      const actions = el("div", { class: "actions" });
      const yes = el("button", { type: "button", class: "danger" }, ["Ja, weghalen"]);
      yes.addEventListener("click", () => removeDrink(drink.id));
      const no = el("button", { type: "button" }, ["Laten staan"]);
      no.addEventListener("click", () => {
        pendingDeleteId = null;
        render();
      });
      actions.append(yes, no);
      main.append(actions);
    } else {
      const actions = el("div", { class: "actions" });
      const edit = el("button", { type: "button" }, ["Bewerken"]);
      edit.addEventListener("click", () => {
        setEditing(drink);
        form.scrollIntoView({ behavior: "smooth", block: "nearest" });
        naamInput.focus();
      });
      const remove = el("button", { type: "button" }, ["Weghalen"]);
      remove.addEventListener("click", () => {
        pendingDeleteId = drink.id;
        render();
      });
      actions.append(edit, remove);
      main.append(actions);
    }
    card.append(main);
    const item = el("li", { "data-id": drink.id });
    item.append(card);
    listEl.append(item);
  });
}

function applyPayload(payload) {
  drinks = payload.drinks || [];
  pathEl.textContent = payload.spreadsheet || "";
  if (payload.gewijzigd) {
    const when = new Date(payload.gewijzigd);
    timeEl.textContent = `Bijgewerkt ${when.toLocaleString("nl-NL")}`;
  } else {
    timeEl.textContent = "";
  }
  const warnings = payload.warnings || [];
  warningsEl.hidden = warnings.length === 0;
  warningsEl.replaceChildren();
  warnings.forEach((warning) => warningsEl.append(el("p", {}, [warning])));
  render();
}

async function load() {
  savedId = null;
  try {
    applyPayload(await api("GET", "/api/drinks"));
    showError("");
  } catch (error) {
    summaryEl.textContent = error.message;
  }
}

async function removeDrink(id) {
  savedId = null;
  try {
    pendingDeleteId = null;
    applyPayload(await api("DELETE", `/api/drinks/${encodeURIComponent(id)}`));
    if (editingId === id) setEditing(null);
  } catch (error) {
    showError(error.message);
    await load();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  let data;
  try {
    data = payloadFromForm();
  } catch (error) {
    showError(error.message);
    return;
  }
  submitButton.disabled = true;
  try {
    const url = editingId ? `/api/drinks/${encodeURIComponent(editingId)}` : "/api/drinks";
    const method = editingId ? "PUT" : "POST";
    const payload = await api(method, url, data);
    savedId = payload.savedId || null;
    setEditing(null);
    applyPayload(payload);
    if (savedId) {
      const node = listEl.querySelector(`[data-id="${CSS.escape(savedId)}"]`);
      node?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  } catch (error) {
    showError(error.message);
  } finally {
    submitButton.disabled = false;
  }
});

cancelButton.addEventListener("click", () => {
  setEditing(null);
  showError("");
});

[naamInput, suikerInput, kcalInput].forEach((input) => {
  input.addEventListener("input", updatePreview);
});

refreshButton.addEventListener("click", load);
load();
