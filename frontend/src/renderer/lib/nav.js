// Shared module list + sidebar builder. Used by the post-login launcher
// (app.js) and by the per-screen shell (screen-shell.js) so the sidebar is
// identical everywhere. Order confirmed with the client (BRD entry 106).
// RBAC here is a convenience (which links a role even sees) - the backend
// enforces the real rule independently on every write (SDD non-negotiable).
// daily-trial-balance's roles were widened 2026-09-06 for ADR-2's maker-checker
// model; see that screen's own canFinalize() for the finer-grained gate.

import { apiBase } from "./api.js";

export const MODULES = [
  { key: "daily-sales-entry", label: "Daily Sales Entry", href: "screens/daily-sales-entry/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "daily-sales-summary", label: "Daily Sales Summary", href: "screens/daily-sales-summary/index.html", roles: ["Sales", "Manager", "Owner"] },
  // ADR-2, confirmed 2026-09-06: Sales is the maker (entry/save); Close & Sign
  // Off (finalize) stays Manager/Owner only, gated inside the screen itself.
  { key: "daily-trial-balance", label: "Daily Trial Balance", href: "screens/daily-trial-balance/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "credit-remittance-master", label: "Credit / Remittance Master", href: "screens/credit-remittance-master/index.html", roles: ["Manager", "Owner"] },
  { key: "payment-receipt", label: "Payment Receipt", href: "screens/payment-receipt/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "inventory-tracking", label: "Inventory Tracking", href: "screens/inventory-tracking/index.html", roles: ["Manager", "Owner"] },
  { key: "rate-master", label: "Rate Master", href: "screens/rate-master/index.html", roles: ["Manager", "Owner"] },
  { key: "monthly-expenses", label: "Monthly Expenses", href: "screens/monthly-expenses/index.html", roles: ["Manager", "Owner"] },
  { key: "employee-master", label: "Employee Master", href: "screens/employee-master/index.html", roles: ["Manager", "Owner"] },
  { key: "yearly-sales-report", label: "Yearly Sales Report", href: "screens/yearly-sales-report/index.html", roles: ["Manager", "Owner"] },
];

// Renders after a divider, in its own "Admin" group.
export const ADMIN_MODULE = {
  key: "manage-users",
  label: "Manage Users",
  href: "screens/manage-users/index.html",
  roles: ["Manager", "Owner"],
};

const ICONS = {
  "daily-sales-entry": '<rect x="6" y="3" width="12" height="18" rx="2"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="13" y2="16"/>',
  "daily-sales-summary": '<line x1="4" y1="20" x2="20" y2="20"/><rect x="6" y="13" width="3" height="7"/><rect x="11" y="9" width="3" height="11"/><rect x="16" y="5" width="3" height="15"/>',
  "daily-trial-balance": '<line x1="12" y1="4" x2="12" y2="20"/><line x1="5" y1="8" x2="19" y2="8"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="12" r="3"/><line x1="8" y1="20" x2="16" y2="20"/>',
  "credit-remittance-master": '<rect x="3" y="6" width="18" height="13" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="6" y1="15" x2="10" y2="15"/>',
  "payment-receipt": '<path d="M6 3h12v16l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2-2 1.2Z"/><line x1="9" y1="7.5" x2="15" y2="7.5"/><path d="M9 12.5l1.5 1.5 3-3"/>',
  "inventory-tracking": '<path d="M12 3 20 7v10l-8 4-8-4V7Z"/><path d="M4 7l8 4 8-4"/><line x1="12" y1="11" x2="12" y2="21"/>',
  "rate-master": '<path d="M11 3H5a2 2 0 0 0-2 2v6l10 10 8-8L11 3Z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  "monthly-expenses": '<path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 10h16"/><circle cx="16" cy="14" r="1.3"/>',
  "employee-master": '<rect x="5" y="3" width="14" height="18" rx="2"/><circle cx="12" cy="10" r="2.6"/><path d="M8 17c.7-2 2-3 4-3s3.3 1 4 3"/>',
  "yearly-sales-report": '<rect x="3" y="5" width="18" height="15" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/><path d="M6.5 16l3-3 2.5 2 4.5-5"/>',
  "manage-users": '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5"/><circle cx="17" cy="9" r="2.4"/><path d="M15.5 14.2c2.6.3 4.5 2.2 4.5 5.3"/>',
};

function navLink(mod, hrefPrefix, activeKey) {
  const a = document.createElement("a");
  a.className = mod.key === activeKey ? "nav-item nav-item-active" : "nav-item";
  const sep = mod.href.includes("?") ? "&" : "?";
  a.href = `${hrefPrefix}${mod.href}${sep}apiBase=${encodeURIComponent(apiBase)}`;
  a.dataset.module = mod.key;
  a.innerHTML =
    `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[mod.key] || ""}</svg><span>${mod.label}</span>`;
  return a;
}

// Fill `container` (a <nav id="nav-links">) with role-filtered links.
// hrefPrefix: "" from the launcher, "../../" from a screen page.
export function buildNav(container, role, { activeKey = "", hrefPrefix = "" } = {}) {
  container.innerHTML = "";
  for (const mod of MODULES) {
    if (!mod.roles.includes(role)) continue;
    container.appendChild(navLink(mod, hrefPrefix, activeKey));
  }
  if (ADMIN_MODULE.roles.includes(role)) {
    const divider = document.createElement("div");
    divider.className = "nav-divider";
    container.appendChild(divider);
    const label = document.createElement("div");
    label.className = "nav-group-label";
    label.textContent = "Admin";
    container.appendChild(label);
    container.appendChild(navLink(ADMIN_MODULE, hrefPrefix, activeKey));
  }
}
