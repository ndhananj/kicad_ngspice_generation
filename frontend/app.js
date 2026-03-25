const fallbackExamples = [
  {
    id: "rc_lowpass",
    name: "RC Low-pass",
    summary: "Single-pole filter topology with a resistor-capacitor stage for smoothing high-frequency content.",
    description: "A foundational analog stage that demonstrates passive roll-off and clean node labeling across KiCad, TeX, and ngspice exports.",
    tags: ["filter", "passive", "frequency shaping"],
  },
  {
    id: "rc_highpass",
    name: "RC High-pass",
    summary: "Coupling capacitor stage that attenuates DC and low-frequency content before handing the signal forward.",
    description: "Useful for exploring shared specification data while verifying the generated artifacts stay aligned across toolchains.",
    tags: ["filter", "passive", "signal conditioning"],
  },
  {
    id: "rlc_bandpass",
    name: "RLC Band-pass",
    summary: "Resonant network for emphasizing a target frequency band with richer reactive interactions.",
    description: "Highlights the readability of more complex passive layouts and the benefit of layered visual hierarchy in the preview workspace.",
    tags: ["resonant", "reactive", "band-pass"],
  },
  {
    id: "diode_clipper",
    name: "Diode Clipper",
    summary: "Non-linear waveform shaper using diode conduction thresholds to limit output amplitude.",
    description: "An approachable way to inspect a mixed analog behavior example while jumping directly to generated source artifacts.",
    tags: ["non-linear", "wave shaping", "diodes"],
  },
  {
    id: "bjt_common_emitter",
    name: "BJT Common Emitter",
    summary: "Classic transistor gain stage with biasing network and collector load for voltage amplification.",
    description: "Pairs well with the inspector panel to show how active-device examples can still feel editorial and calm rather than dense.",
    tags: ["transistor", "gain stage", "biasing"],
  },
  {
    id: "opamp_inverting",
    name: "Op-amp Inverting",
    summary: "Feedback-driven op-amp stage that maps input polarity inversion to stable small-signal gain.",
    description: "Useful for opening the KiCad and TeX outputs side-by-side from a single floating control surface.",
    tags: ["op-amp", "feedback", "gain"],
  },
  {
    id: "cmos_inverter",
    name: "CMOS Inverter",
    summary: "Complementary MOS pair that converts logic levels with strong contrast between high and low states.",
    description: "A digital-leaning example that fits the neon laboratory brief with glowing signal paths and compact component storytelling.",
    tags: ["digital", "CMOS", "logic"],
  },
  {
    id: "schmitt_trigger",
    name: "Schmitt Trigger",
    summary: "Regenerative switching topology that adds hysteresis for cleaner thresholding and noise immunity.",
    description: "Good for validating that the interface handles more advanced comparator-style circuits without visual clutter.",
    tags: ["hysteresis", "comparator", "thresholding"],
  },
];

const sourceTabs = [
  {
    id: "circuitikz",
    label: "circuitikz.tex",
    title: "Circuitikz Source",
    filename: "circuitikz.tex",
    artifactKey: "circuitikzTex",
    previewMode: "visual",
  },
  {
    id: "report",
    label: "report.tex",
    title: "Report TeX",
    filename: "report.tex",
    artifactKey: "reportTex",
    previewMode: "document",
  },
  {
    id: "ngspice",
    label: "ngspice.cir",
    title: "SPICE Netlist",
    filename: "ngspice.cir",
    artifactKey: "ngspice",
    previewMode: "visual",
  },
];

const artifactEntries = [
  { id: "circuitikz", label: "circuitikz.tex", meta: "Readable circuit source", tabId: "circuitikz", artifactKey: "circuitikzTex" },
  { id: "report", label: "report.tex", meta: "Standalone report source", tabId: "report", artifactKey: "reportTex" },
  { id: "ngspice", label: "ngspice.cir", meta: "Simulation-ready netlist", tabId: "ngspice", artifactKey: "ngspice" },
  { id: "svg", label: "preview.svg", meta: "Schematic companion", hrefKey: "svg" },
  { id: "reportPdf", label: "report.pdf", meta: "Document preview", hrefKey: "reportPdf" },
  { id: "kicad", label: "schematic.kicad_sch", meta: "KiCad source", hrefKey: "kicad" },
];

const artifactUrlTemplates = {
  svg: "/examples/generated/svg/{exampleId}.svg",
  pdf: "/examples/generated/svg/{exampleId}.pdf",
  kicad: "/examples/generated/kicad/{exampleId}.kicad_sch",
  ngspice: "/examples/generated/ngspice/{exampleId}.cir",
  reportTex: "/examples/generated/tex/{exampleId}.tex",
  circuitikzTex: "/examples/generated/tex/{exampleId}.circuitikz.tex",
  reportPdf: "/examples/generated/tex/{exampleId}.pdf",
};

const state = {
  examples: [],
  byId: {},
  activeExampleId: fallbackExamples[0].id,
  activeTabId: "circuitikz",
};

const exampleCount = document.querySelector("#example-count");
const exampleList = document.querySelector("#example-list");
const artifactList = document.querySelector("#artifact-list");
const heroTitle = document.querySelector("#hero-title");
const heroSummary = document.querySelector("#hero-summary");
const focusButton = document.querySelector("#focus-button");
const activeFileLabel = document.querySelector("#active-file-label");
const sourceTabList = document.querySelector("#source-tab-list");
const sourceCode = document.querySelector("#source-code");
const sourceStatus = document.querySelector("#source-status");
const openRawLink = document.querySelector("#open-raw-link");
const previewCaption = document.querySelector("#preview-caption");
const previewOpenLink = document.querySelector("#preview-open-link");
const visualPreview = document.querySelector("#visual-preview");
const previewImage = document.querySelector("#preview-image");
const previewState = document.querySelector("#preview-state");
const previewStateTitle = document.querySelector("#preview-state-title");
const previewStateCopy = document.querySelector("#preview-state-copy");
const documentPreview = document.querySelector("#document-preview");
const previewFrame = document.querySelector("#preview-frame");
const documentFallback = document.querySelector("#document-fallback");
const documentFallbackTitle = document.querySelector("#document-fallback-title");
const documentFallbackCopy = document.querySelector("#document-fallback-copy");
const documentFallbackCode = document.querySelector("#document-fallback-code");
const inspectorTitle = document.querySelector("#inspector-title");
const inspectorDescription = document.querySelector("#inspector-description");
const tagList = document.querySelector("#tag-list");
const viewCircuitikz = document.querySelector("#view-circuitikz");
const viewReportTex = document.querySelector("#view-report-tex");
const viewNgspice = document.querySelector("#view-ngspice");
const viewKicad = document.querySelector("#view-kicad");
const downloadSvg = document.querySelector("#download-svg");
const downloadPdf = document.querySelector("#download-pdf");

let sourceRequestToken = 0;

function defaultArtifactUrl(kind, exampleId) {
  return artifactUrlTemplates[kind].replace("{exampleId}", exampleId);
}

function createDefaultArtifacts(exampleId) {
  return {
    svg: { url: defaultArtifactUrl("svg", exampleId), available: true },
    pdf: { url: defaultArtifactUrl("pdf", exampleId), available: true },
    kicad: { url: defaultArtifactUrl("kicad", exampleId), available: true },
    ngspice: { url: defaultArtifactUrl("ngspice", exampleId), available: true },
    reportTex: { url: defaultArtifactUrl("reportTex", exampleId), available: true },
    circuitikzTex: { url: defaultArtifactUrl("circuitikzTex", exampleId), available: true },
    reportPdf: { url: defaultArtifactUrl("reportPdf", exampleId), available: false },
  };
}

function normalizeArtifacts(example) {
  const defaults = createDefaultArtifacts(example.id);
  return Object.fromEntries(
    Object.entries(defaults).map(([key, fallbackArtifact]) => {
      const artifact = example.artifacts?.[key] ?? fallbackArtifact;
      const url = artifact.url ?? fallbackArtifact.url;
      return [
        key,
        {
          url,
          available: Boolean(artifact.available ?? fallbackArtifact.available) && Boolean(url),
        },
      ];
    }),
  );
}

function normalizeExample(example) {
  const fallback = fallbackExamples.find((entry) => entry.id === example.id) ?? {};
  return {
    ...fallback,
    ...example,
    tags: example.tags ?? fallback.tags ?? [],
    artifacts: normalizeArtifacts({ ...fallback, ...example }),
  };
}

function setExamples(examples) {
  state.examples = examples.map(normalizeExample);
  state.byId = Object.fromEntries(state.examples.map((example) => [example.id, example]));
  if (!state.byId[state.activeExampleId] && state.examples[0]) {
    state.activeExampleId = state.examples[0].id;
  }
  exampleCount.textContent = `${state.examples.length} circuits`;
}

function getActiveExample() {
  return state.byId[state.activeExampleId] ?? state.examples[0];
}

function getActiveTab() {
  return sourceTabs.find((tab) => tab.id === state.activeTabId) ?? sourceTabs[0];
}

function getArtifact(example, key) {
  return example?.artifacts?.[key] ?? { url: "#", available: false };
}

function isArtifactAvailable(example, key) {
  const artifact = getArtifact(example, key);
  return Boolean(artifact.available && artifact.url);
}

function setLinkState(element, artifact) {
  if (artifact.available && artifact.url) {
    element.href = artifact.url;
    element.removeAttribute("aria-disabled");
    return;
  }
  element.removeAttribute("href");
  element.setAttribute("aria-disabled", "true");
}

function renderTags(tags) {
  tagList.replaceChildren(
    ...tags.map((tag) => {
      const pill = document.createElement("span");
      pill.className = "tag";
      pill.textContent = tag;
      return pill;
    }),
  );
}

function renderExampleList() {
  exampleList.replaceChildren(
    ...state.examples.map((example) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "example-card";
      button.dataset.exampleId = example.id;
      button.setAttribute("aria-pressed", String(example.id === state.activeExampleId));
      button.innerHTML = `
        <span class="example-card-title">${example.name}</span>
        <span class="example-card-summary">${example.summary}</span>
      `;
      button.addEventListener("click", () => setActiveExample(example.id));
      if (example.id === state.activeExampleId) {
        button.classList.add("active");
      }
      return button;
    }),
  );
}

function renderArtifactList() {
  const example = getActiveExample();
  artifactList.replaceChildren(
    ...artifactEntries.map((entry) => {
      const artifactKey = entry.artifactKey ?? entry.hrefKey;
      const artifact = getArtifact(example, artifactKey);
      const available = Boolean(artifact.available && artifact.url);
      const element = document.createElement(entry.tabId ? "button" : "a");
      element.className = "artifact-item";
      element.classList.toggle("unavailable", !available);
      if (entry.tabId) {
        element.type = "button";
        element.addEventListener("click", () => setActiveTab(entry.tabId));
        if (entry.tabId === state.activeTabId) {
          element.classList.add("active");
        }
      } else {
        element.target = "_blank";
        element.rel = "noopener";
        setLinkState(element, artifact);
      }
      element.innerHTML = `
        <span class="artifact-name">${entry.label}</span>
        <span class="artifact-meta">${available ? entry.meta : `${entry.meta} unavailable in this corpus`}</span>
      `;
      return element;
    }),
  );
}

function renderSourceTabs() {
  const example = getActiveExample();
  sourceTabList.replaceChildren(
    ...sourceTabs.map((tab) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "source-tab";
      button.classList.toggle("unavailable", !isArtifactAvailable(example, tab.artifactKey));
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(tab.id === state.activeTabId));
      button.textContent = tab.label;
      button.addEventListener("click", () => setActiveTab(tab.id));
      if (tab.id === state.activeTabId) {
        button.classList.add("active");
      }
      return button;
    }),
  );
}

function setStatus(message, isError = false) {
  if (!message) {
    sourceStatus.hidden = true;
    sourceStatus.textContent = "";
    sourceStatus.classList.remove("error");
    return;
  }

  sourceStatus.hidden = false;
  sourceStatus.textContent = message;
  sourceStatus.classList.toggle("error", isError);
}

function showVisualFallback(title, copy) {
  previewImage.hidden = true;
  previewState.hidden = false;
  previewStateTitle.textContent = title;
  previewStateCopy.textContent = copy;
}

function hideVisualFallback() {
  previewState.hidden = true;
}

function showDocumentFallback(title, copy, code = "") {
  documentPreview.hidden = false;
  documentFallback.hidden = false;
  previewFrame.hidden = true;
  previewFrame.removeAttribute("src");
  previewFrame.srcdoc = "";
  documentFallbackTitle.textContent = title;
  documentFallbackCopy.textContent = copy;
  documentFallbackCode.hidden = !code;
  documentFallbackCode.textContent = code;
}

function showDocumentFrame(url) {
  documentPreview.hidden = false;
  documentFallback.hidden = true;
  previewFrame.hidden = false;
  previewFrame.srcdoc = "";
  previewFrame.src = url;
}

function renderPreview(sourceText = sourceCode.textContent) {
  const example = getActiveExample();
  const activeTab = getActiveTab();
  const svgArtifact = getArtifact(example, "svg");
  const reportTexArtifact = getArtifact(example, "reportTex");
  const reportPdfArtifact = getArtifact(example, "reportPdf");

  if (activeTab.previewMode === "document") {
    visualPreview.hidden = true;
    documentPreview.hidden = false;

    if (reportPdfArtifact.available) {
      showDocumentFrame(reportPdfArtifact.url);
      setLinkState(previewOpenLink, reportPdfArtifact);
      previewCaption.textContent = `${example.name} report preview`;
      return;
    }

    setLinkState(previewOpenLink, reportTexArtifact);
    previewCaption.textContent = `${example.name} report source preview`;
    if (reportTexArtifact.available) {
      showDocumentFallback(
        "Inline report preview",
        "Showing report.tex because no rendered report PDF is available for this example.",
        sourceText || "Loading report.tex...",
      );
      return;
    }

    showDocumentFallback(
      "Report preview unavailable",
      "This example does not include report.tex or report.pdf in the current corpus.",
    );
    return;
  }

  documentPreview.hidden = true;
  visualPreview.hidden = false;
  previewCaption.textContent = `${example.name} schematic companion`;
  setLinkState(previewOpenLink, svgArtifact);

  if (!svgArtifact.available) {
    showVisualFallback("Preview unavailable", "No SVG preview is available for this example in the current corpus.");
    return;
  }

  previewImage.hidden = false;
  previewImage.alt = `${example.name} schematic preview`;
  previewImage.onload = () => hideVisualFallback();
  previewImage.onerror = () => {
    showVisualFallback("Preview unavailable", "The SVG preview could not be loaded even though the artifact was listed as available.");
  };
  previewImage.src = svgArtifact.url;
}

function getPrimaryArtifact(example) {
  for (const key of ["circuitikzTex", "reportTex", "ngspice", "svg", "kicad"]) {
    const artifact = getArtifact(example, key);
    if (artifact.available) {
      return artifact;
    }
  }
  return { available: false, url: "#" };
}

function renderInspector() {
  const example = getActiveExample();
  if (!example) {
    return;
  }

  heroTitle.textContent = example.name;
  heroSummary.textContent = example.summary;
  inspectorTitle.textContent = example.name;
  inspectorDescription.textContent = example.description;
  renderTags(example.tags);

  setLinkState(viewCircuitikz, getArtifact(example, "circuitikzTex"));
  setLinkState(viewReportTex, getArtifact(example, "reportTex"));
  setLinkState(viewNgspice, getArtifact(example, "ngspice"));
  setLinkState(viewKicad, getArtifact(example, "kicad"));
  setLinkState(downloadSvg, getArtifact(example, "svg"));
  setLinkState(downloadPdf, getArtifact(example, "pdf"));

  const primaryArtifact = getPrimaryArtifact(example);
  focusButton.disabled = !primaryArtifact.available;
  focusButton.onclick = primaryArtifact.available
    ? () => window.open(primaryArtifact.url, "_blank", "noopener")
    : null;
}

async function loadSourceText() {
  const example = getActiveExample();
  const activeTab = getActiveTab();
  const artifact = getArtifact(example, activeTab.artifactKey);
  const requestToken = ++sourceRequestToken;

  sourceCode.textContent = "";
  activeFileLabel.textContent = activeTab.filename;
  setLinkState(openRawLink, artifact);

  if (!artifact.available) {
    setStatus(`Unable to load ${activeTab.filename}. This artifact is not available in the current corpus.`, true);
    renderPreview("");
    return;
  }

  setStatus(`Loading ${activeTab.filename}...`);
  try {
    const response = await fetch(artifact.url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    if (requestToken !== sourceRequestToken) {
      return;
    }
    sourceCode.textContent = text;
    setStatus("");
    renderPreview(text);
  } catch (error) {
    if (requestToken !== sourceRequestToken) {
      return;
    }
    sourceCode.textContent = "";
    setStatus(`Unable to load ${activeTab.filename}. ${error.message}.`, true);
    renderPreview("");
  }
}

function renderAll() {
  renderExampleList();
  renderArtifactList();
  renderSourceTabs();
  renderInspector();
  renderPreview();
}

function setActiveTab(tabId) {
  if (!sourceTabs.some((tab) => tab.id === tabId)) {
    return;
  }
  state.activeTabId = tabId;
  renderArtifactList();
  renderSourceTabs();
  renderPreview();
  void loadSourceText();
}

function setActiveExample(exampleId) {
  if (!state.byId[exampleId]) {
    return;
  }
  state.activeExampleId = exampleId;
  state.activeTabId = "circuitikz";
  renderAll();
  void loadSourceText();
}

async function hydrateFromServer() {
  try {
    const response = await fetch("/frontend/api/examples.json");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const examples = await response.json();
    if (!Array.isArray(examples) || examples.length === 0) {
      return;
    }
    const activeExampleId = state.activeExampleId;
    setExamples(examples);
    if (!state.byId[activeExampleId] && state.examples[0]) {
      state.activeExampleId = state.examples[0].id;
    }
    renderAll();
    void loadSourceText();
  } catch (error) {
    console.warn("Falling back to static example metadata.", error);
  }
}

function initializeApp() {
  if (new URLSearchParams(window.location.search).get("test") === "1") {
    document.documentElement.dataset.testMode = "true";
  }
  setExamples(fallbackExamples);
  renderAll();
  void loadSourceText();
  void hydrateFromServer();
}

initializeApp();
