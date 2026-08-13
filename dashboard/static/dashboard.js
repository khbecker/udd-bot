"use strict";

// Sort order for the State column: things needing a human first.
const STATE_PRIORITY = {
  "merge-needed": 0,
  "sync-available": 1,
  "in-proposed": 2,
  "not-in-devel": 3,
  "autosync-pending": 4,
  "ubuntu-only": 5,
  "delta-current": 6,
  "ubuntu-ahead": 7,
  synced: 8,
};

const table = document.getElementById("pkgTable");
const tbody = table.querySelector("tbody");
const filterInput = document.getElementById("filter");
const stateFilter = document.getElementById("stateFilter");
const upstreamFilter = document.getElementById("upstreamFilter");
const componentFilter = document.getElementById("componentFilter");
const resetBtn = document.getElementById("resetBtn");
const countEl = document.getElementById("count");

const FILTERS = [filterInput, stateFilter, upstreamFilter, componentFilter];

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

function applyFilters() {
  const text = filterInput.value.toLowerCase().trim();
  const state = stateFilter.value;
  const upstream = upstreamFilter.value;
  const component = componentFilter.value;
  const rows = tbody.querySelectorAll("tr");
  let shown = 0;

  rows.forEach((row) => {
    let show = row.dataset.pkg.toLowerCase().includes(text);
    if (show && state === "__action") show = row.dataset.actionable === "yes";
    else if (show && state) show = row.dataset.state === state;
    if (show && upstream) show = row.dataset.upstream === upstream;
    if (show && component) show = row.dataset.component === component;
    row.hidden = !show;
    if (show) shown += 1;
  });

  countEl.textContent =
    shown === rows.length
      ? `Showing all ${rows.length} packages`
      : `Showing ${shown} of ${rows.length} packages`;
  syncUrl();
}

// Keep filters in the URL so a view can be shared.
function syncUrl() {
  const params = new URLSearchParams();
  if (filterInput.value.trim()) params.set("q", filterInput.value.trim());
  if (stateFilter.value) params.set("state", stateFilter.value);
  if (upstreamFilter.value) params.set("upstream", upstreamFilter.value);
  if (componentFilter.value) params.set("component", componentFilter.value);
  const qs = params.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function restoreFromUrl() {
  const params = new URLSearchParams(location.search);
  filterInput.value = params.get("q") || "";
  stateFilter.value = params.get("state") || "";
  upstreamFilter.value = params.get("upstream") || "";
  componentFilter.value = params.get("component") || "";
}

FILTERS.forEach((el) => {
  el.addEventListener("input", applyFilters);
  el.addEventListener("change", applyFilters);
});

resetBtn.addEventListener("click", () => {
  FILTERS.forEach((el) => {
    el.value = "";
  });
  applyFilters();
});

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

const SORT_COLUMN = {
  pkg: null, // uses the data attribute
  state: null,
  devel: 2,
  proposed: 3,
  debian: 4,
  lts: 5,
  upstream: 6,
  upload: 7,
};

function sortKey(row, kind) {
  if (kind === "pkg") return row.dataset.pkg;
  if (kind === "state") {
    return String(STATE_PRIORITY[row.dataset.state] ?? 99).padStart(2, "0");
  }
  if (kind === "upstream") {
    return row.dataset.upstream + row.children[SORT_COLUMN[kind]].textContent.trim();
  }
  const index = SORT_COLUMN[kind];
  return index === undefined ? "" : row.children[index].textContent.trim();
}

table.querySelectorAll("th[data-sort]").forEach((th) => {
  th.setAttribute("tabindex", "0");

  const sort = () => {
    // aria-sort is the accessible state, the caret Vanilla draws, and our
    // direction flag: one source of truth.
    const ascending = th.getAttribute("aria-sort") !== "ascending";
    table.querySelectorAll("th[data-sort]").forEach((other) => {
      other.removeAttribute("aria-sort");
    });
    th.setAttribute("aria-sort", ascending ? "ascending" : "descending");

    const kind = th.dataset.sort;
    const rows = Array.from(tbody.querySelectorAll("tr"));
    rows.sort((a, b) => {
      const cmp = collator.compare(sortKey(a, kind), sortKey(b, kind));
      return ascending ? cmp : -cmp;
    });
    const fragment = document.createDocumentFragment();
    rows.forEach((row) => fragment.appendChild(row));
    tbody.appendChild(fragment);
  };

  th.addEventListener("click", sort);
  th.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      sort();
    }
  });
});

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

const modal = document.getElementById("promptModal");
const modalTitle = document.getElementById("modalTitle");
const modalPrompt = document.getElementById("modalPrompt");
const copyBtn = document.getElementById("copyBtn");
let lastFocused = null;

function openModal() {
  lastFocused = document.activeElement;
  modal.style.display = "flex";
  document.getElementById("closeBtn").focus();
}

function closeModal() {
  modal.style.display = "none";
  copyBtn.textContent = "Copy to clipboard";
  if (lastFocused) lastFocused.focus();
}

document.getElementById("closeBtn").addEventListener("click", closeModal);
modal.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && modal.style.display !== "none") closeModal();
});

document.querySelectorAll("button.js-prompt").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const pkg = btn.dataset.promptPkg;
    const kind = btn.dataset.promptKind;
    // The ellipsis is a button affordance, not part of the action name.
    const label = btn.textContent.trim().replace(/…$/, "");
    modalTitle.textContent = `${pkg} — ${label}`;
    modalPrompt.textContent = "Loading…";
    openModal();
    try {
      const resp = await fetch(
        `/api/prompt/${encodeURIComponent(pkg)}?kind=${encodeURIComponent(kind)}`
      );
      const data = await resp.json();
      modalPrompt.textContent = data.prompt || data.error || "No prompt returned.";
    } catch (err) {
      modalPrompt.textContent = `Failed to load prompt: ${err}`;
    }
  });
});

copyBtn.addEventListener("click", () => {
  navigator.clipboard.writeText(modalPrompt.textContent).then(
    () => {
      copyBtn.textContent = "Copied";
      setTimeout(() => {
        copyBtn.textContent = "Copy to clipboard";
      }, 2000);
    },
    () => {
      copyBtn.textContent = "Copy failed";
    }
  );
});

restoreFromUrl();
applyFilters();
