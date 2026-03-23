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

const byId = Object.fromEntries(examples.map((example) => [example.id, example]));
const exampleList = document.querySelector("#example-list");
const heroTitle = document.querySelector("#hero-title");
const heroSummary = document.querySelector("#hero-summary");
const previewImage = document.querySelector("#preview-image");
const inspectorTitle = document.querySelector("#inspector-title");
const inspectorDescription = document.querySelector("#inspector-description");
const tagList = document.querySelector("#tag-list");
const viewKicad = document.querySelector("#view-kicad");
const viewNgspice = document.querySelector("#view-ngspice");
const viewTex = document.querySelector("#view-tex");
const downloadSvg = document.querySelector("#download-svg");
const downloadPdf = document.querySelector("#download-pdf");
const focusButton = document.querySelector("#focus-button");

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
    case "tex":
      return `../examples/generated/tex/${exampleId}.tex`;
    default:
      return "#";
  }
}

function renderTags(tags) {
  tagList.replaceChildren(...tags.map((tag) => {
    const pill = document.createElement("span");
    pill.className = "tag";
    pill.textContent = tag;
    return pill;
  }));
}

function setActiveExample(exampleId) {
  const example = byId[exampleId];
  if (!example) return;

  for (const chip of exampleList.querySelectorAll("button")) {
    chip.classList.toggle("active", chip.dataset.exampleId === exampleId);
  }

  heroTitle.textContent = example.name;
  heroSummary.textContent = example.summary;
  inspectorTitle.textContent = example.name;
  inspectorDescription.textContent = example.description;
  renderTags(example.tags);

  const svgPath = artifactPath("svg", exampleId);
  previewImage.src = svgPath;
  previewImage.alt = `${example.name} schematic preview`;

  viewKicad.href = artifactPath("kicad", exampleId);
  viewNgspice.href = artifactPath("ngspice", exampleId);
  viewTex.href = artifactPath("tex", exampleId);
  downloadSvg.href = svgPath;
  downloadPdf.href = artifactPath("pdf", exampleId);
  focusButton.onclick = () => window.open(artifactPath("kicad", exampleId), "_blank", "noopener");
}

for (const example of examples) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "example-chip";
  chip.dataset.exampleId = example.id;
  chip.textContent = example.name;
  chip.addEventListener("click", () => setActiveExample(example.id));
  exampleList.appendChild(chip);
}

setActiveExample(examples[0].id);
