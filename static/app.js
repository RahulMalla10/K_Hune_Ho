const topicInput = document.getElementById("topicInput");
const analyzeButton = document.getElementById("analyzeButton");
const causalCheckbox = document.getElementById("causalCheckbox");
const inputPanel = document.getElementById("inputPanel");
const progressPanel = document.getElementById("progressPanel");
const summaryPanel = document.getElementById("summaryPanel");
const summaryGrid = document.getElementById("summaryGrid");
const causalSection = document.getElementById("causalSection");
const causalContent = document.getElementById("causalContent");
const domainsSection = document.getElementById("domainsSection");
const domainsContent = document.getElementById("domainsContent");
const timelineSection = document.getElementById("timelineSection");
const timelineContent = document.getElementById("timelineContent");
const sourcesSection = document.getElementById("sourcesSection");
const sourcesContent = document.getElementById("sourcesContent");
const resultsRegion = document.getElementById("resultsRegion");
const downloadCompletePdfButton = document.getElementById("downloadCompletePdfButton");
const downloadFullReportPdfButton = document.getElementById("downloadFullReportPdfButton");
const pdfPreviewModal = document.getElementById("pdfPreviewModal");
const pdfPreviewBackdrop = document.getElementById("pdfPreviewBackdrop");
const pdfPreviewClose = document.getElementById("pdfPreviewClose");
const pdfPreviewCancel = document.getElementById("pdfPreviewCancel");
const pdfPreviewConfirm = document.getElementById("pdfPreviewConfirm");
const pdfPreviewTitle = document.getElementById("pdfPreviewTitle");
const pdfPreviewSubtitle = document.getElementById("pdfPreviewSubtitle");
const pdfPreviewBody = document.getElementById("pdfPreviewBody");
const progressStatus = document.getElementById("progressStatus");
const progressTitle = document.getElementById("progressTitle");
const progressBadge = document.getElementById("progressBadge");
const progressOverallFill = document.getElementById("progressOverallFill");
const cpuPercentText = document.getElementById("cpuPercentText");
const cpuUsageFill = document.getElementById("cpuUsageFill");
const cpuCoresText = document.getElementById("cpuCoresText");
const cpuSparkline = document.getElementById("cpuSparkline");
const gpuPercentText = document.getElementById("gpuPercentText");
const gpuUsageFill = document.getElementById("gpuUsageFill");
const gpuInfoText = document.getElementById("gpuInfoText");
const gpuModeLabel = document.getElementById("gpuModeLabel");
const cpuModeLabel = document.getElementById("cpuModeLabel");

const cpuHistory = [];
const gpuHistory = [];
const STATUS_HISTORY_LENGTH = 60;

const STEP_STATUS_TEXT = {
  active: {
    1: "Fetching articles from news sources…",
    2: "Routing topic to expert domains…",
    3: "Running causal trace analysis…",
    4: "Generating domain predictions…",
    5: "Building timeline and report…",
  },
};

let cpuChart, gpuChart;

function initializeCharts() {
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    animation: { duration: 0 },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        enabled: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        ticks: {
          color: '#888',
          font: { size: 11 },
        },
        grid: {
          color: '#2a2a2a',
          drawBorder: false,
        },
      },
      x: {
        display: false,
        grid: {
          display: false,
        },
      },
    },
  };

  // CPU Chart
  const cpuCtx = document.getElementById('cpuChart').getContext('2d');
  cpuChart = new Chart(cpuCtx, {
    type: 'line',
    data: {
      labels: Array(STATUS_HISTORY_LENGTH).fill(''),
      datasets: [{
        label: 'CPU %',
        data: cpuHistory,
        borderColor: '#2ecc71',
        backgroundColor: 'rgba(46, 204, 113, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 0,
      }],
    },
    options: chartOptions,
  });

  // GPU Chart
  const gpuCtx = document.getElementById('gpuChart').getContext('2d');
  gpuChart = new Chart(gpuCtx, {
    type: 'line',
    data: {
      labels: Array(STATUS_HISTORY_LENGTH).fill(''),
      datasets: [{
        label: 'GPU %',
        data: gpuHistory,
        borderColor: '#f39c12',
        backgroundColor: 'rgba(243, 156, 18, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 0,
      }],
    },
    options: chartOptions,
  });
}

function updateCharts() {
  if (cpuChart) {
    cpuChart.data.datasets[0].data = cpuHistory;
    cpuChart.update('none'); 
  }
  if (gpuChart) {
    gpuChart.data.datasets[0].data = gpuHistory;
    gpuChart.update('none');
  }
}

function updateStatusPanel(status) {
  const cpuPercent = typeof status.cpu_percent === "number" ? status.cpu_percent : 0;
  const gpuPercent = typeof status.gpu_utilization_percent === "number" ? status.gpu_utilization_percent : 0;

  cpuPercentText.textContent = `${cpuPercent.toFixed(0)}%`;
  cpuUsageFill.style.width = `${Math.min(100, Math.max(0, cpuPercent))}%`;
  cpuCoresText.textContent = `Cores: ${status.cpu_count_logical || "--"} (${status.cpu_count_physical || "--"} physical)`;
  cpuModeLabel.textContent = status.device === "cpu" ? "CPU" : "Mixed";

  gpuPercentText.textContent = status.gpu_available
    ? (typeof status.gpu_utilization_percent === "number" ? `${status.gpu_utilization_percent.toFixed(0)}%` : "N/A")
    : "Unavailable";
  gpuUsageFill.style.width = `${Math.min(100, Math.max(0, gpuPercent))}%`;
  gpuInfoText.textContent = `Type: ${status.gpu_type || "none"}`;
  gpuModeLabel.textContent = status.gpu_available ? status.gpu_type.toUpperCase() : "None";

  cpuHistory.push(cpuPercent);
  if (cpuHistory.length > STATUS_HISTORY_LENGTH) cpuHistory.shift();

  if (status.gpu_available && typeof status.gpu_utilization_percent === "number") {
    gpuHistory.push(status.gpu_utilization_percent);
  } else {
    gpuHistory.push(0);
  }
  if (gpuHistory.length > STATUS_HISTORY_LENGTH) gpuHistory.shift();

  updateCharts();
}

async function fetchDeviceStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const status = await res.json();
    updateStatusPanel(status);
  } catch (err) {
  }
}

initializeCharts();
setInterval(fetchDeviceStatus, 1000);
fetchDeviceStatus();

const STEP_HINT = {
  pending: "Waiting",
  active: "Running",
  completed: "Done",
  skipped: "Skipped",
  error: "Failed",
};

let lastAnalysisResult = null;
let pendingPdfKind = null;

analyzeButton.addEventListener("click", handleAnalyze);
downloadCompletePdfButton.addEventListener("click", () => openPdfPreview("complete"));
downloadFullReportPdfButton.addEventListener("click", () => openPdfPreview("full"));
pdfPreviewCancel.addEventListener("click", closePdfPreview);
pdfPreviewClose.addEventListener("click", closePdfPreview);
pdfPreviewBackdrop.addEventListener("click", closePdfPreview);
pdfPreviewConfirm.addEventListener("click", confirmPdfDownload);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && pendingPdfKind) closePdfPreview();
});

const STEP_LABELS = {
  1: "1",
  2: "2",
  3: "3",
  4: "4",
  5: "5",
};

const TOTAL_PROGRESS_STEPS = 5;

let currentActiveStep = 1;
let analyzeAbortController = null;

function setProgressPhase(phase, message) {
  progressPanel.classList.remove("is-running", "progress-success", "progress-failed");

  if (phase === "running") {
    progressPanel.classList.add("is-running");
    if (progressTitle) progressTitle.textContent = "Analysis in progress";
    if (progressBadge) {
      progressBadge.textContent = "Running";
      progressBadge.className = "progress-badge progress-badge--running";
    }
    if (progressStatus && message) {
      progressStatus.textContent = message;
      progressStatus.className = "progress-status is-active";
    }
    return;
  }

  if (phase === "success") {
    progressPanel.classList.add("progress-success");
    if (progressTitle) progressTitle.textContent = "Analysis complete";
    if (progressBadge) {
      progressBadge.textContent = "Success";
      progressBadge.className = "progress-badge progress-badge--success";
    }
    if (progressOverallFill) progressOverallFill.style.width = "100%";
    if (progressStatus) {
      progressStatus.textContent = message || "All steps finished successfully.";
      progressStatus.className = "progress-status is-success";
    }
    return;
  }

  if (phase === "error") {
    progressPanel.classList.add("progress-failed");
    if (progressTitle) progressTitle.textContent = "Analysis failed";
    if (progressBadge) {
      progressBadge.textContent = "Failed";
      progressBadge.className = "progress-badge progress-badge--error";
    }
    if (progressStatus) {
      progressStatus.textContent = message || "Something went wrong. Please try again.";
      progressStatus.className = "progress-status is-error";
    }
    return;
  }

  if (progressTitle) progressTitle.textContent = "Ready to analyze";
  if (progressBadge) {
    progressBadge.textContent = "Ready";
    progressBadge.className = "progress-badge progress-badge--idle";
  }
  if (progressOverallFill) progressOverallFill.style.width = "0%";
  if (progressStatus) {
    progressStatus.textContent = message || "Enter a topic and click Analyze.";
    progressStatus.className = "progress-status";
  }
}

function setOverallProgress(percent) {
  if (!progressOverallFill) return;
  const clamped = Math.min(100, Math.max(0, percent));
  progressOverallFill.style.width = `${clamped}%`;
}

function setStepHint(progressItem, status) {
  const hint = progressItem.querySelector(".progress-step-hint");
  if (hint) hint.textContent = STEP_HINT[status] || "";
}

function updateProgress(step, status = "active") {
  const progressItem = document.querySelector(`.progress-item[data-step="${step}"]`);
  if (!progressItem) return;

  const stepEl = progressItem.querySelector(".progress-step");
  progressItem.classList.remove("pending", "active", "completed", "error", "skipped");
  progressItem.classList.add(status === "pending" ? "pending" : status);
  progressItem.setAttribute("aria-busy", status === "active" ? "true" : "false");
  setStepHint(progressItem, status);

  if (status === "completed") {
    if (stepEl) {
      stepEl.innerHTML = '<span class="progress-icon progress-icon-success" aria-hidden="true">✓</span>';
    }
  } else if (status === "error") {
    if (stepEl) {
      stepEl.innerHTML = '<span class="progress-icon progress-icon-error" aria-hidden="true">✕</span>';
    }
  } else if (status === "active") {
    if (stepEl) {
      stepEl.replaceChildren();
      const spinner = document.createElement("span");
      spinner.className = "progress-spinner";
      spinner.setAttribute("aria-hidden", "true");
      stepEl.appendChild(spinner);
    }
    if (progressStatus) {
      progressStatus.textContent =
        STEP_STATUS_TEXT.active[step] || `Running step ${step}…`;
      progressStatus.className = "progress-status is-active";
    }
  } else if (status === "skipped") {
    if (stepEl) stepEl.textContent = "—";
  } else if (status === "pending" && stepEl) {
    stepEl.textContent = STEP_LABELS[step] || String(step);
  }

  const label = progressItem.querySelector(".progress-label")?.textContent || "Step";
  const ariaMap = {
    pending: `${label}: waiting`,
    active: `${label}: running`,
    completed: `${label}: completed`,
    skipped: `${label}: skipped`,
    error: `${label}: failed`,
  };
  progressItem.setAttribute("aria-label", ariaMap[status] || label);
}

function syncProgressSteps(activeStep, message) {
  for (let s = 1; s <= TOTAL_PROGRESS_STEPS; s += 1) {
    const item = document.querySelector(`.progress-item[data-step="${s}"]`);
    const isSkipped = item?.classList.contains("skipped");
    if (s < activeStep) {
      if (!isSkipped) updateProgress(s, "completed");
    } else if (s === activeStep) {
      updateProgress(s, "active");
    } else if (!isSkipped) {
      updateProgress(s, "pending");
    }
  }
  if (message && progressStatus) {
    progressStatus.textContent = message;
    progressStatus.className = "progress-status is-active";
  }
  const percent = Math.round(((activeStep - 1) / TOTAL_PROGRESS_STEPS) * 100);
  setOverallProgress(activeStep === 1 ? 8 : percent);
}

function advanceToNextStep(completedStep) {
  const next = completedStep + 1;
  if (next > TOTAL_PROGRESS_STEPS) return;
  currentActiveStep = next;
  syncProgressSteps(next);
  setOverallProgress(overallPercentForEvent({ step: next, status: "active" }));
}

function overallPercentForEvent(event) {
  const step = event.step || 1;
  if (event.status === "completed" || event.status === "skipped") {
    return (step / TOTAL_PROGRESS_STEPS) * 100;
  }
  if (event.status === "active") {
    if (step === 4 && event.domain_index && event.domain_total) {
      const base = ((step - 1) / TOTAL_PROGRESS_STEPS) * 100;
      const slice = 100 / TOTAL_PROGRESS_STEPS;
      return base + (slice * event.domain_index) / event.domain_total;
    }
    return ((step - 1) / TOTAL_PROGRESS_STEPS) * 100 + 6;
  }
  return 0;
}

function applyProgressEvent(event) {
  const step = event.step;
  const status = event.status;
  const message = event.message || "";

  if (status === "active") {
    currentActiveStep = step;
    syncProgressSteps(step, message);
    setOverallProgress(overallPercentForEvent(event));
    return;
  }

  if (status === "completed" || status === "skipped") {
    for (let s = 1; s < step; s += 1) {
      updateProgress(s, "completed");
    }
    updateProgress(step, status === "skipped" ? "skipped" : "completed");
    if (status === "skipped") {
      const item = document.querySelector(`.progress-item[data-step="${step}"]`);
      if (item) setStepHint(item, "skipped");
    }
    setOverallProgress(overallPercentForEvent(event));

    if (step < TOTAL_PROGRESS_STEPS) {
      advanceToNextStep(step);
    } else if (message && progressStatus) {
      progressStatus.textContent = message;
      progressStatus.className = "progress-status is-success";
    }
  }
}

function finishProgressSuccess() {
  for (let s = 1; s <= TOTAL_PROGRESS_STEPS; s += 1) {
    updateProgress(s, "completed");
  }
  currentActiveStep = TOTAL_PROGRESS_STEPS;
  setOverallProgress(100);
  setProgressPhase("success", "All steps finished successfully. Results are ready below.");
}

function finishProgressError(step, errorMessage) {
  const failedStep = Math.min(Math.max(step || currentActiveStep, 1), TOTAL_PROGRESS_STEPS);
  for (let s = 1; s < failedStep; s += 1) {
    updateProgress(s, "completed");
  }
  updateProgress(failedStep, "error");
  for (let s = failedStep + 1; s <= TOTAL_PROGRESS_STEPS; s += 1) {
    updateProgress(s, "pending");
    const item = document.querySelector(`.progress-item[data-step="${s}"]`);
    if (item) {
      item.classList.remove("completed", "active");
      item.classList.add("pending");
      setStepHint(item, "pending");
      const stepEl = item.querySelector(".progress-step");
      if (stepEl) stepEl.textContent = STEP_LABELS[s] || String(s);
    }
  }
  currentActiveStep = failedStep;
  const pct = Math.round(((failedStep - 1) / TOTAL_PROGRESS_STEPS) * 100);
  setOverallProgress(Math.max(pct, 12));
  setProgressPhase("error", errorMessage || `Step ${failedStep} failed. Please try again.`);
}

function setFormLocked(locked) {
  if (topicInput) {
    topicInput.disabled = locked;
    topicInput.readOnly = locked;
  }
  if (causalCheckbox) causalCheckbox.disabled = locked;
  if (analyzeButton) analyzeButton.disabled = locked;
  if (inputPanel) inputPanel.classList.toggle("is-locked", locked);
}

async function consumeAnalyzeStream(response) {
  if (!response.body) {
    throw new Error("Streaming is not supported in this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult = null;

  const handleLine = (line) => {
    const trimmed = line.trim();
    if (!trimmed || !trimmed.startsWith("{")) return;
    const event = JSON.parse(trimmed);
    if (event.type === "progress") {
      applyProgressEvent(event);
    } else if (event.type === "done") {
      finalResult = event.result;
    } else if (event.type === "error") {
      const err = new Error(event.message || "Analysis failed.");
      err.step = event.step || currentActiveStep;
      throw err;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    lines.forEach(handleLine);
  }

  if (buffer.trim()) handleLine(buffer);
  return finalResult;
}

function resetProgressSteps() {
  document.querySelectorAll(".progress-item").forEach((item) => {
    const step = item.getAttribute("data-step");
    const stepEl = item.querySelector(".progress-step");
    if (stepEl && step) {
      stepEl.textContent = STEP_LABELS[step] || step;
    }
    setStepHint(item, "pending");
  });
}

function clearProgress() {
  document.querySelectorAll(".progress-item").forEach((item) => {
    item.classList.remove("active", "completed", "error");
    item.classList.add("pending");
    item.removeAttribute("aria-busy");
    item.removeAttribute("aria-label");
  });
  resetProgressSteps();
  setProgressPhase("running", "Starting analysis…");
}

function setLoading(isLoading) {
  if (isLoading) {
    analyzeButton.textContent = "Analyzing...";
    progressPanel.classList.remove("hidden");
  } else {
    analyzeButton.textContent = "Analyze";
  }
}

function clearResults() {
  lastAnalysisResult = null;
  summaryGrid.innerHTML = "";
  causalContent.innerHTML = "";
  domainsContent.innerHTML = "";
  timelineContent.innerHTML = "";
  sourcesContent.innerHTML = "";
  causalSection.classList.add("hidden");
  domainsSection.classList.add("hidden");
  timelineSection.classList.add("hidden");
  sourcesSection.classList.add("hidden");
  resultsRegion.classList.add("hidden");
  downloadFullReportPdfButton.disabled = true;
  closePdfPreview();
}

function formatNumber(value) {
  return typeof value === "number" ? value.toLocaleString() : value;
}

function showResultsRegion() {
  resultsRegion.classList.remove("hidden");
}

function renderSummary(result) {
  showResultsRegion();
  summaryGrid.innerHTML = "";

  const items = [
    { title: "Topic", value: result.topic },
    { title: "Articles Found", value: formatNumber(result.article_count) },
    { title: "Active Domains", value: Object.keys(result.routed_domains || {}).length },
    { title: "Model Mode", value: result.model_mode === "low-power" ? "CPU Mode" : "GPU Mode" },
  ];

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `
      <h3>${item.title}</h3>
      <p class="summary-metric">${item.value}</p>
    `;
    summaryGrid.appendChild(card);
  });
}

function renderCausal(result) {
  if (!result.causal_chains || result.causal_chains.length === 0) {
    causalSection.classList.add("hidden");
    return;
  }

  causalSection.classList.remove("hidden");
  causalContent.innerHTML = "";
  result.causal_chains.forEach((chain) => {
    const item = document.createElement("div");
    item.className = "domain-card";
    const rank = chain.display_rank || chain.rank || "?";
    const confidence = Number(chain.confidence).toFixed(2);
    item.innerHTML = `
      <div class="domain-metadata">
        <span class="label-pill">Rank ${rank}</span>
        <span>Confidence: ${confidence}</span>
      </div>
      <p style="margin: 12px 0 0; font-size: 14px;">${chain.chain}</p>
    `;
    causalContent.appendChild(item);
  });
}

function renderDomains(result) {
  if (!result.agent_results || Object.keys(result.agent_results).length === 0) {
    domainsSection.classList.add("hidden");
    return;
  }

  domainsSection.classList.remove("hidden");
  domainsContent.innerHTML = "";
  const domainWeights = result.routed_domains || {};
  const domains = Object.entries(result.agent_results).sort((a, b) => {
    return (domainWeights[b[0]] || 0) - (domainWeights[a[0]] || 0);
  });

  domains.forEach(([domain, data]) => {
    const card = document.createElement("div");
    card.className = "domain-card";
    const weight = domainWeights[domain] ? Number(domainWeights[domain]).toFixed(2) : "-";
    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <h3>${domain.charAt(0).toUpperCase() + domain.slice(1)}</h3>
        <span class="label-pill">Weight ${weight}</span>
      </div>
    `;

    if (data.predictions && Array.isArray(data.predictions) && data.predictions.length > 0) {
      data.predictions.forEach((prediction) => {
        const item = document.createElement("div");
        item.className = "prediction-item";

        const extraFields = Object.entries(prediction)
          .filter(([key]) => !["prediction", "confidence", "timeline", "effective_confidence"].includes(key))
          .map(([key, value]) => `<div><strong>${key.replace(/_/g, " ")}:</strong> ${value || "N/A"}</div>`)
          .join("");

        item.innerHTML = `
          <p>${prediction.prediction || "N/A"}</p>
          <div class="prediction-meta">
            <span> Confidence: ${(prediction.confidence ?? "N/A")}</span>
            <span>📅 Timeline: ${prediction.timeline ?? "N/A"}</span>
            ${prediction.effective_confidence ? `<span>⚖️ Weighted: ${prediction.effective_confidence}</span>` : ""}
          </div>
          ${extraFields}
        `;
        card.appendChild(item);
      });
    } else {
      const errorMessage = data.error || "No predictions generated.";
      const errorBlock = document.createElement("div");
      errorBlock.className = "prediction-item";
      errorBlock.innerHTML = `<p><strong>${errorMessage}</strong></p>`;
      if (data.raw) {
        errorBlock.innerHTML += `<div style="color: var(--text-muted); font-size: 12px; margin-top: 8px;">${data.raw}</div>`;
      }
      card.appendChild(errorBlock);
    }

    domainsContent.appendChild(card);
  });
}

function renderTimeline(result) {
  if (!result.timeline || result.timeline.length === 0) {
    timelineSection.classList.add("hidden");
    return;
  }

  timelineSection.classList.remove("hidden");
  timelineContent.innerHTML = "";
  result.timeline.forEach((item) => {
    const line = document.createElement("li");
    line.innerHTML = `<strong>${item.date || "Unknown date"}</strong> — ${item.title}`;
    timelineContent.appendChild(line);
  });
}

function renderSources(result) {
  if (!result.articles || result.articles.length === 0) {
    sourcesSection.classList.add("hidden");
    return;
  }

  sourcesSection.classList.remove("hidden");
  sourcesContent.innerHTML = "";
  result.articles.forEach((article) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <a href="${article.url}" target="_blank" rel="noreferrer">${article.title}</a>
      <div class="prediction-meta" style="margin-top: 8px;">
        <span>📅 ${article.date || "Unknown date"}</span>
        <span> ${article.source || "Unknown source"}</span>
      </div>
    `;
    sourcesContent.appendChild(item);
  });
}

function updatePdfDownloadButtons(result) {
  const hasFullReport = Boolean(result?.report_text?.trim());
  downloadFullReportPdfButton.disabled = !hasFullReport;
}

function ensurePdfExportReady() {
  if (!window.KhunehoPdf || !window.jspdf) {
    alert("PDF export is unavailable. Please refresh the page.");
    return false;
  }
  return true;
}

function openPdfPreview(kind) {
  if (!lastAnalysisResult) {
    alert("No report available yet. Run an analysis first.");
    return;
  }
  if (!ensurePdfExportReady()) return;

  if (kind === "full" && !lastAnalysisResult.report_text?.trim()) {
    alert("No full analysis report is available for this run.");
    return;
  }

  pendingPdfKind = kind;
  const doc =
    kind === "complete"
      ? window.KhunehoPdf.buildCompleteDocument(lastAnalysisResult)
      : window.KhunehoPdf.buildFullDocument(lastAnalysisResult);

  pdfPreviewTitle.textContent =
    kind === "complete" ? "Complete report preview" : "Full analysis preview";
  pdfPreviewSubtitle.textContent = lastAnalysisResult.topic || "";
  pdfPreviewBody.innerHTML = window.KhunehoPdf.renderPreviewHtml(doc);
  pdfPreviewModal.classList.remove("hidden");
  document.body.classList.add("pdf-modal-open");
  pdfPreviewCancel.focus();
}

function closePdfPreview() {
  pendingPdfKind = null;
  pdfPreviewModal.classList.add("hidden");
  pdfPreviewBody.innerHTML = "";
  document.body.classList.remove("pdf-modal-open");
}

function confirmPdfDownload() {
  if (!pendingPdfKind || !lastAnalysisResult) return;
  if (!ensurePdfExportReady()) return;

  if (pendingPdfKind === "complete") {
    window.KhunehoPdf.downloadCompleteReportPdf(lastAnalysisResult);
  } else {
    window.KhunehoPdf.downloadFullReportPdf(
      lastAnalysisResult.report_text,
      lastAnalysisResult.topic
    );
  }
  closePdfPreview();
}

async function handleAnalyze() {
  const topic = topicInput.value.trim();
  if (!topic) {
    alert("Please enter a topic before analyzing.");
    return;
  }

  if (analyzeAbortController) {
    analyzeAbortController.abort();
  }
  analyzeAbortController = new AbortController();

  clearResults();
  clearProgress();
  setProgressPhase("running", STEP_STATUS_TEXT.active[1]);
  syncProgressSteps(1);
  setLoading(true);
  setFormLocked(true);

  try {
    const response = await fetch("/api/analyze/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, enable_causal_trace: causalCheckbox.checked }),
      signal: analyzeAbortController.signal,
    });

    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      const msg = result.message || result.error || "Analysis failed. Please try again.";
      finishProgressError(result.step || currentActiveStep, msg);
      alert(msg);
      return;
    }

    const result = await consumeAnalyzeStream(response);
    if (!result) {
      finishProgressError(currentActiveStep, "Analysis finished without a result.");
      alert("Analysis finished without a result.");
      return;
    }

    finishProgressSuccess();

    lastAnalysisResult = result;
    updatePdfDownloadButtons(result);
    renderSummary(result);
    renderCausal(result);
    renderDomains(result);
    renderTimeline(result);
    renderSources(result);

    setTimeout(() => {
      summaryPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 300);
  } catch (error) {
    if (error.name === "AbortError") {
      return;
    }
    const msg = error.message || "Unable to connect to the analysis engine.";
    finishProgressError(error.step || currentActiveStep, msg);
    alert(msg);
  } finally {
    analyzeAbortController = null;
    setFormLocked(false);
    setLoading(false);
  }
}
