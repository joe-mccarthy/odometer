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
  document
    .querySelectorAll("button,input,select")
    .forEach((e) => (e.disabled = true));
  try {
    await action();
    $("status").textContent = "Saved. Current data refreshed.";
  } catch (e) {
    showError(e, form);
    $("status").textContent =
      "Changes were not confirmed. Check the error before trying again.";
  } finally {
    busy = false;
    document
      .querySelectorAll("button,input,select")
      .forEach((e) => (e.disabled = false));
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
    const [summary, fuel, expenses] = await Promise.all([
      api("/summary?" + query),
      id ? api(`/vehicles/${encodeURIComponent(id)}/fuel?limit=1000`) : [],
      id ? api(`/vehicles/${encodeURIComponent(id)}/expenses?limit=1000`) : [],
    ]);
    if (token !== generation) return;
    renderSummary(summary);
    $("records").hidden = !id;
    $("record-hint").hidden = !!id;
    $("vehicle-actions").hidden = !id;
    if (id) {
      $("tank-form").elements.fuel_tank_litres.value = v.fuel_tank_litres || "";
      for (const kind of ["fuel", "expense"])
        $(kind + "-list").replaceChildren();
      table(
        $("fuel-list"),
        "Fuel · newest first · up to 1,000 records",
        ["Date", "Miles", "Litres", "Cost", "Tank", "Action"],
        fuel.map((r) => [
          r.date,
          number(r.odometer_miles),
          number(r.litres),
          money(r.total_cost_pence),
          r.is_full_tank ? "Full" : "Partial",
          deleteButton(
            `/fuel/${encodeURIComponent(r.id)}`,
            `${v.registration} fuel on ${r.date}, ${money(r.total_cost_pence)}`,
          ),
        ]),
      );
      table(
        $("expense-list"),
        "Expenses · newest first · up to 1,000 records",
        ["Date", "Category", "Description", "Cost", "Action"],
        expenses.map((r) => [
          r.date,
          r.category,
          r.description || "—",
          money(r.amount_pence),
          deleteButton(
            `/expenses/${encodeURIComponent(r.id)}`,
            `${v.registration} ${r.category} on ${r.date}, ${money(r.amount_pence)}`,
          ),
        ]),
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
$("vehicle").onchange = () => load();
$("inactive").onchange = () => load();
$("refresh").onclick = () => load();
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
