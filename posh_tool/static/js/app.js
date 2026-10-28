/**
 * POSH IC & Company Research Hub - Frontend Logic
 * Strictly implements modern web guidance for accessibility, ARIA sync, and sticky tables.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const form = document.getElementById("research-form");
  const inputCity = document.getElementById("input-city");
  const inputArea = document.getElementById("input-area");
  const inputCount = document.getElementById("input-count");
  const inputIndustry = document.getElementById("input-industry");
  const checkAutoContinue = document.getElementById("check-auto-continue");

  const btnStart = document.getElementById("btn-start");
  const btnContinue = document.getElementById("btn-continue");
  const btnStop = document.getElementById("btn-stop");
  const btnDownloadTop = document.getElementById("btn-download-top");
  const btnDownloadBottom = document.getElementById("btn-download-bottom");
  const btnDownloadAlert = document.getElementById("btn-download-alert");

  const badgeStatus = document.getElementById("system-status-badge");
  const headerProgressBadge = document.getElementById("header-progress-badge");
  const badgePctLarge = document.getElementById("badge-pct-large");
  const valProgressPctBold = document.getElementById("val-progress-pct-bold");
  const resultsPctBadge = document.getElementById("results-pct-badge");

  const taskAlertBanner = document.getElementById("task-alert-banner");
  const alertBannerTitle = document.getElementById("alert-banner-title");
  const alertBannerMsg = document.getElementById("alert-banner-msg");

  const valDelivered = document.getElementById("val-delivered");
  const progressBar = document.getElementById("progress-bar");
  const valProgressPct = document.getElementById("val-progress-pct");
  const valIcEmail = document.getElementById("val-ic-email");
  const valIcEmailPct = document.getElementById("val-ic-email-pct");
  const valIcDoc = document.getElementById("val-ic-doc");
  const valIcDocPct = document.getElementById("val-ic-doc-pct");
  const valHrContact = document.getElementById("val-hr-contact");
  const valHrContactPct = document.getElementById("val-hr-contact-pct");
  const valExcluded = document.getElementById("val-excluded");

  const consoleOutput = document.getElementById("console-output");
  const btnClearConsole = document.getElementById("btn-clear-console");
  const btnToggleConsole = document.getElementById("btn-toggle-console");

  const companiesTableBody = document.getElementById("companies-table-body");
  const excludedTableBody = document.getElementById("excluded-table-body");
  const sourcesList = document.getElementById("sources-list");
  const filterInput = document.getElementById("filter-input");

  const countBadgeCompanies = document.getElementById("count-badge-companies");
  const countBadgeExcluded = document.getElementById("count-badge-excluded");
  const countBadgeSources = document.getElementById("count-badge-sources");

  // State
  let currentDownloadFilename = null;
  let pollInterval = null;
  let allCompanies = [];
  let loggedEntriesCount = 0;

  // ARIA sync for modern form validation (:user-invalid)
  const syncAria = (el) => {
    if (el && el.matches) {
      el.setAttribute("aria-invalid", el.matches(":user-invalid") ? "true" : "false");
    }
  };
  document.addEventListener("blur", (e) => syncAria(e.target), true);
  document.addEventListener("input", (e) => {
    if (e.target && e.target.hasAttribute && e.target.hasAttribute("aria-invalid")) {
      syncAria(e.target);
    }
  });

  // Tab switching
  const tabs = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      panels.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      const targetPanel = document.getElementById(tab.getAttribute('aria-controls'));
      if (targetPanel) {
        targetPanel.classList.add('active');
      }
    });
  });

  // Console controls
  btnClearConsole.addEventListener('click', () => {
    consoleOutput.innerHTML = '';
  });

  btnToggleConsole.addEventListener('click', () => {
    consoleOutput.classList.toggle('collapsed');
    btnToggleConsole.textContent = consoleOutput.classList.contains('collapsed') ? 'Expand' : 'Collapse';
  });

  // Start Research Submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const payload = {
      city: inputCity.value.trim(),
      area: inputArea.value.trim() || "Whole city",
      count: parseInt(inputCount.value, 10) || 25,
      industry: inputIndustry.value.trim() || "Any",
      batch_size: 25,
      auto_continue: checkAutoContinue.checked
    };

    try {
      btnStart.disabled = true;
      btnStop.disabled = false;
      appendLog(`Submitting research request for ${payload.city}...`, "info");

      const res = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success) {
        appendLog(`Task initiated successfully! Target: ${payload.count} companies in ${payload.city}.`, "success");
        startPolling();
      } else {
        appendLog(`Error starting task: ${data.error}`, "error");
        btnStart.disabled = false;
        btnStop.disabled = true;
      }
    } catch (err) {
      appendLog(`Network error: ${err.message}`, "error");
      btnStart.disabled = false;
      btnStop.disabled = true;
    }
  });

  // Continue Batch
  btnContinue.addEventListener("click", async () => {
    try {
      btnContinue.disabled = true;
      const res = await fetch("/api/continue", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        appendLog("Resumed next batch as requested.", "info");
        btnContinue.style.display = "none";
      }
    } catch (err) {
      appendLog(`Failed to continue: ${err.message}`, "error");
    }
  });

  // Stop Task
  btnStop.addEventListener("click", async () => {
    try {
      btnStop.disabled = true;
      appendLog("Requesting cancellation...", "warning");
      await fetch("/api/stop", { method: "POST" });
    } catch (err) {
      appendLog(`Error stopping task: ${err.message}`, "error");
    }
  });

  // Downloads
  const triggerDownload = () => {
    if (currentDownloadFilename) {
      window.location.href = `/api/download/${encodeURIComponent(currentDownloadFilename)}`;
    } else {
      window.location.href = `/api/download-latest`;
    }
  };
  btnDownloadTop.addEventListener("click", triggerDownload);
  btnDownloadBottom.addEventListener("click", triggerDownload);
  if (btnDownloadAlert) {
    btnDownloadAlert.addEventListener("click", triggerDownload);
  }

  // Filter Table
  filterInput.addEventListener("input", () => {
    const q = filterInput.value.toLowerCase().trim();
    const rows = companiesTableBody.querySelectorAll("tr:not(.empty-row)");
    rows.forEach(r => {
      const text = r.textContent.toLowerCase();
      r.style.display = text.includes(q) ? "" : "none";
    });
  });

  // Polling loop
  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchStatus, 1500);
    fetchStatus();
  }

  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const status = await res.json();

      updateUI(status);

      if (status.status === "completed" || status.status === "stopped" || status.status === "error") {
        btnStart.disabled = false;
        btnStop.disabled = true;
        btnContinue.style.display = "none";
      } else if (status.status === "paused") {
        btnStart.disabled = true;
        btnStop.disabled = false;
        btnContinue.style.display = "inline-flex";
        btnContinue.disabled = false;
      } else if (status.status === "running") {
        btnStart.disabled = true;
        btnStop.disabled = false;
        btnContinue.style.display = "none";
      }
    } catch (err) {
      console.error("Poll error:", err);
    }
  }

  function updateUI(data) {
    // Status Badge
    badgeStatus.textContent = data.status.toUpperCase();
    badgeStatus.className = `badge badge-status badge-${data.status}`;

    // Metrics & Progress Calculations
    const delivered = data.delivered_count || 0;
    const target = data.target_count || 0;
    valDelivered.textContent = `${delivered} / ${target}`;

    const pctFloat = target > 0 ? (delivered / target) * 100 : 0;
    const pctInt = Math.min(100, Math.round(pctFloat));
    const pctStr = `${pctInt}%`;
    const pctDetailedStr = `${pctFloat.toFixed(1)}%`;

    // Update all progress percentage displays in HTML
    if (progressBar) progressBar.style.inlineSize = `${pctInt}%`;
    if (valProgressPct) valProgressPct.textContent = `${pctDetailedStr} of target completed (Batch ${data.batch_no || 1})`;
    if (headerProgressBadge) {
      headerProgressBadge.textContent = `${pctInt}% Complete`;
      headerProgressBadge.style.display = target > 0 ? "inline-flex" : "none";
    }
    if (badgePctLarge) badgePctLarge.textContent = pctStr;
    if (valProgressPctBold) valProgressPctBold.textContent = pctDetailedStr;
    if (resultsPctBadge) resultsPctBadge.textContent = `${pctInt}% Complete (${delivered}/${target})`;

    // Live Browser Tab Title with Progress Percentage
    if (data.status === "running") {
      document.title = `(${pctInt}%) POSH IC Research Hub`;
    } else if (data.status === "completed") {
      document.title = `(100% Done) POSH IC Research Hub`;
    } else if (data.status === "paused") {
      document.title = `(Paused ${pctInt}%) POSH IC Research Hub`;
    } else if (data.status === "error") {
      document.title = `(Interrupted - Excel Saved) POSH IC Research Hub`;
    } else {
      document.title = `POSH IC & Compliance Research Hub (Zero AI)`;
    }

    // Alert Banner handling (Guarantees Excel is always accessible even on failure/stop)
    if (taskAlertBanner) {
      if (data.status === "error") {
        taskAlertBanner.className = "alert-banner alert-danger";
        if (alertBannerTitle) alertBannerTitle.textContent = "Research Interrupted";
        if (alertBannerMsg) {
          alertBannerMsg.textContent = `${data.error_message || "An issue occurred."} All ${delivered} verified companies gathered so far are safely preserved in Excel.`;
        }
        taskAlertBanner.style.display = "flex";
      } else if (data.status === "stopped") {
        taskAlertBanner.className = "alert-banner alert-warning";
        if (alertBannerTitle) alertBannerTitle.textContent = "Research Paused / Stopped";
        if (alertBannerMsg) {
          alertBannerMsg.textContent = `Search stopped by user. All ${delivered} verified companies gathered so far are safely preserved in Excel.`;
        }
        taskAlertBanner.style.display = "flex";
      } else {
        taskAlertBanner.style.display = "none";
      }
    }

    if (data.gaps) {
      const icEmailFound = data.gaps.ic_email?.found || 0;
      valIcEmail.textContent = icEmailFound;
      valIcEmailPct.textContent = delivered > 0 ? `${((icEmailFound / delivered) * 100).toFixed(1)}% rate` : "0% rate";

      const icDocFound = data.gaps.ic_doc?.found || 0;
      valIcDoc.textContent = icDocFound;
      valIcDocPct.textContent = delivered > 0 ? `${((icDocFound / delivered) * 100).toFixed(1)}% rate` : "0% rate";

      const hrEmailFound = data.gaps.hr_email?.found || 0;
      valHrContact.textContent = hrEmailFound;
      valHrContactPct.textContent = delivered > 0 ? `${((hrEmailFound / delivered) * 100).toFixed(1)}% rate` : "0% rate";
    }

    valExcluded.textContent = data.excluded_count || 0;

    // Excel file download: ALWAYS enabled if file exists or if rows were verified
    if (data.excel_exists || delivered > 0) {
      currentDownloadFilename = data.excel_filename;
      btnDownloadTop.disabled = false;
      btnDownloadBottom.disabled = false;
      if (btnDownloadAlert) btnDownloadAlert.disabled = false;

      const downloadLabel = delivered > 0 
        ? `Download Excel (${delivered} Saved)` 
        : `Download Excel (.xlsx)`;

      btnDownloadTop.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        ${downloadLabel}`;
      
      btnDownloadBottom.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        ${downloadLabel}`;

      btnDownloadTop.title = `Download ${data.excel_filename || 'Excel workbook'}`;
      btnDownloadBottom.title = `Download ${data.excel_filename || 'Excel workbook'}`;
    }

    // Append Logs
    if (data.logs && data.logs.length > loggedEntriesCount) {
      const newLogs = data.logs.slice(loggedEntriesCount);
      newLogs.forEach(entry => {
        appendLog(`[${entry.time}] ${entry.msg}`, entry.level);
      });
      loggedEntriesCount = data.logs.length;
    }

    // Update Tables
    if (data.companies && data.companies.length !== allCompanies.length) {
      allCompanies = data.companies;
      renderCompaniesTable(allCompanies);
    }
    countBadgeCompanies.textContent = allCompanies.length;

    renderExcludedTable(data.excluded || []);
    countBadgeExcluded.textContent = (data.excluded || []).length;

    renderSourcesList(data.sources || []);
    countBadgeSources.textContent = (data.sources || []).length;
  }

  function appendLog(text, level = "info") {
    const div = document.createElement("div");
    div.className = `log-entry log-${level}`;
    div.textContent = text;
    consoleOutput.appendChild(div);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
  }

  function renderCompaniesTable(companies) {
    if (!companies || companies.length === 0) {
      companiesTableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="21" class="text-center">No companies gathered yet. Start a research task above to populate.</td>
        </tr>`;
      return;
    }

    let html = "";
    companies.forEach((c, idx) => {
      const formatCell = (val, isLink = false, isLegal = false) => {
        if (!val || val === "Not available") {
          return `<span class="pill-badge pill-na">Not available</span>`;
        }
        if (isLink && (val.startsWith("http://") || val.startsWith("https://"))) {
          return `<a href="${encodeURI(val)}" target="_blank" rel="noopener noreferrer">${escapeHtml(val)}</a>`;
        }
        if (isLegal) {
          return `<span class="pill-badge pill-legal">${escapeHtml(val)}</span>`;
        }
        return escapeHtml(val);
      };

      html += `
        <tr>
          <th scope="row">${c["#"] || idx + 1}</th>
          <td><strong>${escapeHtml(c["Company name"] || "Unknown")}</strong></td>
          <td>${formatCell(c["Legal form (Pvt Ltd / LLP / Listed / Not confirmed)"], false, true)}</td>
          <td>${formatCell(c["Full address with PIN"])}</td>
          <td>${formatCell(c["Company website"], true)}</td>
          <td>${formatCell(c["Company public phone number"])}</td>
          <td>${formatCell(c["Company public email ID"])}</td>
          <td>${formatCell(c["POSH / IC web page link"], true)}</td>
          <td>${formatCell(c["IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)"], true)}</td>
          <td>${formatCell(c["Where IC details were found (document name + page/section)"])}</td>
          <td>${formatCell(c["IC presiding officer / member name(s) (as published)"])}</td>
          <td>${formatCell(c["IC email ID"])}</td>
          <td>${formatCell(c["IC phone / mobile number"])}</td>
          <td>${formatCell(c["HR contact name (as published, if any)"])}</td>
          <td>${formatCell(c["HR email ID"])}</td>
          <td>${formatCell(c["HR phone number"])}</td>
          <td>${formatCell(c["Employee count evidence"])}</td>
          <td>${formatCell(c["Source URL(s)"], true)}</td>
          <td>${formatCell(c["Date of source / date checked"])}</td>
          <td>${c["Batch no."] || 1}</td>
          <td>${formatCell(c["Notes"])}</td>
        </tr>
      `;
    });

    companiesTableBody.innerHTML = html;
  }

  function renderExcludedTable(excluded) {
    if (!excluded || excluded.length === 0) {
      excludedTableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="3" class="text-center">No excluded companies recorded yet.</td>
        </tr>`;
      return;
    }

    let html = "";
    excluded.forEach((exc, idx) => {
      html += `
        <tr>
          <td>${idx + 1}</td>
          <td><strong>${escapeHtml(exc.name || "Unknown")}</strong></td>
          <td><span class="pill-badge pill-na">${escapeHtml(exc.reason || "Did not qualify")}</span></td>
        </tr>
      `;
    });
    excludedTableBody.innerHTML = html;
  }

  function renderSourcesList(sources) {
    if (!sources || sources.length === 0) {
      sourcesList.innerHTML = `<li class="empty-item">No sources collected yet.</li>`;
      return;
    }

    let html = "";
    sources.forEach(s => {
      html += `<li><a href="${encodeURI(s)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s)}</a></li>`;
    });
    sourcesList.innerHTML = html;
  }

  function escapeHtml(str) {
    if (typeof str !== "string") str = String(str);
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initial check on load
  fetchStatus();
});

