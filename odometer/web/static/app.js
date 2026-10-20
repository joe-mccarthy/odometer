"use strict";
const $ = (id) => document.getElementById(id);
const categories = [
  "FUEL",
  "SERVICE",
  "MOT",
  "INSURANCE",
  "TAX",
  "REPAIR",
  "FINANCE",
  "TYRES",
  "CLEANING",
  "PARKING",
  "TOLL",
  "FINE",
  "ACCESSORY",
  "OTHER",
];
const money = (p) =>
  p == null
    ? "Unavailable"
    : new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: "GBP",
      }).format(p / 100);
const number = (n, unit = "") =>
  n == null
    ? "Unavailable"
    : `${new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(n)}${unit}`;
function pence(value) {
  if (!/^\d+(\.\d{1,2})?$/.test(value))
    throw new Error("Enter GBP with at most two decimal places.");
  const [whole, fraction = ""] = value.split(".");
  const result = Number(whole + fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(result)) throw new Error("Amount is too large.");
  return result;
}
function editMoney(record, name) {
  const value = BigInt(record[name + "_exact"] ?? record[name]);
  return `${value / 100n}.${(value % 100n).toString().padStart(2, "0")}`;
}
function node(tag, text, parent) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  if (parent) parent.append(el);
  return el;
}
let vehicles = [],
  generation = 0,
  busy = false,
  initialContext = true,
  creationFocus = false,
  writeConfirmed = false;
const errorRegion = () => $("vehicle-dialog").open ? $("vehicle-errors") : $("error");
function clearError() {
  $("vehicle-errors").replaceChildren();
  $("error").hidden = true;
  document.querySelectorAll(".field-error").forEach((e) => e.remove());
  document.querySelectorAll("[aria-invalid]").forEach((e) => {
    e.removeAttribute("aria-invalid");
    e.removeAttribute("aria-describedby");
  });
}
function showError(error, form) {
  errorRegion().textContent =
    error.message || "Request failed. Check the local server and refresh.";
  errorRegion().hidden = false;
  for (const [path, message] of Object.entries(error.fields || {})) {
    const name = path.replace(/^body\./, "");
    const input = form?.elements.namedItem(name);
    if (input) {
      input.setAttribute("aria-invalid", "true");
      const hint = node("span", message, input.parentElement);
      hint.className = "field-error";
      hint.id = `${form.id}-${name}-error`;
      input.setAttribute("aria-describedby", hint.id);
    } else errorRegion().textContent += `\n${name}: ${message}`;
  }
  errorRegion().focus();
}
// All request bodies are flat objects. Encode bigint money as numeric JSON tokens,
// while JSON.stringify still escapes every key and all ordinary field values.
function requestJSON(body) {
  return "{" + Object.entries(body).filter(([, value]) => value !== undefined)
    .map(([key, value]) => JSON.stringify(key) + ":" +
      (typeof value === "bigint" ? value.toString() : JSON.stringify(value)))
    .join(",") + "}";
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api" + path, {
    method,
    cache: "no-store",
    headers:
      method === "GET"
        ? {}
        : { "Content-Type": "application/json", "X-Odometer-Request": "1" },
    body: body === undefined ? undefined : requestJSON(body),
  });
  const data = await response.json();
  if (!response.ok) throw data.error || new Error("Request failed");
  if (method !== "GET") writeConfirmed = true;
  return data;
}
const specs = {
  "vehicle-form": [
    ["registration", "Registration", "text", true],
    ["initial_mileage", "Initial mileage (miles)", "integer", true],
    ["make", "Make"],
    ["model", "Model"],
    ["nickname", "Nickname"],
    ["year", "Year", "integer"],
    ["fuel_tank_litres", "Tank capacity (litres)", "number"],
    ["purchase_date", "Purchase date", "date"],
    ["purchase_price_pence", "Purchase price (GBP)", "money"],
  ],
  "fuel-form": [
    ["date", "Date", "date", true],
    ["odometer_miles", "Odometer (miles)", "integer", true],
    ["litres", "Fuel (litres)", "number", true],
    ["total_cost_pence", "Total cost (GBP)", "money", true],
    ["is_full_tank", "Full tank", "checkbox"],
    ["fuel_tank_litres", "Tank capacity (litres, optional)", "number"],
    ["station", "Station"],
    ["notes", "Notes"],
  ],
  "expense-form": [
    ["date", "Date", "date", true],
    ["category", "Category", "select", true],
    ["amount_pence", "Amount (GBP)", "money", true],
    ["odometer_miles", "Odometer (miles)", "integer"],
    ["description", "Description"],
    ["vendor", "Vendor"],
    ["notes", "Notes"],
  ],
};
for (const [id, fields] of Object.entries(specs)) {
  const form = $(id);
  for (const [name, title, type = "text", required = false] of fields) {
    const label = node("label", title, form);
    const input = node(type === "select" ? "select" : "input", null, label);
    input.name = name;
    input.id = `${id}-${name}`;
    input.required = required;
    if (id === "vehicle-form") label.firstChild.textContent += required ? " (required)" : " (optional)";
    if (type === "select")
      categories.forEach((c) => {
        const o = node("option", c, input);
        o.value = c;
      });
    else {
      input.type = ["integer", "number"].includes(type)
        ? "number"
        : type === "money"
          ? "text"
          : type;
      if (type === "money") {
        input.inputMode = "decimal";
        input.pattern = "[0-9]+(\\.[0-9]{1,2})?";
      }
      if (type === "integer") {
        input.min = "0";
        input.max = "9007199254740991";
        input.step = "1";
      }
      if (type === "number") {
        input.min = "0.01";
        input.step = "any";
      }
      if (type === "checkbox") input.checked = true;
    }
  }
  node(
    "button",
    id === "vehicle-form"
      ? "Add vehicle"
      : id === "fuel-form"
        ? "Save fuel"
        : "Save expense",
    form,
  );
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    mutate(form, async () => {
      const body = {};
      for (const [name, , type = "text"] of fields) {
        const input = form.elements.namedItem(name);
        if (type === "checkbox") body[name] = input.checked;
        else if (input.value !== "") {
          body[name] =
            type === "money"
              ? pence(input.value)
              : ["integer", "number"].includes(type)
                ? Number(input.value)
                : input.value;
          if (type === "integer" && !Number.isSafeInteger(body[name]))
            throw new Error("Use a safe whole number.");
        }
      }
      const selected = $("vehicle").value;
      if (id !== "vehicle-form" && !selected)
        throw new Error("Select a vehicle first.");
      const result = await api(
        id === "vehicle-form"
          ? "/vehicles"
          : `/vehicles/${encodeURIComponent(selected)}/${id === "fuel-form" ? "fuel" : "expenses"}`,
        "POST",
        body,
      );
      form.reset();
      resetHistory();
      if (id === "vehicle-form") {
        $("vehicle-dialog").close("saved");
        creationFocus = true;
        await load(result.id);
      }
      else await load(selected);
    });
  });
}
async function mutate(form, action) {
  if (busy) return;
  busy = true;
  writeConfirmed = false;
  clearError();
  $("status").textContent = "Saving…";
  const focus = document.activeElement;
  let failed = false;
  document.querySelectorAll("button,input,select").forEach((e) => {
    e.dataset.wasDisabled = String(e.disabled);
    e.disabled = true;
  });
  try {
    await action();
    $("status").textContent = "Saved. Current data refreshed.";
  } catch (e) {
    failed = true;
    creationFocus = false;
    showError(e, form);
    $("status").textContent =
      writeConfirmed
        ? "Saved. Could not refresh totals; refresh to see current values."
        : "Save could not be confirmed. Refresh before trying again.";
  } finally {
    busy = false;
    document.querySelectorAll("button,input,select").forEach((e) => {
      e.disabled = e.dataset.wasDisabled === "true";
    });
    updatePageButtons();
    $("add-reminder").disabled = !$("vehicle").value;
    if (!failed) {
      if (creationFocus) {
        creationFocus = false;
        $("context").focus();
        $("status").textContent = "Saved. Vehicle added. Ready to record fuel or an expense.";
      } else if (focus?.isConnected && !focus.closest("[hidden]")) focus.focus();
      else $("vehicle").focus();
    }
  }
}
function table(parent, title, headers, rows) {
  const wrap = node("div", null, parent);
  wrap.className = "table-wrap";
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute("aria-label", title);
  const t = node("table", null, wrap);
  node("caption", title, t);
  const head = node("tr", null, node("thead", null, t));
  headers.forEach((h) => {
    const th = node("th", h, head);
    th.scope = "col";
  });
  const b = node("tbody", null, t);
  if (!rows.length) {
    const cell = node("td", "No records yet.", node("tr", null, b));
    cell.colSpan = headers.length;
  }
  rows.forEach((row) => {
    const tr = node("tr", null, b);
    row.forEach((value) => {
      const cell = node("td", null, tr);
      if (value instanceof Node) cell.append(value);
      else cell.textContent = value;
    });
  });
}
function recordActions(kind, record, vehicle, path, description) {
  const group = node("div");
  const edit = node("button", "Edit", group);
  edit.dataset.editId = record.id;
  edit.setAttribute("aria-label", `Edit ${description}`);
  edit.onclick = () => editRecord(kind, record, vehicle, edit);
  group.append(deleteButton(path, description));
  return group;
}
function editRecord(kind, record, vehicle, trigger) {
  const dialog = node("dialog", null, document.body);
  dialog.setAttribute("aria-labelledby", "edit-title");
  node("h2", `Edit ${vehicle.registration} ${kind}`, dialog).id = "edit-title";
  const errors = node("div", null, dialog);
  errors.setAttribute("role", "alert");
  errors.tabIndex = -1;
  const form = node("form", null, dialog);
  form.id = "edit-record";
  const fields = specs[kind + "-form"].filter(([name]) => name !== "fuel_tank_litres");
  if (kind === "fuel") fields.push(["price_per_litre_pence", "Price per litre (pence, optional)", "number"]);
  for (const [name, title, type = "text", required = false] of fields) {
    const label = node("label", title, form);
    const input = node(type === "select" ? "select" : "input", null, label);
    input.name = name;
    input.required = required;
    input.id = "edit-" + name;
    if (type === "select") categories.forEach(c => { const o = node("option", c, input); o.value = c; });
    else input.type = type === "checkbox" ? "checkbox" : type === "date" ? "date" : "text";
    if (type === "checkbox") input.checked = record[name];
    else input.value = record[name] == null ? "" : type === "money" ? editMoney(record, name) : record[name];
  }
  const save = node("button", "Save changes", form);
  const cancel = node("button", "Cancel", form);
  cancel.type = "button";
  const draft = () => JSON.stringify(fields.map(([n,,t]) => t === "checkbox" ? form.elements[n].checked : form.elements[n].value));
  const initial = draft();
  let saving = false;
  function close() {
    if (saving) return;
    if (draft() !== initial) {
      errors.replaceChildren();
      node("p", "Discard changes?", errors);
      const keep = node("button", "Keep editing", errors);
      keep.type = "button";
      const discard = node("button", "Discard changes", errors);
      discard.type = "button";
      keep.onclick = () => { errors.replaceChildren(); form.querySelector("input,select").focus(); };
      discard.onclick = () => dialog.close();
      keep.focus();
      return;
    }
    dialog.close();
  }
  cancel.onclick = close;
  dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
  dialog.addEventListener("close", () => { dialog.remove(); if (trigger.isConnected) trigger.focus(); });
  form.onsubmit = async event => {
    event.preventDefault();
    if (saving) return;
    errors.replaceChildren();
    try {
      const body = {};
      for (const [name,,type = "text"] of fields) {
        const input = form.elements[name];
        if (type === "money") {
          body[name] = input.value === editMoney(record, name)
            ? BigInt(record[name + "_exact"] ?? record[name]) : pence(input.value);
        } else {
          body[name] = type === "checkbox" ? input.checked : input.value === "" ? null
            : ["number", "integer"].includes(type) ? Number(input.value) : input.value;
        }
      }
      // Omitting an untouched unit price lets the shared service preserve nulls
      // or derive from changed cost/quantity. Explicit clearing requests derivation.
      if (kind === "fuel" && body.price_per_litre_pence === record.price_per_litre_pence)
        delete body.price_per_litre_pence;
      saving = true;
      save.disabled = true;
      cancel.disabled = true;
      errors.textContent = "Saving…";
      await api(`/${kind === "fuel" ? "fuel" : "expenses"}/${encodeURIComponent(record.id)}`, "PUT", body);
    } catch (error) {
      errors.textContent = error.message || "Save could not be confirmed. Refresh before trying again.";
      for (const [path, message] of Object.entries(error.fields || {})) {
        const name = path.replace(/^body\./, "");
        const input = form.elements.namedItem(name);
        if (input) {
          input.setAttribute("aria-invalid", "true");
          const link = node("a", `${name}: ${message}`, node("p", null, errors));
          link.href = "#" + input.id;
          link.onclick = e => { e.preventDefault(); input.focus(); };
        }
      }
      errors.focus();
      saving = false;
      save.disabled = false;
      cancel.disabled = false;
      return;
    }
    dialog.close();
    try {
      resetHistory();
      await load(vehicle.id, true);
      const replacement = [...$(kind + "-list").querySelectorAll("[data-edit-id]")].find(b => b.dataset.editId === record.id);
      if (replacement) replacement.focus();
      else { $(kind + "-list").tabIndex = -1; $(kind + "-list").focus(); }
      $("status").textContent = `${kind === "fuel" ? "Fuel" : "Expense"} updated.${replacement ? "" : " Record is outside this view."}`;
    } catch (_) { $("status").textContent = "Saved. Could not refresh totals; refresh to see current values."; }
  };
  dialog.showModal();
  form.querySelector("input,select").focus();
}
function deleteButton(path, description) {
  const b = node("button", "Delete");
  b.className = "danger";
  b.setAttribute("aria-label", `Delete ${description}`);
  b.onclick = () => confirmDelete(path, description);
  return b;
}
async function confirmDelete(path, description) {
  $("confirm-text").textContent =
    `Delete ${description}? This cannot be undone.`;
  const dialog = $("confirm");
  dialog.returnValue = "cancel";
  dialog.showModal();
  dialog.addEventListener(
    "close",
    () => {
      if (dialog.returnValue === "delete")
        mutate(null, async () => {
          await api(path, "DELETE");
          resetHistory();
          await load(path.startsWith("/vehicles/") ? "" : $("vehicle").value);
          $("vehicle").focus();
        });
    },
    { once: true },
  );
}
// Charts consume the same unmodified summary rows as the monthly table.
function monthlyChart(parent, rows, key, title, scope, format) {
  const figure = node("figure", null, parent);
  figure.className = "monthly-chart";
  node("figcaption", `${title} · ${scope}`, figure);
  const available = rows.filter((r) => r[key] != null);
  node("p", rows.length
    ? `${available.length} of ${rows.length} periods have data. Bars start at zero. Exact values follow in the monthly table.`
    : "No monthly data for this scope.", figure);
  const link = node("a", "View monthly values", figure);
  link.href = "#monthly-values";
  if (!rows.length) return;
  const max = Math.max(0, ...available.map((r) => r[key]));
  const plot = node("div", null, figure);
  // The semantic table and figure summary provide the accessible equivalent.
  plot.setAttribute("aria-hidden", "true");
  const scale = node("div", null, plot);
  scale.className = "chart-scale";
  node("span", format(0), scale);
  node("span", format(max), scale);
  rows.forEach((r) => {
    const row = node("div", null, plot);
    row.className = "chart-row";
    node("span", r.period, row);
    const track = node("div", null, row);
    track.className = "chart-track";
    if (r[key] != null) {
      const bar = node("div", null, track);
      bar.className = "chart-bar";
      bar.style.width = `${max ? r[key] / max * 100 : 0}%`;
    }
    node("span", r[key] == null ? "No reading/data" : format(r[key]), row);
  });
}
function renderSummary(s) {
  $("metrics").replaceChildren();
  const o = s.overall;
  const reasons = {
    no_driven_distance: "Add an odometer reading above the initial mileage.",
    missing_purchase_price:
      "Add the vehicle purchase price to calculate ownership cost.",
    no_fuel_history:
      "No fuel history. Record a full fill, then a later full fill at higher mileage.",
    no_closed_segment:
      "Record a later full fill at higher mileage to close a segment.",
    invalid_full_interval:
      "Full fills have no valid positive-distance interval. Check readings and record a later full fill at higher mileage.",
  };
  const cost = (value, codes) =>
    value == null
      ? `Not available — ${(codes || []).map((code) => reasons[code]).join(" ")}`
      : number(value, " p");
  [
    ["Total spending", money(o.total_spend_pence)],
    ["Fuel", money(o.fuel_spend_pence)],
    ["Other expenses", money(o.non_fuel_spend_pence)],
    ["Distance", number(o.miles_driven, " miles")],
    [
      "Running cost / mile",
      cost(o.running_cost_per_mile_pence, o.running_unavailable_reasons),
    ],
    [
      "Ownership cost / mile",
      cost(o.ownership_cost_per_mile_pence, o.ownership_unavailable_reasons),
    ],
    [
      "Average UK MPG",
      s.mpg
        ? number(s.mpg.average_mpg)
        : $("vehicle").value
          ? `Not available — ${reasons[s.mpg_context?.reason]}`
          : "Not available — Select a vehicle to view UK MPG.",
    ],
  ].forEach(([title, value]) => {
    const card = node("div", title, $("metrics"));
    node("strong", value, card);
  });
  if (s.mpg_context) {
    const details = node("details", null, $("metrics"));
    node("summary", "How UK MPG was calculated", details);
    node(
      "p",
      "A full fill establishes the baseline; its fuel is excluded. Partial fills after it and the closing full fill are included. A later full fill at higher mileage closes a segment. One imperial gallon = 4.54609 litres. MPG = miles / imperial gallons.",
      details,
    );
    node("p", s.mpg_context.aggregation, details);
    const segments = s.mpg_context.segments;
    if (segments.length) {
      node(
        "p",
        `Average interval: ${segments[0].start_date} to ${segments[segments.length - 1].date}; ${segments.length} closed segments.`,
        details,
      );
    }
    for (const segment of segments) {
      node(
        "p",
        `${segment.start_date} (${segment.start_odometer_miles} miles) to ${segment.date} (${segment.end_odometer_miles} miles): ${segment.miles} miles; ${segment.litres} litres; ${number(segment.imperial_gallons)} imperial gallons; ${number(segment.uk_mpg)} UK MPG.`,
        details,
      );
    }
  }
  const root = $("summaries");
  root.replaceChildren();
  const scope = `${$("context").textContent} · ${$("year").value} · ${$("inactive").checked ? "including sold and archived" : "active vehicles only"}`;
  const charts = node("div", null, root);
  charts.className = "monthly-charts";
  monthlyChart(charts, s.monthly, "total_spend_pence", "Monthly spending (GBP)", scope, money);
  monthlyChart(charts, s.monthly, "miles_driven", "Monthly mileage (miles)", scope, (v) => number(v, " miles"));
  for (const [key, title] of [
    ["monthly", `Monthly · ${$("year").value}`],
    ["annual", "Annual · all years"],
  ]) {
    const col = node("div", null, root);
    if (key === "monthly") {
      col.id = "monthly-values";
      col.tabIndex = -1;
      node("p", `Monthly values · ${scope}. Scroll for more columns if needed.`, col);
    }
    table(
      col,
      title,
      ["Period", "Spending", "Miles"],
      s[key].map((r) => [
        r.period,
        money(r.total_spend_pence),
        r.miles_driven == null ? "No reading/data" : number(r.miles_driven),
      ]),
    );
  }
  const col = node("div", null, root);
  table(
    col,
    "Categories · all time",
    ["Category", "Spending"],
    s.categories.map((r) => [r.category, money(r.amount_pence)]),
  );
  const rolling = node("div", null, root);
  table(
    rolling,
    "Average monthly spending",
    ["Window", "Average"],
    [
      ["All months", money(s.rolling.all_months_average_pence)],
      ...[3, 6, 12].map((n) => [
        `Last ${n} months`,
        money(s.rolling[`last_${n}_months_average_pence`]),
      ]),
    ],
  );
}
// Each table owns its filters and page. SQL offsets are stable on unchanged data;
// Refresh restarts traversal after external changes. Summaries have separate scope.
const history = {};
for (const kind of ["fuel", "expense"]) {
  const state = (history[kind] = {
    offset: 0,
    filters: {},
    token: 0,
    more: false,
    loading: false,
  });
  const host = $(kind + "-list");
  const form = node("form", null, host);
  form.id = kind + "-filters";
  form.className = "fields";
  for (const [name, label] of [
    ["date_from", "From date"],
    ["date_to", "To date"],
  ]) {
    const input = node("input", null, node("label", label, form));
    input.type = "date";
    input.name = name;
    input.id = kind + "-" + name;
  }
  if (kind === "expense") {
    const select = node("select", null, node("label", "Category", form));
    select.name = "category";
    const all = node("option", "All categories", select);
    all.value = "";
    categories.forEach((c) => {
      node("option", c, select).value = c;
    });
  }
  node("button", "Apply filters", form);
  const clear = node("button", "Clear filters", form);
  clear.type = "button";
  clear.onclick = () => {
    form.reset();
    state.filters = {};
    state.offset = 0;
    loadHistory(kind);
  };
  form.onsubmit = (event) => {
    event.preventDefault();
    clearError();
    const values = Object.fromEntries(new FormData(form));
    if (
      values.date_from &&
      values.date_to &&
      values.date_from > values.date_to
    ) {
      showError(
        {
          message: "From date must not follow To date.",
          fields: { date_from: "Choose a date on or before To date." },
        },
        form,
      );
      return;
    }
    state.filters = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v),
    );
    state.offset = 0;
    loadHistory(kind);
  };
  const heading = node("h3", "History", host);
  heading.id = kind + "-range";
  heading.tabIndex = -1;
  const scope = node("p", null, host);
  scope.id = kind + "-scope";
  state.results = node("div", null, host);
  const nav = node("nav", null, host);
  nav.setAttribute("aria-label", kind + " pagination");
  for (const [direction, text] of [
    [-1, "Previous"],
    [1, "Next"],
  ]) {
    const button = node("button", text, nav);
    button.id = kind + (direction < 0 ? "-previous" : "-next");
    button.onclick = () => {
      state.offset += direction * 50;
      loadHistory(kind, button);
    };
  }
  node(
    "p",
    "History may change in other windows. Refresh restarts from page one.",
    host,
  );
}
function resetHistory() {
  for (const state of Object.values(history)) {
    state.offset = 0;
    state.token++;
  }
}
function updatePageButtons() {
  for (const [kind, state] of Object.entries(history)) {
    $(kind + "-previous").disabled = state.loading || state.offset === 0;
    $(kind + "-next").disabled = state.loading || !state.more;
  }
}
async function loadHistory(kind, trigger) {
  clearError();
  const state = history[kind],
    token = ++state.token,
    contextToken = generation;
  const vehicle = $("vehicle").value;
  if (!vehicle) return;
  const v = vehicles.find((v) => v.id === vehicle);
  state.loading = true;
  updatePageButtons();
  const endpoint = kind === "fuel" ? "fuel" : "expenses";
  const query = new URLSearchParams({
    ...state.filters,
    limit: "50",
    offset: String(state.offset),
    page: "true",
  });
  $(kind + "-range").textContent = "Loading history…";
  try {
    const page = await api(
      `/vehicles/${encodeURIComponent(vehicle)}/${endpoint}?${query}`,
    );
    if (token !== state.token || contextToken !== generation) return;
    state.more = page.has_next;
    state.results.replaceChildren();
    const rows = page.items;
    const label = rows.length
      ? `${state.offset + 1}–${state.offset + rows.length} ${endpoint}`
      : `0 ${endpoint}`;
    $(kind + "-range").textContent = label;
    $(kind + "-scope").textContent = [
      v.registration,
      state.filters.date_from
        ? "From " + state.filters.date_from
        : "All start dates",
      state.filters.date_to ? "To " + state.filters.date_to : "All end dates",
      state.filters.category || (kind === "expense" ? "All categories" : ""),
    ]
      .filter(Boolean)
      .join(" · ");
    if (!rows.length)
      node(
        "p",
        Object.keys(state.filters).length
          ? `No ${endpoint} match these filters. Use Clear filters.`
          : `No ${endpoint} recorded for this vehicle. Add a record above.`,
        state.results,
      );
    else
      table(
        state.results,
        endpoint + " · newest date then ID first",
        kind === "fuel"
          ? ["Date", "Miles", "Litres", "Cost", "Tank", "Action"]
          : ["Date", "Category", "Description", "Cost", "Action"],
        rows.map((r) => [
          ...(kind === "fuel"
            ? [
                r.date,
                number(r.odometer_miles),
                number(r.litres),
                money(r.total_cost_pence),
                r.is_full_tank ? "Full" : "Partial",
              ]
            : [
                r.date,
                r.category,
                r.description || "—",
                money(r.amount_pence),
              ]),
          recordActions(kind, r, v,
            `/${endpoint}/${encodeURIComponent(r.id)}`,
            `${v.registration} ${kind} on ${r.date}`,
          ),
        ]),
      );
    $("status").textContent = label + " loaded.";
    return true;
  } catch (error) {
    if (token !== state.token || contextToken !== generation) return;
    $(kind + "-range").textContent =
      "History is not current. Use Refresh to retry.";
    state.more = false;
    showError(error, $(kind + "-filters"));
    return false;
  } finally {
    if (token === state.token) {
      state.loading = false;
      updatePageButtons();
      if (trigger && $("error").hidden)
        (trigger.disabled ? $(kind + "-range") : trigger).focus();
    }
  }
}
async function load(preferred = $("vehicle").value, propagate = false) {
  const token = ++generation;
  clearError();
  $("status").textContent = "Loading…";
  $("metrics").replaceChildren();
  $("summaries").replaceChildren();
  $("records").hidden = true;
  $("vehicle-actions").hidden = true;
  $("reminder-list").replaceChildren();
  $("add-reminder").disabled = true;
  try {
    const include = $("inactive").checked;
    // Read the complete garage to distinguish inactive history from no vehicles.
    const all = await api("/vehicles?include_inactive=true");
    const list = include ? all : all.filter((v) => v.status === "ACTIVE");
    if (token !== generation) return;
    if (initialContext) {
      const active = all.filter((v) => v.status === "ACTIVE");
      if (active.length === 1) preferred = active[0].id;
      initialContext = false;
    }
    const unavailable = preferred && !list.some((v) => v.id === preferred);
    vehicles = list;
    $("creation").hidden = false;
    $("creation-heading").textContent = all.length ? "Vehicles" : "Add your first vehicle";
    $("add-vehicle").hidden = !all.length;
    if (!$("vehicle-dialog").open) {
      const target = all.length ? $("vehicle-dialog") : $("creation-inline");
      target.append($("vehicle-help"), $("vehicle-form"));
    }
    const select = $("vehicle");
    select.replaceChildren();
    const fleet = node(
      "option",
      include ? "All vehicles" : "Active fleet",
      select,
    );
    fleet.value = "";
    vehicles.forEach((v) => {
      const option = node(
        "option",
        `${v.registration}${v.nickname ? " · " + v.nickname : ""} · ${v.status}`,
        select,
      );
      option.value = v.id;
    });
    select.value = vehicles.some((v) => v.id === preferred) ? preferred : "";
    const id = select.value;
    const v = vehicles.find((v) => v.id === id);
    $("context").textContent = v
      ? `${v.registration} · ${v.status}`
      : include
        ? "All vehicles"
        : "Active fleet";
    $("vehicle-detail").textContent = v
      ? [
          v.make,
          v.model,
          v.year,
          v.fuel_tank_litres
            ? `${v.fuel_tank_litres} litre tank`
            : "Tank capacity not set",
        ]
          .filter(Boolean)
          .join(" · ")
      : vehicles.length
        ? "Select a vehicle for its records."
        : all.length
          ? "No active vehicles. Include sold and archived vehicles to view history, or add a vehicle."
          : "Your garage is empty. Add your first vehicle below.";
    const query = new URLSearchParams({
      include_inactive: String(include),
      year: $("year").value,
    });
    if (id) query.set("vehicle_id", id);
    const summary = await api("/summary?" + query);
    if (token !== generation) return;
    renderSummary(summary);
    await loadReminders(token);
    if (token !== generation) return;
    $("records").hidden = !id;
    $("record-hint").hidden = !!id;
    $("vehicle-actions").hidden = !id;
    if (id) {
      $("tank-form").elements.fuel_tank_litres.value = v.fuel_tank_litres || "";
      const loaded = await Promise.all([
        loadHistory("fuel"),
        loadHistory("expense"),
      ]);
      if (token !== generation) return;
      if (loaded.some((result) => result === false))
        throw new Error(
          "Could not load current history. Use Refresh to retry.",
        );
    }
    $("status").textContent = unavailable
      ? "Selected vehicle is no longer available in this scope. Showing fleet. Up to date."
      : "Up to date.";
  } catch (e) {
    if (token === generation) {
      showError(e);
      $("status").textContent =
        "Could not load current data. Use Refresh to try again.";
      if (busy || propagate) throw e;
    }
  }
}
$("vehicle-errors").setAttribute("role", "alert");
$("vehicle-errors").tabIndex = -1;
$("add-vehicle").onclick = () => {
  clearError();
  $("vehicle-dialog").showModal();
  $("vehicle-form-registration").focus();
};
$("cancel-vehicle").onclick = () => $("vehicle-dialog").close("cancel");
$("vehicle-dialog").addEventListener("close", () => {
  if ($("vehicle-dialog").returnValue !== "saved") $("add-vehicle").focus();
});
$("vehicle").onchange = () => {
  resetHistory();
  load();
};
$("inactive").onchange = () => {
  resetHistory();
  load();
};
$("refresh").onclick = () => {
  resetHistory();
  load();
};
$("year").value = new Date().getFullYear();
$("year").onchange = () => {
  if ($("year").checkValidity() && $("year").value) load();
  else $("year").reportValidity();
};
$("delete-vehicle").onclick = () => {
  const v = vehicles.find((v) => v.id === $("vehicle").value);
  if (v)
    confirmDelete(
      `/vehicles/${encodeURIComponent(v.id)}`,
      `${v.registration} and ALL its fuel and expense records`,
    );
};
document.querySelectorAll("[data-status]").forEach(
  (b) =>
    (b.onclick = () =>
      mutate(null, async () => {
        await api(
          `/vehicles/${encodeURIComponent($("vehicle").value)}`,
          "PATCH",
          { status: b.dataset.status },
        );
        await load();
      })),
);
$("tank-form").onsubmit = (e) => {
  e.preventDefault();
  mutate($("tank-form"), async () => {
    await api(`/vehicles/${encodeURIComponent($("vehicle").value)}`, "PATCH", {
      fuel_tank_litres: Number($("tank-form").elements.fuel_tank_litres.value),
    });
    await load();
  });
};
load();

// Downloads always cover the database, independently of dashboard context.
document.querySelectorAll("[data-download]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (button.getAttribute("aria-disabled") === "true") return;
    button.setAttribute("aria-disabled", "true");
    $("download-error").textContent = "";
    $("download-status").textContent = "Preparing download…";
    let url;
    try {
      const kind =
        button.dataset.download === "csv"
          ? $("csv-record-type").value
          : button.dataset.download;
      const response = await fetch(`/api/downloads/${kind}`);
      if (!response.ok)
        throw new Error("Could not prepare download. Try again.");
      const blob = await response.blob();
      url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = response.headers
        .get("Content-Disposition")
        .match(/filename="([^"]+)"/)[1];
      document.body.append(link);
      link.click();
      link.remove();
      $("download-status").textContent =
        "Download prepared; check your browser downloads.";
    } catch (error) {
      $("download-status").textContent = "";
      $("download-error").textContent = error.message;
    } finally {
      button.removeAttribute("aria-disabled");
      if (url) setTimeout(() => URL.revokeObjectURL(url), 60000);
    }
  });
});

const reminderForm = $("reminder-form"),
  reminderDialog = $("reminder-dialog");
let reminderMode,
  reminderRow,
  reminderTrigger,
  reminderSaving = false,
  reminderDraft;
categories.forEach((c) => {
  node("option", c, reminderForm.elements.category).value = c;
});
function reminderError(error) {
  const box = $("reminder-error");
  box.replaceChildren();
  box.hidden = false;
  node(
    "p",
    error.message ||
      "Save could not be confirmed. Refresh before trying again.",
    box,
  );
  reminderForm
    .querySelectorAll("[aria-invalid]")
    .forEach((el) => el.removeAttribute("aria-invalid"));
  for (const [path, message] of Object.entries(error.fields || {})) {
    const name = path.replace(/^body\./, "").replace(/^next_/, "");
    const input = reminderForm.elements.namedItem(name);
    if (input) {
      input.setAttribute("aria-invalid", "true");
      const link = node("a", message, box);
      link.href = "#" + input.id;
      link.onclick = (event) => {
        event.preventDefault();
        input.focus();
      };
    }
  }
  box.focus();
}
for (const input of reminderForm.querySelectorAll("input,select"))
  input.id = "reminder-" + input.name;
function openReminder(mode, row, trigger) {
  reminderMode = mode;
  reminderRow = row;
  reminderTrigger = trigger;
  reminderForm.reset();
  $("reminder-error").hidden = true;
  reminderForm
    .querySelectorAll("[aria-invalid]")
    .forEach((el) => el.removeAttribute("aria-invalid"));
  const completing = mode === "complete";
  $("reminder-details").hidden = completing;
  reminderForm.elements.title.required = !completing;
  for (const name of ["title", "category", "due_date", "due_mileage"])
    if (row && !completing) reminderForm.elements[name].value = row[name] ?? "";
  $("reminder-dialog-heading").textContent =
    `${completing ? "Complete" : mode === "edit" ? "Edit" : "Add"} reminder · ${vehicles.find((v) => v.id === (row?.vehicle_id || $("vehicle").value))?.registration || "vehicle"}`;
  $("reminder-save").textContent = completing
    ? "Complete reminder"
    : "Save reminder";
  $("reminder-dialog-hint").textContent = completing
    ? "Optional next thresholds create a new occurrence. Blank completes only; history is retained."
    : "Supply at least one due date or due mileage. Both are retained when supplied.";
  reminderDraft = JSON.stringify(
    Object.fromEntries(new FormData(reminderForm)),
  );
  reminderDialog.showModal();
  (completing
    ? reminderForm.elements.due_date
    : reminderForm.elements.title
  ).focus();
}
function cancelReminder(event) {
  if (event) event.preventDefault();
  if (reminderSaving) return;
  if (
    JSON.stringify(Object.fromEntries(new FormData(reminderForm))) !==
      reminderDraft &&
    !window.confirm("Discard reminder changes?")
  )
    return;
  reminderDialog.close();
}
$("reminder-cancel").onclick = cancelReminder;
reminderDialog.addEventListener("cancel", cancelReminder);
reminderDialog.addEventListener("close", () => {
  if (reminderTrigger?.isConnected) reminderTrigger.focus();
  else $("reminder-heading").focus();
});
$("add-reminder").onclick = (event) =>
  openReminder("add", null, event.currentTarget);
reminderForm.onsubmit = async (event) => {
  event.preventDefault();
  if (reminderSaving) return;
  const date = reminderForm.elements.due_date.value || null;
  const rawMiles = reminderForm.elements.due_mileage.value;
  const miles = rawMiles === "" ? null : Number(rawMiles);
  if (miles !== null && (!Number.isSafeInteger(miles) || miles < 0)) {
    reminderError({
      message: "Use a nonnegative safe whole number.",
      fields: { due_mileage: "Check due mileage" },
    });
    return;
  }
  if (reminderMode !== "complete" && date === null && miles === null) {
    reminderError({
      message: "Supply at least one due threshold.",
      fields: { due_date: "Add a due date or mileage" },
    });
    return;
  }
  reminderSaving = true;
  $("reminder-save").setAttribute("aria-disabled", "true");
  let wrote = false;
  try {
    const path =
      reminderMode === "add"
        ? `/vehicles/${encodeURIComponent($("vehicle").value)}/reminders`
        : `/reminders/${encodeURIComponent(reminderRow.id)}${reminderMode === "complete" ? "/complete" : ""}`;
    const body =
      reminderMode === "complete"
        ? { next_due_date: date, next_due_mileage: miles }
        : {
            title: reminderForm.elements.title.value,
            category: reminderForm.elements.category.value,
            due_date: date,
            due_mileage: miles,
          };
    await api(path, reminderMode === "edit" ? "PUT" : "POST", body);
    wrote = true;
    reminderDialog.close();
    await loadReminders(generation);
    $("reminder-heading").focus();
    $("status").textContent =
      reminderMode === "complete"
        ? "Reminder completed; history retained."
        : "Reminder saved.";
  } catch (error) {
    if (wrote) {
      showError(
        new Error(
          "Saved. Could not refresh reminders; use Refresh to see current values.",
        ),
      );
    } else reminderError(error);
  } finally {
    reminderSaving = false;
    $("reminder-save").removeAttribute("aria-disabled");
  }
};
async function loadReminders(token) {
  const query = new URLSearchParams({
    include_inactive: String($("inactive").checked),
  });
  if ($("vehicle").value) query.set("vehicle_id", $("vehicle").value);
  const rows = await api("/reminders?" + query);
  if (token !== generation) return;
  $("add-reminder").disabled = !$("vehicle").value;
  $("reminder-hint").hidden = !!$("vehicle").value;
  const root = $("reminder-list");
  root.replaceChildren();
  for (const [status, label] of [
    ["due", "Due"],
    ["upcoming", "Upcoming"],
    ["unknown", "Mileage status unknown"],
    ["later", "Later"],
    ["completed", "Completed"],
  ]) {
    node("h3", label, root);
    const group = rows.filter((item) => item.status === status);
    if (!group.length)
      node(
        "p",
        status === "completed"
          ? "No completed reminders."
          : "No reminders in this group.",
        root,
      );
    for (const item of group) {
      const r = item.reminder,
        reading = item.reading;
      const article = node("article", null, root);
      node(
        "h4",
        `${item.registration} · ${item.vehicle_status} · ${r.title}`,
        article,
      );
      node(
        "p",
        `${r.category} · ${label} · Due date: ${r.due_date ?? "not set"} · Due odometer: ${r.due_mileage ?? "not set"} miles`,
        article,
      );
      node(
        "p",
        `Latest recorded mileage: ${reading.miles} miles; date: ${reading.date ?? "unknown"}; source: ${reading.source}. ${reading.message}`,
        article,
      );
      if (r.completed_at)
        node(
          "p",
          `Completed: ${r.completed_at}${r.previous_id ? " · Previous occurrence: " + r.previous_id : ""}`,
          article,
        );
      if (!r.completed_at)
        for (const mode of ["edit", "complete"]) {
          const button = node(
            "button",
            mode === "edit" ? "Edit" : "Complete",
            article,
          );
          button.setAttribute(
            "aria-label",
            `${mode === "edit" ? "Edit" : "Complete"} reminder ${r.title} for ${item.registration}`,
          );
          button.onclick = () => openReminder(mode, r, button);
        }
      const remove = node("button", "Delete", article);
      remove.className = "danger";
      remove.setAttribute(
        "aria-label",
        `Delete reminder ${r.title} for ${item.registration}`,
      );
      remove.onclick = () => {
        const dialog = $("confirm");
        $("confirm-text").textContent =
          `Delete reminder ${r.title} for ${item.registration}? This cannot be undone.`;
        dialog.returnValue = "cancel";
        dialog.showModal();
        dialog.addEventListener(
          "close",
          async () => {
            if (dialog.returnValue !== "delete") {
              remove.focus();
              return;
            }
            remove.disabled = true;
            let wrote = false;
            try {
              await api(`/reminders/${encodeURIComponent(r.id)}`, "DELETE");
              wrote = true;
              await loadReminders(generation);
              $("reminder-heading").focus();
              $("status").textContent = "Reminder deleted.";
            } catch (error) {
              showError(
                wrote
                  ? new Error(
                      "Deleted. Could not refresh reminders; use Refresh.",
                    )
                  : error,
              );
              remove.disabled = false;
            }
          },
          { once: true },
        );
      };
    }
  }
  if (!rows.length)
    node(
      "p",
      "No reminders yet. Select a vehicle and choose Add reminder.",
      root,
    );
}
