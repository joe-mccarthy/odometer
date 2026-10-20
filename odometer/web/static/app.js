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
function node(tag, text, parent) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  if (parent) parent.append(el);
  return el;
}
let vehicles = [],
  generation = 0,
  busy = false;
function clearError() {
  $("error").hidden = true;
  document.querySelectorAll(".field-error").forEach((e) => e.remove());
  document.querySelectorAll("[aria-invalid]").forEach((e) => {
    e.removeAttribute("aria-invalid");
    e.removeAttribute("aria-describedby");
  });
}
function showError(error, form) {
  $("error").textContent =
    error.message || "Request failed. Check the local server and refresh.";
  $("error").hidden = false;
  for (const [path, message] of Object.entries(error.fields || {})) {
    const name = path.replace(/^body\./, "");
    const input = form?.elements.namedItem(name);
    if (input) {
      input.setAttribute("aria-invalid", "true");
      const hint = node("span", message, input.parentElement);
      hint.className = "field-error";
      hint.id = `${form.id}-${name}-error`;
      input.setAttribute("aria-describedby", hint.id);
    } else $("error").textContent += `\n${name}: ${message}`;
  }
  $("error").focus();
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api" + path, {
    method,
    cache: "no-store",
    headers:
      method === "GET"
        ? {}
        : { "Content-Type": "application/json", "X-Odometer-Request": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw data.error || new Error("Request failed");
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
      if (id === "vehicle-form") await load(result.id);
      else await load(selected);
    });
  });
}
async function mutate(form, action) {
  if (busy) return;
  busy = true;
  clearError();
  $("status").textContent = "Saving…";
  const focus = document.activeElement;
  document.querySelectorAll("button,input,select").forEach((e) => {
    e.dataset.wasDisabled = String(e.disabled);
    e.disabled = true;
  });
  try {
    await action();
    $("status").textContent = "Saved. Current data refreshed.";
  } catch (e) {
    showError(e, form);
    $("status").textContent =
      "Changes were not confirmed. Check the error before trying again.";
  } finally {
    busy = false;
    document.querySelectorAll("button,input,select").forEach((e) => {
      e.disabled = e.dataset.wasDisabled === "true";
    });
    updatePageButtons();
    if ($("error").hidden) {
      if (focus?.isConnected && !focus.closest("[hidden]")) focus.focus();
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
function renderSummary(s) {
  $("metrics").replaceChildren();
  const o = s.overall;
  [
    ["Total spending", money(o.total_spend_pence)],
    ["Fuel", money(o.fuel_spend_pence)],
    ["Other expenses", money(o.non_fuel_spend_pence)],
    ["Distance", number(o.miles_driven, " miles")],
    ["Running cost / mile", number(o.running_cost_per_mile_pence, " p")],
    ["Ownership cost / mile", number(o.ownership_cost_per_mile_pence, " p")],
    [
      "Average UK MPG",
      s.mpg
        ? number(s.mpg.average_mpg)
        : $("vehicle").value
          ? "Unavailable — needs two full fills"
          : "Unavailable — select a vehicle",
    ],
  ].forEach(([title, value]) => {
    const card = node("div", title, $("metrics"));
    node("strong", value, card);
  });
  const root = $("summaries");
  root.replaceChildren();
  for (const [key, title] of [
    ["monthly", `Monthly · ${$("year").value}`],
    ["annual", "Annual · all years"],
  ]) {
    const col = node("div", null, root);
    table(
      col,
      title,
      ["Period", "Spending", "Miles"],
      s[key].map((r) => [
        r.period,
        money(r.total_spend_pence),
        number(r.miles_driven),
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
          deleteButton(
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
async function load(preferred = $("vehicle").value) {
  const token = ++generation;
  clearError();
  $("status").textContent = "Loading…";
  $("metrics").replaceChildren();
  $("summaries").replaceChildren();
  $("records").hidden = true;
  $("vehicle-actions").hidden = true;
  try {
    const include = $("inactive").checked;
    const list = await api(`/vehicles?include_inactive=${include}`);
    if (token !== generation) return;
    vehicles = list;
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
        : "Your garage is empty. Add your first vehicle below.";
    const query = new URLSearchParams({
      include_inactive: String(include),
      year: $("year").value,
    });
    if (id) query.set("vehicle_id", id);
    const summary = await api("/summary?" + query);
    if (token !== generation) return;
    renderSummary(summary);
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
    $("status").textContent = "Up to date.";
  } catch (e) {
    if (token === generation) {
      showError(e);
      $("status").textContent =
        "Could not load current data. Use Refresh to try again.";
      if (busy) throw e;
    }
  }
}
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
