const SVG_NS = "http://www.w3.org/2000/svg";
const GRID_STEP = 1.27;
const LARGE_GRID_STEP = GRID_STEP * 4;

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
    id: "editor",
    label: "Editor",
    title: "Interactive Editor",
    filename: "editor.scene.json",
    artifactKey: "editorScene",
    kind: "editor",
    previewMode: "visual",
  },
  {
    id: "circuitikz",
    label: "circuitikz.tex",
    title: "Circuitikz Source",
    filename: "circuitikz.tex",
    artifactKey: "circuitikzTex",
    kind: "source",
    previewMode: "visual",
  },
  {
    id: "report",
    label: "report.tex",
    title: "Report TeX",
    filename: "report.tex",
    artifactKey: "reportTex",
    kind: "source",
    previewMode: "document",
  },
  {
    id: "ngspice",
    label: "ngspice.cir",
    title: "SPICE Netlist",
    filename: "ngspice.cir",
    artifactKey: "ngspice",
    kind: "source",
    previewMode: "visual",
  },
];

const artifactEntries = [
  { id: "editor", label: "editor.scene.json", meta: "Interactive geometry scene", tabId: "editor", artifactKey: "editorScene" },
  { id: "circuitikz", label: "circuitikz.tex", meta: "Readable circuit source", tabId: "circuitikz", artifactKey: "circuitikzTex" },
  { id: "report", label: "report.tex", meta: "Standalone report source", tabId: "report", artifactKey: "reportTex" },
  { id: "ngspice", label: "ngspice.cir", meta: "Simulation-ready netlist", tabId: "ngspice", artifactKey: "ngspice" },
  { id: "svg", label: "preview.svg", meta: "Schematic companion", hrefKey: "svg" },
  { id: "reportPdf", label: "report.pdf", meta: "Document preview", hrefKey: "reportPdf" },
  { id: "kicad", label: "schematic.kicad_sch", meta: "KiCad source", hrefKey: "kicad" },
];

const artifactUrlTemplates = {
  editorScene: "/examples/generated/frontend/{exampleId}.scene.json",
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
  activeTabId: "editor",
  sourceRequestToken: 0,
  sceneRequestToken: 0,
  editorScenes: {},
  selectedComponentId: null,
  dragSession: null,
};

const exampleCount = document.querySelector("#example-count");
const exampleList = document.querySelector("#example-list");
const artifactList = document.querySelector("#artifact-list");
const heroTitle = document.querySelector("#hero-title");
const heroSummary = document.querySelector("#hero-summary");
const focusButton = document.querySelector("#focus-button");
const activeFileLabel = document.querySelector("#active-file-label");
const sourceTabList = document.querySelector("#source-tab-list");
const sourceViewer = document.querySelector("#source-viewer");
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
const documentState = document.querySelector("#document-state");
const documentStateTitle = document.querySelector("#document-state-title");
const documentStateCopy = document.querySelector("#document-state-copy");
const inspectorTitle = document.querySelector("#inspector-title");
const inspectorDescription = document.querySelector("#inspector-description");
const tagList = document.querySelector("#tag-list");
const viewCircuitikz = document.querySelector("#view-circuitikz");
const viewReportTex = document.querySelector("#view-report-tex");
const viewNgspice = document.querySelector("#view-ngspice");
const viewKicad = document.querySelector("#view-kicad");
const downloadSvg = document.querySelector("#download-svg");
const downloadPdf = document.querySelector("#download-pdf");
const editorSurface = document.querySelector("#editor-surface");
const editorCanvas = document.querySelector("#editor-canvas");
const editorSelection = document.querySelector("#editor-selection");
const editorEmptyState = document.querySelector("#editor-empty-state");
const editorEmptyTitle = document.querySelector("#editor-empty-title");
const editorEmptyCopy = document.querySelector("#editor-empty-copy");

function defaultArtifactUrl(kind, exampleId) {
  return artifactUrlTemplates[kind].replace("{exampleId}", exampleId);
}

function createDefaultArtifacts(exampleId) {
  return {
    editorScene: { url: defaultArtifactUrl("editorScene", exampleId), available: true },
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

function resetVisualPreview() {
  previewImage.hidden = true;
  previewImage.onload = null;
  previewImage.onerror = null;
  previewImage.removeAttribute("src");
  previewImage.alt = "";
  hideVisualFallback();
}

function showDocumentState(title, copy) {
  documentPreview.hidden = false;
  documentState.hidden = false;
  previewFrame.hidden = true;
  previewFrame.removeAttribute("src");
  documentStateTitle.textContent = title;
  documentStateCopy.textContent = copy;
}

function showDocumentFrame(url) {
  documentPreview.hidden = false;
  documentState.hidden = true;
  previewFrame.hidden = false;
  previewFrame.src = url;
}

function resetDocumentPreview() {
  documentState.hidden = true;
  previewFrame.hidden = true;
  previewFrame.removeAttribute("src");
}

function renderPreview() {
  const example = getActiveExample();
  const activeTab = getActiveTab();
  const svgArtifact = getArtifact(example, "svg");
  const reportTexArtifact = getArtifact(example, "reportTex");
  const reportPdfArtifact = getArtifact(example, "reportPdf");

  if (activeTab.previewMode === "document") {
    visualPreview.hidden = true;
    documentPreview.hidden = false;
    resetVisualPreview();

    if (reportPdfArtifact.available) {
      showDocumentFrame(reportPdfArtifact.url);
      setLinkState(previewOpenLink, reportPdfArtifact);
      previewCaption.textContent = `${example.name} report preview`;
      return;
    }

    setLinkState(previewOpenLink, reportPdfArtifact);
    previewCaption.textContent = `${example.name} report preview`;
    showDocumentState(
      "Report preview unavailable",
      reportTexArtifact.available
        ? "This example includes report.tex, but the rendered report PDF is missing from the current corpus."
        : "This example does not include report.pdf in the current corpus.",
    );
    return;
  }

  resetDocumentPreview();
  documentPreview.hidden = true;
  visualPreview.hidden = false;
  previewCaption.textContent = activeTab.kind === "editor" ? `${example.name} editor companion` : `${example.name} schematic companion`;
  setLinkState(previewOpenLink, svgArtifact);

  if (!svgArtifact.available) {
    showVisualFallback("Preview unavailable", "No SVG preview is available for this example in the current corpus.");
    return;
  }

  previewImage.hidden = false;
  hideVisualFallback();
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

function showEditorEmptyState(title, copy) {
  editorEmptyState.hidden = false;
  editorEmptyTitle.textContent = title;
  editorEmptyCopy.textContent = copy;
}

function hideEditorEmptyState() {
  editorEmptyState.hidden = true;
}

function pointKey(point) {
  return `${point.x}:${point.y}`;
}

function roundToGrid(value) {
  return Math.round(value / GRID_STEP) * GRID_STEP;
}

function normalizeEditorScene(scene) {
  const componentByRef = new Map();
  const components = (scene.components ?? []).map((component) => {
    const normalized = {
      ...component,
      center: { ...component.center },
      bodyBoxOffset: {
        left: component.bodyBox.left - component.center.x,
        top: component.bodyBox.top - component.center.y,
        right: component.bodyBox.right - component.center.x,
        bottom: component.bodyBox.bottom - component.center.y,
      },
      terminalOffsets: (component.terminals ?? []).map((terminal) => ({
        name: terminal.name,
        side: terminal.side,
        offset: {
          x: terminal.point.x - component.center.x,
          y: terminal.point.y - component.center.y,
        },
      })),
    };
    componentByRef.set(normalized.ref, normalized);
    return normalized;
  });

  const labels = (scene.labels ?? []).map((label) => {
    const owner = componentByRef.get(label.ownerRef);
    return {
      ...label,
      position: { ...label.position },
      offset: owner
        ? {
            x: label.position.x - owner.center.x,
            y: label.position.y - owner.center.y,
          }
        : null,
    };
  });

  return {
    ...scene,
    bounds: scene.bounds ?? { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 },
    components,
    labels,
    wires: (scene.wires ?? []).map((wire) => ({
      ...wire,
      points: wire.points.map((point) => ({ ...point })),
    })),
    nodes: (scene.nodes ?? []).map((node) => ({
      ...node,
      point: { ...node.point },
      attachments: (node.attachments ?? []).map((attachment) => ({ ...attachment })),
    })),
    junctions: (scene.junctions ?? []).map((junction) => ({
      ...junction,
      point: { ...junction.point },
    })),
  };
}

function deriveComponent(component) {
  return {
    ...component,
    bodyBox: {
      left: component.center.x + component.bodyBoxOffset.left,
      top: component.center.y + component.bodyBoxOffset.top,
      right: component.center.x + component.bodyBoxOffset.right,
      bottom: component.center.y + component.bodyBoxOffset.bottom,
    },
    terminals: component.terminalOffsets.map((terminal) => ({
      name: terminal.name,
      side: terminal.side,
      point: {
        x: component.center.x + terminal.offset.x,
        y: component.center.y + terminal.offset.y,
      },
    })),
  };
}

function compressPolyline(points) {
  const compressed = [];
  for (const point of points) {
    const last = compressed[compressed.length - 1];
    if (!last || last.x !== point.x || last.y !== point.y) {
      compressed.push(point);
    }
  }
  return compressed;
}

function routeOrthogonal(start, end) {
  if (start.x === end.x || start.y === end.y) {
    return [start, end];
  }
  return compressPolyline([start, { x: end.x, y: start.y }, end]);
}

function buildRenderedWires(scene, componentsByRef) {
  if (!scene.nodes?.length) {
    return scene.wires ?? [];
  }

  const rendered = [];
  for (const node of scene.nodes) {
    const attachments = node.attachments
      .map((attachment) => {
        const component = componentsByRef.get(attachment.ownerRef);
        const terminal = component?.terminals.find((item) => item.name === attachment.terminalName);
        return terminal ? { attachment, point: terminal.point } : null;
      })
      .filter(Boolean);

    if (attachments.length < 2) {
      continue;
    }

    if (attachments.length === 2 && node.renderStyle !== "junction") {
      rendered.push({
        id: `${node.id}:inline`,
        points: routeOrthogonal(attachments[0].point, attachments[1].point),
      });
      continue;
    }

    for (const item of attachments) {
      rendered.push({
        id: `${node.id}:${item.attachment.ownerRef}:${item.attachment.terminalName}`,
        points: routeOrthogonal(item.point, node.point),
      });
    }
  }
  return rendered;
}

function buildRenderedScene(scene) {
  const components = scene.components.map(deriveComponent);
  const componentsByRef = new Map(components.map((component) => [component.ref, component]));
  const labels = scene.labels.map((label) => {
    const owner = componentsByRef.get(label.ownerRef);
    return {
      ...label,
      position: label.offset && owner
        ? {
            x: owner.center.x + label.offset.x,
            y: owner.center.y + label.offset.y,
          }
        : label.position,
    };
  });
  const wires = buildRenderedWires(scene, componentsByRef);
  const bounds = calculateRenderedBounds(components, wires, labels, scene.junctions, scene.nodes);
  return { components, labels, wires, bounds };
}

function calculateRenderedBounds(components, wires, labels, junctions, nodes) {
  const xs = [];
  const ys = [];

  for (const component of components) {
    xs.push(component.bodyBox.left, component.bodyBox.right, component.center.x);
    ys.push(component.bodyBox.top, component.bodyBox.bottom, component.center.y);
    for (const terminal of component.terminals) {
      xs.push(terminal.point.x);
      ys.push(terminal.point.y);
    }
  }

  for (const wire of wires) {
    for (const point of wire.points) {
      xs.push(point.x);
      ys.push(point.y);
    }
  }

  for (const label of labels) {
    xs.push(label.position.x);
    ys.push(label.position.y);
  }

  for (const item of [...junctions, ...nodes]) {
    xs.push(item.point.x);
    ys.push(item.point.y);
  }

  if (!xs.length || !ys.length) {
    return { left: 0, top: 0, right: 100, bottom: 100, width: 100, height: 100 };
  }

  const left = Math.min(...xs);
  const top = Math.min(...ys);
  const right = Math.max(...xs);
  const bottom = Math.max(...ys);
  return {
    left,
    top,
    right,
    bottom,
    width: Math.max(right - left, 1),
    height: Math.max(bottom - top, 1),
  };
}

function getActiveEditorScene() {
  return state.editorScenes[state.activeExampleId] ?? null;
}

function renderEditorSelection() {
  const scene = getActiveEditorScene();
  if (!scene || !state.selectedComponentId) {
    editorSelection.textContent = "No component selected";
    return;
  }
  const component = scene.components.find((entry) => entry.ref === state.selectedComponentId);
  editorSelection.textContent = component ? `Selected: ${component.ref} (${component.shape})` : "No component selected";
}

function createSvgElement(name, attrs = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    element.setAttribute(key, String(value));
  }
  return element;
}

function renderEditorScene() {
  const scene = getActiveEditorScene();
  if (getActiveTab().kind !== "editor") {
    editorSurface.hidden = true;
    sourceViewer.hidden = false;
    return;
  }

  editorSurface.hidden = false;
  sourceViewer.hidden = true;
  editorCanvas.replaceChildren();
  renderEditorSelection();

  if (!scene) {
    showEditorEmptyState("Editor unavailable", "This example does not include an editor scene in the current corpus.");
    return;
  }

  hideEditorEmptyState();
  const rendered = buildRenderedScene(scene);
  const margin = 12;
  const viewLeft = rendered.bounds.left - margin;
  const viewTop = rendered.bounds.top - margin;
  const viewWidth = rendered.bounds.width + margin * 2;
  const viewHeight = rendered.bounds.height + margin * 2;
  editorCanvas.setAttribute("viewBox", `${viewLeft} ${viewTop} ${viewWidth} ${viewHeight}`);

  const wireLayer = createSvgElement("g", { class: "editor-wire-layer" });
  for (const wire of rendered.wires) {
    wireLayer.append(
      createSvgElement("polyline", {
        class: "editor-wire",
        points: wire.points.map((point) => `${point.x},${point.y}`).join(" "),
      }),
    );
  }

  const nodeLayer = createSvgElement("g", { class: "editor-node-layer" });
  const renderedNodePoints = new Set();
  for (const node of scene.nodes ?? []) {
    if (node.renderStyle === "junction") {
      renderedNodePoints.add(pointKey(node.point));
    }
  }
  for (const junction of scene.junctions ?? []) {
    renderedNodePoints.add(pointKey(junction.point));
  }
  for (const point of renderedNodePoints) {
    const [x, y] = point.split(":").map(Number);
    nodeLayer.append(createSvgElement("circle", { class: "editor-junction", cx: x, cy: y, r: 1.9 }));
  }

  const labelLayer = createSvgElement("g", { class: "editor-label-layer" });
  for (const label of rendered.labels) {
    const text = createSvgElement("text", {
      class: `editor-label editor-label-${label.role}`,
      x: label.position.x,
      y: label.position.y,
    });
    text.textContent = label.text;
    labelLayer.append(text);
  }

  const componentLayer = createSvgElement("g", { class: "editor-component-layer" });
  for (const component of rendered.components) {
    const group = createSvgElement("g", {
      class: `editor-component${component.ref === state.selectedComponentId ? " active" : ""}`,
      transform: `translate(${component.center.x} ${component.center.y})`,
      "data-component-id": component.ref,
      tabindex: -1,
    });
    group.append(
      createSvgElement("rect", {
        class: "editor-component-body",
        x: component.bodyBox.left - component.center.x,
        y: component.bodyBox.top - component.center.y,
        width: component.bodyBox.right - component.bodyBox.left,
        height: component.bodyBox.bottom - component.bodyBox.top,
        rx: 2.6,
        ry: 2.6,
      }),
    );
    for (const terminal of component.terminals) {
      group.append(
        createSvgElement("circle", {
          class: "editor-terminal",
          cx: terminal.point.x - component.center.x,
          cy: terminal.point.y - component.center.y,
          r: 1.3,
        }),
      );
    }

    const refText = createSvgElement("text", { class: "editor-component-ref", x: 0, y: -1.5 });
    refText.textContent = component.ref;
    group.append(refText);

    const shapeText = createSvgElement("text", { class: "editor-component-shape", x: 0, y: 2.8 });
    shapeText.textContent = component.shape;
    group.append(shapeText);
    componentLayer.append(group);
  }

  editorCanvas.append(wireLayer, nodeLayer, labelLayer, componentLayer);
}

function setEditorSelection(componentId) {
  state.selectedComponentId = componentId;
  renderEditorScene();
}

function getEditorScenePoint(event) {
  const rect = editorCanvas.getBoundingClientRect();
  const viewBox = editorCanvas.viewBox.baseVal;
  if (!rect.width || !rect.height) {
    return { x: 0, y: 0 };
  }
  return {
    x: viewBox.x + ((event.clientX - rect.left) / rect.width) * viewBox.width,
    y: viewBox.y + ((event.clientY - rect.top) / rect.height) * viewBox.height,
  };
}

function updateSelectedComponent(deltaX, deltaY) {
  const scene = getActiveEditorScene();
  if (!scene || !state.selectedComponentId) {
    return;
  }
  const component = scene.components.find((entry) => entry.ref === state.selectedComponentId);
  if (!component) {
    return;
  }
  component.center = {
    x: roundToGrid(component.center.x + deltaX),
    y: roundToGrid(component.center.y + deltaY),
  };
  renderEditorScene();
}

function handleEditorPointerDown(event) {
  if (getActiveTab().kind !== "editor") {
    return;
  }
  const componentGroup = event.target.closest("[data-component-id]");
  if (!componentGroup) {
    state.dragSession = null;
    setEditorSelection(null);
    return;
  }

  const scene = getActiveEditorScene();
  const componentId = componentGroup.dataset.componentId;
  const component = scene?.components.find((entry) => entry.ref === componentId);
  if (!component) {
    return;
  }
  event.preventDefault();
  editorCanvas.focus();
  setEditorSelection(componentId);
  state.dragSession = {
    componentId,
    startPointer: getEditorScenePoint(event),
    startCenter: { ...component.center },
  };
}

function handleEditorPointerMove(event) {
  if (!state.dragSession || getActiveTab().kind !== "editor") {
    return;
  }
  const scene = getActiveEditorScene();
  const component = scene?.components.find((entry) => entry.ref === state.dragSession.componentId);
  if (!component) {
    return;
  }
  const point = getEditorScenePoint(event);
  component.center = {
    x: roundToGrid(state.dragSession.startCenter.x + point.x - state.dragSession.startPointer.x),
    y: roundToGrid(state.dragSession.startCenter.y + point.y - state.dragSession.startPointer.y),
  };
  renderEditorScene();
}

function handleEditorPointerUp() {
  state.dragSession = null;
}

function handleEditorKeyDown(event) {
  if (getActiveTab().kind !== "editor" || !state.selectedComponentId) {
    return;
  }
  const step = event.shiftKey ? LARGE_GRID_STEP : GRID_STEP;
  if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    setEditorSelection(null);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    updateSelectedComponent(0, -step);
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    updateSelectedComponent(0, step);
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    updateSelectedComponent(-step, 0);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    updateSelectedComponent(step, 0);
  }
}

async function loadSourceText() {
  const example = getActiveExample();
  const activeTab = getActiveTab();
  const artifact = getArtifact(example, activeTab.artifactKey);
  const requestToken = ++state.sourceRequestToken;

  sourceCode.textContent = "";
  activeFileLabel.textContent = activeTab.filename;
  setLinkState(openRawLink, artifact);

  if (!artifact.available) {
    setStatus(`Unable to load ${activeTab.filename}. This artifact is not available in the current corpus.`, true);
    renderPreview();
    return;
  }

  setStatus(`Loading ${activeTab.filename}...`);
  try {
    const response = await fetch(artifact.url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    if (requestToken !== state.sourceRequestToken) {
      return;
    }
    sourceCode.textContent = text;
    setStatus("");
    renderPreview();
  } catch (error) {
    if (requestToken !== state.sourceRequestToken) {
      return;
    }
    sourceCode.textContent = "";
    setStatus(`Unable to load ${activeTab.filename}. ${error.message}.`, true);
    renderPreview();
  }
}

async function loadEditorScene() {
  const example = getActiveExample();
  const activeTab = getActiveTab();
  const artifact = getArtifact(example, activeTab.artifactKey);
  const requestToken = ++state.sceneRequestToken;

  activeFileLabel.textContent = activeTab.filename;
  setLinkState(openRawLink, artifact);
  setStatus("");

  if (!artifact.available) {
    delete state.editorScenes[example.id];
    state.selectedComponentId = null;
    renderEditorScene();
    return;
  }

  try {
    const response = await fetch(artifact.url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const scene = await response.json();
    if (requestToken !== state.sceneRequestToken) {
      return;
    }
    state.editorScenes[example.id] = normalizeEditorScene(scene);
    state.selectedComponentId = null;
    renderEditorScene();
  } catch (error) {
    if (requestToken !== state.sceneRequestToken) {
      return;
    }
    delete state.editorScenes[example.id];
    state.selectedComponentId = null;
    showEditorEmptyState("Editor unavailable", `Unable to load ${activeTab.filename}. ${error.message}.`);
    setStatus(`Unable to load ${activeTab.filename}. ${error.message}.`, true);
    renderEditorScene();
  }
}

function renderAll() {
  renderExampleList();
  renderArtifactList();
  renderSourceTabs();
  renderInspector();
  renderPreview();
  renderEditorScene();
}

function loadActiveTabContent() {
  if (getActiveTab().kind === "editor") {
    sourceCode.textContent = "";
    setStatus("");
    void loadEditorScene();
    return;
  }
  renderEditorScene();
  void loadSourceText();
}

function setActiveTab(tabId) {
  if (!sourceTabs.some((tab) => tab.id === tabId)) {
    return;
  }
  state.activeTabId = tabId;
  renderArtifactList();
  renderSourceTabs();
  renderPreview();
  renderEditorScene();
  loadActiveTabContent();
}

function setActiveExample(exampleId) {
  if (!state.byId[exampleId]) {
    return;
  }
  state.activeExampleId = exampleId;
  state.selectedComponentId = null;
  state.dragSession = null;
  renderAll();
  loadActiveTabContent();
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
    loadActiveTabContent();
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
  loadActiveTabContent();
  void hydrateFromServer();
}

editorCanvas.addEventListener("pointerdown", handleEditorPointerDown);
window.addEventListener("pointermove", handleEditorPointerMove);
window.addEventListener("pointerup", handleEditorPointerUp);
editorCanvas.addEventListener("keydown", handleEditorKeyDown);

initializeApp();
