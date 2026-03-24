const examples = [
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
  { id: "circuitikz", label: "circuitikz.tex", meta: "Readable circuit source", tabId: "circuitikz" },
  { id: "report", label: "report.tex", meta: "Standalone report source", tabId: "report" },
  { id: "ngspice", label: "ngspice.cir", meta: "Simulation-ready netlist", tabId: "ngspice" },
  { id: "svg", label: "preview.svg", meta: "Schematic companion", hrefKey: "svg" },
  { id: "reportPdf", label: "report.pdf", meta: "Document preview", hrefKey: "reportPdf" },
  { id: "kicad", label: "schematic.kicad_sch", meta: "KiCad source", hrefKey: "kicad" },
];

const byId = Object.fromEntries(examples.map((example) => [example.id, example]));
const state = {
  activeExampleId: examples[0].id,
  activeTabId: "circuitikz",
};

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
const documentPreview = document.querySelector("#document-preview");
const previewFrame = document.querySelector("#preview-frame");
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

function artifactPath(kind, exampleId) {
  switch (kind) {
    case "svg":
      return `../examples/generated/svg/${exampleId}.svg`;
    case "pdf":
      return `../examples/generated/svg/${exampleId}.pdf`;
    case "kicad":
      return `../examples/generated/kicad/${exampleId}.kicad_sch`;
    case "ngspice":
      return `../examples/generated/ngspice/${exampleId}.cir`;
    case "reportTex":
      return `../examples/generated/tex/${exampleId}.tex`;
    case "circuitikzTex":
      return `../examples/generated/tex/${exampleId}.circuitikz.tex`;
    case "reportPdf":
      return `../examples/generated/tex/${exampleId}.pdf`;
    default:
      return "#";
  }
}

function getArtifactMap(exampleId) {
  return {
    svg: artifactPath("svg", exampleId),
    pdf: artifactPath("pdf", exampleId),
    kicad: artifactPath("kicad", exampleId),
    ngspice: artifactPath("ngspice", exampleId),
    reportTex: artifactPath("reportTex", exampleId),
    circuitikzTex: artifactPath("circuitikzTex", exampleId),
    reportPdf: artifactPath("reportPdf", exampleId),
  };
}

function getActiveExample() {
  return byId[state.activeExampleId];
}

function getActiveTab() {
  return sourceTabs.find((tab) => tab.id === state.activeTabId) ?? sourceTabs[0];
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
    ...examples.map((example) => {
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
  const paths = getArtifactMap(state.activeExampleId);
  artifactList.replaceChildren(
    ...artifactEntries.map((entry) => {
      const element = document.createElement(entry.tabId ? "button" : "a");
      if (entry.tabId) {
        element.type = "button";
        element.addEventListener("click", () => setActiveTab(entry.tabId));
        element.className = "artifact-item";
        if (entry.tabId === state.activeTabId) {
          element.classList.add("active");
        }
      } else {
        element.href = paths[entry.hrefKey];
        element.target = "_blank";
        element.rel = "noopener";
        element.className = "artifact-item";
      }
      element.innerHTML = `
        <span class="artifact-name">${entry.label}</span>
        <span class="artifact-meta">${entry.meta}</span>
      `;
      return element;
    }),
  );
}

function renderSourceTabs() {
  sourceTabList.replaceChildren(
    ...sourceTabs.map((tab) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "source-tab";
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

async function loadSourceText() {
  const activeTab = getActiveTab();
  const paths = getArtifactMap(state.activeExampleId);
  const path = paths[activeTab.artifactKey];
  const requestToken = ++sourceRequestToken;

  sourceCode.textContent = "";
  setStatus(`Loading ${activeTab.filename}...`);
  openRawLink.href = path;
  activeFileLabel.textContent = activeTab.filename;

  try {
    const response = await fetch(path);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    if (requestToken !== sourceRequestToken) {
      return;
    }
    sourceCode.textContent = text;
    setStatus("");
  } catch (error) {
    if (requestToken !== sourceRequestToken) {
      return;
    }
    sourceCode.textContent = "";
    setStatus(`Unable to load ${activeTab.filename}. ${error.message}.`, true);
  }
}

function renderPreview() {
  const example = getActiveExample();
  const activeTab = getActiveTab();
  const paths = getArtifactMap(example.id);

  if (activeTab.previewMode === "document") {
    visualPreview.hidden = true;
    documentPreview.hidden = false;
    previewFrame.src = paths.reportPdf;
    previewOpenLink.href = paths.reportPdf;
    previewCaption.textContent = `${example.name} report preview`;
    return;
  }

  documentPreview.hidden = true;
  visualPreview.hidden = false;
  previewImage.src = paths.svg;
  previewImage.alt = `${example.name} schematic preview`;
  previewOpenLink.href = paths.svg;
  previewCaption.textContent = `${example.name} schematic companion`;
}

function renderInspector() {
  const example = getActiveExample();
  const paths = getArtifactMap(example.id);

  heroTitle.textContent = example.name;
  heroSummary.textContent = example.summary;
  inspectorTitle.textContent = example.name;
  inspectorDescription.textContent = example.description;
  renderTags(example.tags);

  viewCircuitikz.href = paths.circuitikzTex;
  viewReportTex.href = paths.reportTex;
  viewNgspice.href = paths.ngspice;
  viewKicad.href = paths.kicad;
  downloadSvg.href = paths.svg;
  downloadPdf.href = paths.pdf;
  focusButton.onclick = () => window.open(paths.circuitikzTex, "_blank", "noopener");
}

function setActiveTab(tabId) {
  if (!sourceTabs.some((tab) => tab.id === tabId)) {
    return;
  }
  state.activeTabId = tabId;
  renderSourceTabs();
  renderArtifactList();
  renderPreview();
  void loadSourceText();
}

function setActiveExample(exampleId) {
  if (!byId[exampleId]) {
    return;
  }
  state.activeExampleId = exampleId;
  state.activeTabId = "circuitikz";
  renderExampleList();
  renderArtifactList();
  renderSourceTabs();
  renderInspector();
  renderPreview();
  void loadSourceText();
}

setActiveExample(state.activeExampleId);
