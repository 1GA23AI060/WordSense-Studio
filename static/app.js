const $ = (id) => document.getElementById(id);

const sentenceInput = $("sentence");
const targetInput = $("target");
const analyzeBtn = $("analyzeBtn");

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function updateCharCount() {
  $("charCount").textContent = `${sentenceInput.value.length} / 2000`;
}
sentenceInput.addEventListener("input", updateCharCount);
updateCharCount();

$("clearBtn").addEventListener("click", () => {
  sentenceInput.value = "";
  targetInput.value = "";
  updateCharCount();
  sentenceInput.focus();
});

async function getJSON(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.message || "Something went wrong.");
  return data;
}

function selectSample(sentence, target) {
  sentenceInput.value = sentence;
  targetInput.value = target;
  updateCharCount();
  analyzeSentence();
}

document.querySelectorAll("[data-sentence]").forEach((button) => {
  button.addEventListener("click", () => {
    selectSample(button.dataset.sentence, button.dataset.target);
  });
});

async function analyzeSentence() {
  const sentence = sentenceInput.value.trim();
  const target = targetInput.value.trim();

  $("errorBox").classList.add("hidden");
  $("emptyState").classList.remove("hidden");
  $("resultContent").classList.add("hidden");
  analyzeBtn.disabled = true;
  analyzeBtn.querySelector("span").textContent = "Analyzing…";

  try {
    const result = await getJSON("/api/analyze", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({sentence, target})
    });

    if (!result.found) {
      $("emptyState").classList.add("hidden");
      $("errorBox").textContent = result.message;
      $("errorBox").classList.remove("hidden");
      renderCandidates([]);
      return;
    }

    renderResult(result);
    renderCandidates(result.candidates);
  } catch (error) {
    $("emptyState").classList.add("hidden");
    $("errorBox").textContent = error.message;
    $("errorBox").classList.remove("hidden");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.querySelector("span").textContent = "Analyze meaning";
  }
}

function renderResult(result) {
  const sense = result.predicted_sense;
  $("emptyState").classList.add("hidden");
  $("errorBox").classList.add("hidden");
  $("resultContent").classList.remove("hidden");
  $("predictedName").textContent = sense.name;
  $("posBadge").textContent = sense.pos_label.toUpperCase();
  $("confidenceBadge").textContent = `${result.confidence} heuristic`;
  $("synsetId").textContent = sense.id;
  $("definition").textContent = sense.definition;
  $("scoreValue").textContent = sense.score;
  $("scoreBar").style.width = `${Math.min(100, sense.score * 18)}%`;
  $("explanation").textContent = result.explanation;

  const examples = sense.examples || [];
  $("examplesWrap").classList.toggle("hidden", examples.length === 0);
  $("examples").textContent = examples.map((item) => `“${item}”`).join(" · ");
}

function renderCandidates(candidates) {
  $("candidateCount").textContent = `${candidates.length} CANDIDATE SENSES`;
  const container = $("candidates");

  if (!candidates.length) {
    container.innerHTML = '<div class="candidate-placeholder">No candidate senses found. Try another target word.</div>';
    return;
  }

  container.innerHTML = candidates.map((sense, index) => `
    <article class="candidate-card ${index === 0 ? "best" : ""}">
      <div class="candidate-card-top">
        <span class="candidate-name">${escapeHTML(sense.name)}</span>
        <span class="candidate-score">Score ${sense.score}</span>
      </div>
      <p class="candidate-definition">${escapeHTML(sense.definition)}</p>
      <div class="candidate-footer">
        <span>${escapeHTML(sense.pos_label)} · ${escapeHTML(sense.id)}</span>
        <span>${index === 0 ? "TOP MATCH ✳" : "WORDNET SENSE"}</span>
      </div>
      ${(sense.hypernyms || []).length ? `<div class="candidate-footer"><span>Hypernym: ${escapeHTML(sense.hypernyms[0])}</span></div>` : ""}
    </article>
  `).join("");
}

function renderDataset(samples) {
  $("sampleCount").textContent = samples.length;
  const container = $("datasetList");
  container.innerHTML = samples.map((sample) => `
    <button class="dataset-row" data-id="${sample.id}">
      <span class="dataset-number">${String(sample.id).padStart(2, "0")}</span>
      <span class="dataset-copy">
        <strong>${escapeHTML(sample.target)} <span style="display:inline;color:#8c80d7">· ${escapeHTML(sample.category)}</span></strong>
        <span>${escapeHTML(sample.sentence)}</span>
      </span>
      <span class="dataset-arrow">↗</span>
    </button>
  `).join("");

  container.querySelectorAll("[data-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const sample = samples.find((item) => item.id === Number(button.dataset.id));
      if (sample) selectSample(sample.sentence, sample.target);
      window.scrollTo({top: $("sentence").getBoundingClientRect().top + window.scrollY - 110, behavior: "smooth"});
    });
  });
}

$("analyzeBtn").addEventListener("click", analyzeSentence);
targetInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") analyzeSentence();
});
sentenceInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") analyzeSentence();
});

$("reportBtn").addEventListener("click", async () => {
  const button = $("reportBtn");
  const message = $("reportMessage");
  button.disabled = true;
  button.querySelector("span").textContent = "Generating report…";
  message.textContent = "";
  $("downloadLink").classList.add("hidden");

  try {
    const result = await getJSON("/api/report", {method: "POST"});
    message.textContent = result.message;
    $("downloadLink").classList.remove("hidden");
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Generate analysis report";
  }
});

async function init() {
  try {
    const health = await getJSON("/api/health");
    $("systemStatus").textContent = "WordNet connected";
    if (health.samples) $("sampleCount").textContent = health.samples;
  } catch (error) {
    $("systemStatus").textContent = "Check WordNet setup";
    console.error(error);
  }

  try {
    const samples = await getJSON("/api/samples");
    renderDataset(samples);
  } catch (error) {
    $("datasetList").innerHTML = `<div class="candidate-placeholder">${escapeHTML(error.message)}</div>`;
  }

  analyzeSentence();
}
init();
