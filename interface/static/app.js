"use strict";

const form = document.querySelector("#upload-form");
const fileInput = document.querySelector("#file-input");
const fileName = document.querySelector("#file-name");
const fieldSelect = document.querySelector("#field-select");
const fieldLabel = document.querySelector("#field-label");
const vocabFile = document.querySelector("#vocab-file");
const threshold = document.querySelector("#threshold");
const thresholdValue = document.querySelector("#threshold-value");
const notice = document.querySelector("#status-message");
const analysisProgress = document.querySelector("#analysis-progress");
const analysisProgressBar = document.querySelector("#analysis-progress-bar");
const analysisProgressValue = document.querySelector("#analysis-progress-value");
const warnings = document.querySelector("#warnings");
const workspace = document.querySelector("#workspace");
const jobSummary = document.querySelector("#job-summary");
const progressList = document.querySelector("#progress-list");
const currentReview = document.querySelector("#current-review");
const candidateList = document.querySelector("#candidate-list");
const targetTerm = document.querySelector("#target-term");
const targetUri = document.querySelector("#target-uri");
const goButton = document.querySelector("#go-button");
const selectionCount = document.querySelector("#selection-count");
const exportPanel = document.querySelector("#export-panel");
const exportSummary = document.querySelector("#export-summary");
const dataFormat = document.querySelector("#data-format");
const logFormat = document.querySelector("#log-format");
const reportFormat = document.querySelector("#report-format");
let activeJobId = null;
let currentStep = null;
let selectedVariants = new Set();
let busy = false;

function showNotice(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
  notice.hidden = false;
}

function showProgress(fraction) {
  const percent = Math.round(Math.min(Math.max(fraction, 0), 1) * 100);
  analysisProgressBar.value = percent;
  analysisProgressValue.value = `${percent} %`;
  analysisProgress.hidden = false;
}

function setBusy(value) {
  busy = value;
  fieldSelect.disabled = value;
  goButton.disabled = value;
  form.querySelector('button[type="submit"]').disabled = value;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Anfrage fehlgeschlagen (${response.status}).`);
  }
  return payload;
}

fieldSelect.addEventListener("change", () => {
  const option = fieldSelect.selectedOptions[0];
  fieldLabel.textContent = option.dataset.label;
  vocabFile.textContent = option.dataset.vocab;
});

threshold.addEventListener("input", () => {
  thresholdValue.value = Number(threshold.value).toFixed(2);
});

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files.length ? fileInput.files[0].name : "Datei auswählen oder hier ablegen";
});

const dropTarget = document.querySelector(".file-picker");
dropTarget.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropTarget.classList.add("dragging");
});
dropTarget.addEventListener("dragleave", () => dropTarget.classList.remove("dragging"));
dropTarget.addEventListener("drop", (event) => {
  event.preventDefault();
  dropTarget.classList.remove("dragging");
  if (event.dataTransfer.files.length) {
    fileInput.files = event.dataTransfer.files;
    fileInput.dispatchEvent(new Event("change"));
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length || busy) return;
  currentStep = null;
  selectedVariants = new Set();
  workspace.hidden = true;
  warnings.hidden = true;
  warnings.replaceChildren();
  exportPanel.hidden = true;
  currentReview.hidden = true;
  const body = new FormData(form); // vor setBusy: deaktivierte Felder (field) würden fehlen
  setBusy(true);
  showNotice("Datei wird hochgeladen und analysiert …");
  showProgress(0);
  try {
    const result = await requestJson("/api/upload", { method: "POST", body });
    activeJobId = result.job_id;
    await pollJob();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    analysisProgress.hidden = true;
    setBusy(false);
  }
});

async function pollJob() {
  while (activeJobId) {
    const state = await requestJson(`/api/jobs/${encodeURIComponent(activeJobId)}`);
    if (state.status === "error") throw new Error(state.message);
    if (state.status === "ready") {
      showProgress(1); // letzte Poll-Antwort lag meist unter 100 % – Balken vollständig füllen
      await new Promise((resolve) => window.setTimeout(resolve, 600));
      workspace.hidden = false;
      renderState(state);
      showNotice(state.finished ? "Analyse abgeschlossen. Sie können die Ergebnisse exportieren." : "Analyse abgeschlossen. Prüfen Sie die Vorschläge.");
      return;
    }
    showNotice(state.message || "Analyse läuft …");
    showProgress(state.progress || 0);
    await new Promise((resolve) => window.setTimeout(resolve, 800));
  }
}

function renderState(state) {
  const stats = state.stats;
  jobSummary.textContent = `${state.filename} · ${stats.records} Datensätze · ${stats.distinct_values} unterschiedliche Werte · ${stats.candidates} Vorschläge`;

  warnings.replaceChildren();
  for (const warning of state.warnings || []) {
    const item = document.createElement("li");
    item.textContent = warning;
    warnings.append(item);
  }
  warnings.hidden = !state.warnings?.length;

  progressList.replaceChildren();
  for (const [index, step] of state.steps.entries()) {
    if (step.state === "skipped") continue; // nur Begriffe mit Änderungsvorschlägen anzeigen
    const item = document.createElement("li");
    item.className = step.state;
    if (index === state.current) item.classList.add("active");
    const dot = document.createElement("span");
    dot.className = "progress-dot";
    dot.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = step.term;
    item.append(dot, label);
    item.title = step.state === "skipped" ? `${step.term} – keine Kandidaten` : step.term;
    progressList.append(item);
  }

  if (state.finished) {
    currentReview.hidden = true;
    document.querySelector(".review-actions").hidden = true;
    exportPanel.hidden = false;
    exportSummary.textContent = `${state.changes} Änderungen in ${state.records_changed} Datensätzen. Die vollständigen Datensätze sowie das Änderungsprotokoll werden exportiert.`;
    return;
  }

  document.querySelector(".review-actions").hidden = false;
  exportPanel.hidden = true;
  const step = state.current_step;
  if (!step) {
    currentReview.hidden = true;
    return;
  }
  if (currentStep !== step.index) {
    currentStep = step.index;
    selectedVariants = new Set();
  }
  targetTerm.textContent = step.term;
  if (step.uri) {
    targetUri.href = step.uri;
    targetUri.textContent = step.uri;
    targetUri.hidden = false;
  } else {
    targetUri.removeAttribute("href");
    targetUri.textContent = "";
    targetUri.hidden = true;
  }
  candidateList.replaceChildren();
  for (const candidate of step.candidates) {
    candidateList.append(makeCandidateCard(candidate, step.index));
  }
  currentReview.hidden = false;
  updateSelection();
}

function makeIdItem(entry) {
  const item = document.createElement("li");
  if (/^https?:\/\//i.test(entry.url || "")) {
    const link = document.createElement("a");
    link.href = entry.url;
    link.textContent = entry.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.title = `ID: ${entry.id}`;
    item.append(link);
  } else {
    item.textContent = entry.id; // kein Link vorhanden: ID anzeigen
  }
  return item;
}

function makeCandidateCard(candidate, stepIndex) {
  const card = document.createElement("article");
  card.className = "candidate-card";
  const label = document.createElement("label");
  label.className = "candidate-choice";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = selectedVariants.has(candidate.variant);
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) selectedVariants.add(candidate.variant);
    else selectedVariants.delete(candidate.variant);
    card.classList.toggle("selected", checkbox.checked);
    updateSelection();
  });
  const term = document.createElement("span");
  term.textContent = candidate.variant;
  label.append(checkbox, term);
  const details = document.createElement("details");
  details.className = "candidate-meta";
  const summary = document.createElement("summary");
  summary.textContent = `${candidate.id_total} Treffer · Ähnlichkeit ${Number(candidate.score).toFixed(3)}`;
  const ids = document.createElement("ol");
  for (const entry of candidate.ids_preview || []) ids.append(makeIdItem(entry));
  details.append(summary, ids);
  if (candidate.id_total > (candidate.ids_preview || []).length) {
    details.addEventListener("toggle", async () => {
      if (!details.open || details.dataset.loaded) return;
      try {
        const query = new URLSearchParams({ step: String(stepIndex), variant: candidate.variant });
        const result = await requestJson(`/api/jobs/${encodeURIComponent(activeJobId)}/ids?${query}`);
        ids.replaceChildren();
        for (const entry of result.ids) ids.append(makeIdItem(entry));
        details.dataset.loaded = "true";
      } catch (error) {
        const message = document.createElement("li");
        message.textContent = `IDs konnten nicht geladen werden: ${error.message}`;
        ids.append(message);
      }
    });
  }
  card.append(label, details);
  card.classList.toggle("selected", checkbox.checked);
  return card;
}

function updateSelection() {
  selectionCount.textContent = selectedVariants.size
    ? `${selectedVariants.size} ${selectedVariants.size === 1 ? "Variante" : "Varianten"} ausgewählt`
    : "Keine Varianten ausgewählt – Sie können unverändert weitergehen";
  goButton.disabled = busy;
  goButton.textContent = selectedVariants.size ? "Auswahl übernehmen und weiter" : "Ohne Änderungen weiter";
}

goButton.addEventListener("click", async () => {
  if (!activeJobId || busy) return;
  setBusy(true);
  showNotice("Auswahl wird übernommen …");
  try {
    const result = await requestJson(`/api/jobs/${encodeURIComponent(activeJobId)}/go`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected: [...selectedVariants] }),
    });
    renderState(result.state);
    showNotice(result.state.finished ? "Alle Begriffe sind geprüft." : "Änderungen übernommen. Weiter zum nächsten Begriff.");
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    setBusy(false);
  }
});

for (const [buttonId, kind] of [["download-data", "data"], ["download-log", "log"], ["download-zip", "zip"]]) {
  document.querySelector(`#${buttonId}`).addEventListener("click", () => {
    const params = new URLSearchParams({ data_format: dataFormat.value, log_format: logFormat.value });
    window.location.assign(`/api/jobs/${encodeURIComponent(activeJobId)}/export/${kind}?${params}`);
  });
}

document.querySelector("#download-report").addEventListener("click", () => {
  const params = new URLSearchParams({ format: reportFormat.value });
  window.location.assign(`/api/jobs/${encodeURIComponent(activeJobId)}/export/report?${params}`);
});
