console.log("script.js loaded");

const API_BASE = "http://localhost:5000/api";

let quizRoundId = null;
let mcVerbCount = 0;
let sortingVerbCount = 0;
let nounsRoundId = null;
let nounsCount = 0;
let currentNounData = null;
let currentVerbData = {};
let sortingRoundId = null;

// Sections
const vocabSection   = document.getElementById("vocabSection");
const quizSection    = document.getElementById("quizSection");
const cardsSection   = document.getElementById("cardsSection");
const sortingSection = document.getElementById("sortingSection");
const nounsSection   = document.getElementById("nounsSection");

// Navigation wiring
document.getElementById("btnHomeVocab").onclick = () => {
  showSection("vocab");
  loadVocab();
};
document.getElementById("btnHomeQuiz").onclick = () => startQuizFlow();
document.getElementById("btnHomeSorting").onclick = () => {
  showSection("sorting");
  startSortingQuiz();
};
document.getElementById("btnHomeNounSorting").onclick = () => {
  showSection("nouns");
  startNounsQuiz();
};
document.getElementById("btnHomeCards").onclick = () => loadCards();

// Show/hide sections
function showSection(name) {
  console.log("showSection", name);
  vocabSection.style.display   = name === "vocab"   ? "block" : "none";
  quizSection.style.display    = name === "quiz"    ? "block" : "none";
  cardsSection.style.display   = name === "cards"   ? "block" : "none";
  sortingSection.style.display = name === "sorting" ? "block" : "none";
  nounsSection.style.display   = name === "nouns"   ? "block" : "none";
}

/* -------------------- Vocab Book -------------------- */

let currentSortCol = null;
let currentSortDir = "asc";

async function loadVocab() {
  const res  = await fetch(`${API_BASE}/vocab/`);
  const data = await res.json();
  renderVocabTable(data);
  attachSortListeners();
  attachTypeFilters();
}

function attachTypeFilters() {
  document.querySelectorAll(".type-radio").forEach(radio => {
    radio.onchange = filterByType;
  });
}

function filterByType() {
  const selectedType = document.querySelector('input[name="typeFilter"]:checked').value;
  document.querySelectorAll("#vocabTable tbody tr").forEach(row => {
    const typeCell = row.cells[2].textContent.toLowerCase();
    row.style.display =
      selectedType === "all" || typeCell === selectedType ? "" : "none";
  });
}

function renderVocabTable(data) {
  data.sort((a, b) => {
    let aVal = a[currentSortCol] ?? "";
    let bVal = b[currentSortCol] ?? "";
    if (currentSortCol === "accuracy_percent") {
      aVal = parseFloat(aVal);
      bVal = parseFloat(bVal);
    }
    if (aVal < bVal) return currentSortDir === "asc" ? -1 : 1;
    if (aVal > bVal) return currentSortDir === "asc" ? 1 : -1;
    return 0;
  });

  const tbody = document.querySelector("#vocabTable tbody");
  tbody.innerHTML = data
    .map(
      row => `
      <tr>
        <td>${row.latin_word}</td>
        <td>${row.german_translation}</td>
        <td>${row.word_type}</td>
        <td>${row.accuracy_percent.toFixed(1)}%</td>
        <td>${row.has_bronze_card ? "🟤" : ""}</td>
        <td>
          <button class="small-btn" data-action="edit" data-id="${row.id}">Edit</button>
          <button class="small-btn" data-action="delete" data-id="${row.id}">Delete</button>
        </td>
      </tr>
    `
    )
    .join("");

  tbody.querySelectorAll('button[data-action="edit"]').forEach(btn => {
    btn.onclick = () => editVocab(btn.dataset.id);
  });
  tbody.querySelectorAll('button[data-action="delete"]').forEach(btn => {
    btn.onclick = () => deleteVocab(btn.dataset.id);
  });
}

function attachSortListeners() {
  document.querySelectorAll(".sortable").forEach(th => {
    th.onclick = () => {
      const col = th.dataset.col;
      if (currentSortCol === col) {
        currentSortDir = currentSortDir === "asc" ? "desc" : "asc";
      } else {
        currentSortCol = col;
        currentSortDir = "asc";
      }
      document
        .querySelectorAll(".sortable")
        .forEach(h => h.classList.remove("sort-asc", "sort-desc"));
      th.classList.add(`sort-${currentSortDir}`);
      loadVocab();
    };
  });
}

async function editVocab(id) {
  const currentRow = Array.from(
    document.querySelectorAll("#vocabTable tbody tr")
  ).find(tr => tr.querySelector("button[data-id='" + id + "']"));

  if (!currentRow) return;

  const latinCell  = currentRow.children[0];
  const germanCell = currentRow.children[1];

  const currentLatin  = latinCell.textContent;
  const currentGerman = germanCell.textContent;

  const newLatin = prompt("Edit Latin word:", currentLatin);
  if (newLatin === null) return;

  const newGerman = prompt("Edit German translation:", currentGerman);
  if (newGerman === null) return;

  const res = await fetch(`${API_BASE}/vocab/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      latin_word: newLatin,
      german_translation: newGerman
    })
  });

  if (!res.ok) {
    alert("Error updating vocab entry.");
    return;
  }

  await loadVocab();
}

async function deleteVocab(id) {
  if (!confirm("Really delete this vocab entry?")) return;

  const res = await fetch(`${API_BASE}/vocab/${id}`, { method: "DELETE" });

  if (!res.ok) {
    alert("Error deleting vocab entry.");
    return;
  }

  await loadVocab();
}

// Add vocab form
document.getElementById("addVocabForm").onsubmit = async e => {
  e.preventDefault();
  const latin  = e.target.latin.value.trim();
  const german = e.target.german.value.trim();
  if (!latin) return alert("Latin required");

  const body = { latin_word: latin };
  if (german) body.german_translation = german;

  const res  = await fetch(`${API_BASE}/vocab/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await res.json();

  if (data.translations && data.translations.length) {
    showTranslationButtons(
      data.latin_word,
      data.translations,
      data.word_type,
      data.flexion_type
    );
  } else {
    e.target.reset();
    loadVocab();
  }
};

function showTranslationButtons(latin, translations, word_type, flexion_type) {
  document.getElementById("addVocabForm").style.display = "none";
  document.getElementById("translationOptions").style.display = "block";

  const buttonsDiv = document.getElementById("transButtons");
  buttonsDiv.innerHTML = translations
    .map(
      (trans, i) => `
    <button class="trans-btn"
      onclick="selectTranslation('${latin}', '${trans}', '${word_type}', '${flexion_type}')">
      ${i + 1}. ${trans}
    </button>
  `
    )
    .join("<br>");
}

async function selectTranslation(latin, german, word_type, flexion_type) {
  await fetch(`${API_BASE}/vocab/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      latin_word: latin,
      german_translation: german,
      word_type,
      flexion_type
    })
  });

  document.getElementById("translationOptions").style.display = "none";
  const form = document.getElementById("addVocabForm");
  form.style.display = "block";
  form.reset();
  loadVocab();
}

/* -------------------- Multiple Choice Quiz -------------------- */

async function startQuizFlow() {
  console.log("startQuizFlow called");
  const startRes  = await fetch(`${API_BASE}/quiz/start`, { method: "POST" });
  const startData = await startRes.json();
  quizRoundId     = startData.quiz_round_id;
  mcVerbCount     = 0;
  document.getElementById("mcCounter").textContent = "";
  showSection("quiz");
  await loadNextMCQuestion();
}

function showCurrentQuestionStandalone(q) {
  const wordDiv     = document.getElementById("quizWord");
  const optionsDiv  = document.getElementById("quizOptions");
  const feedbackDiv = document.getElementById("quizFeedback");

  wordDiv.textContent     = q.latin_word;
  feedbackDiv.textContent = "";

  optionsDiv.style.cssText = `
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 15px !important;
    justify-content: center !important;
    align-items: center !important;
    margin: 30px 0 !important;
    padding: 20px !important;
    min-height: 120px
  `;

  optionsDiv.innerHTML = "";
  q.options.forEach(opt => {
    const btn = document.createElement("button");
    btn.textContent = opt;
    btn.className   = "quiz-option-btn";
    btn.onclick     = () => submitChoice(opt, q);
    btn.style.margin = "0 !important";
    btn.style.flex   = "0 0 auto";
    optionsDiv.appendChild(btn);
  });
}

async function loadNextMCQuestion() {
  if (mcVerbCount >= 3) {
    document.getElementById("quizFeedback").textContent =
      "Multiple choice quiz complete! (3 words)";
    alert("Multiple choice quiz complete!");
    await fetch(`${API_BASE}/quiz/finish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quiz_round_id: quizRoundId })
    });
    loadVocab();
    showSection("vocab");
    return;
  }

  const qRes         = await fetch(`${API_BASE}/quiz/next?quizroundid=${quizRoundId}`);
  const newQuestions = await qRes.json();
  if (!newQuestions || newQuestions.length === 0) {
    document.getElementById("quizFeedback").textContent = "No more questions.";
    return;
  }

  const q = newQuestions[0];
  showCurrentQuestionStandalone(q);
  document.getElementById("quizFeedback").textContent =
    `Choose the right answer! (${mcVerbCount + 1}/3 words)`;
  mcVerbCount++;
  document.getElementById("mcCounter").textContent = `${mcVerbCount}/3`;
  document.getElementById("btnNextQuestion").style.display = "none";
}

async function submitChoice(selectedOption, q) {
  const res  = await fetch(`${API_BASE}/quiz/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quiz_round_id: quizRoundId,
      vocab_entry_id: q.id,
      selected_option: selectedOption
    })
  });
  const data = await res.json();

  let msg = data.correct ? "Correct!" : "Wrong.";
  msg += ` | Accuracy now: ${data.accuracy_percent.toFixed(1)}%`;
  if (data.card_change === "created") {
    msg += " | Bronze card unlocked!";
  } else if (data.card_change === "removed") {
    msg += " | Bronze card lost (accuracy below 90%).";
  }

  document.getElementById("quizFeedback").textContent = msg;

  document.querySelectorAll(".quiz-option-btn").forEach(b => (b.disabled = true));
  document.getElementById("btnNextQuestion").style.display = "block";
}

document.getElementById("btnNextQuestion").onclick = async () => {
  document.getElementById("btnNextQuestion").style.display = "none";
  await loadNextMCQuestion();
};

/* -------------------- Cards -------------------- */

async function loadCards() {
  const res   = await fetch(`${API_BASE}/cards/`);
  const cards = await res.json();
  const grid  = document.getElementById("cardsGrid");
  grid.innerHTML = "";
  cards.forEach(c => {
    const div = document.createElement("div");
    div.innerHTML = `
      <div>
        <img src="${c.image_url}" alt="${c.title}" style="width:120px;height:auto;">
        <div>${c.title} – ${c.german_translation}</div>
      </div>
    `;
    grid.appendChild(div);
  });
  showSection("cards");
}

/* -------------------- Verb Sorting Quiz -------------------- */

async function startSortingQuiz() {
  const res = await fetch(`${API_BASE}/quiz/verbs/start`, { method: "POST" });
  sortingRoundId      = (await res.json()).quizroundid;
  sortingVerbCount    = 0;
  document.getElementById("sortingCounter").textContent = "";
  await loadNextSortingVerb();
}

async function loadNextSortingVerb() {
  if (sortingVerbCount >= 3) {
    document.getElementById("sortingFeedback").textContent =
      "Sorting quiz complete! (3 verbs)";
    document.getElementById("sortingCounter").textContent = "";
    alert("Sorting quiz complete!");
    loadVocab();
    showSection("vocab");
    return;
  }

  const res  = await fetch(
    `${API_BASE}/quiz/verbs/next?quizroundid=${sortingRoundId}`
  );
  const data = await res.json();
  if (data.error) {
    document.getElementById("sortingFeedback").textContent = data.error;
    alert("Sorting quiz complete! All verbs covered.");
    loadVocab();
    showSection("vocab");
    return;
  }

  sortingVerbCount++;
  currentVerbData = data;
  document.getElementById("verbCard").textContent = data.verb;
  document.getElementById("sortingCounter").textContent =
    `${sortingVerbCount}/3`;
  document.getElementById("sortingFeedback").textContent =
    `Drag to category! (${sortingVerbCount}/3 verbs)`;
  resetVerbCategories();
  document.getElementById("btnNextVerb").style.display = "none";
}

function resetVerbCategories() {
  document.querySelectorAll("#sortingQuizArea .category-box").forEach(box => {
    box.classList.remove("correct", "wrong");
    box.innerHTML = box.dataset.category;
  });
}

async function handleVerbDrop(e) {
  e.preventDefault();
  const box      = e.currentTarget;
  const category = box.dataset.category;

  const res    = await fetch(`${API_BASE}/quiz/verbs/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quizroundid: sortingRoundId,
      verb: currentVerbData.verb,
      category
    })
  });
  const result = await res.json();

  box.classList.add(result.correct ? "correct" : "wrong");
  box.innerHTML = `${box.dataset.category} (${result.message})`;
  document.getElementById("sortingFeedback").innerHTML =
    `<strong>${result.message}</strong> ${result.score.toFixed(1)}%`;
  document.getElementById("btnNextVerb").style.display = "inline-block";
}

document.getElementById("verbCard").addEventListener("dragstart", e => {
  e.dataTransfer.setData("text/plain", "");
});

document
  .querySelectorAll("#sortingQuizArea .category-box")
  .forEach(box => {
    box.addEventListener("dragover", e => e.preventDefault());
    box.addEventListener("drop", handleVerbDrop);
  });

document.getElementById("btnNextVerb").onclick = () => {
  document.getElementById("btnNextVerb").style.display = "none";
  loadNextSortingVerb();
};

/* -------------------- Noun Sorting Quiz -------------------- */

async function startNounsQuiz() {
  const res = await fetch(`${API_BASE}/quiz/nouns/start`, { method: "POST" });
  nounsRoundId = (await res.json()).quizroundid;
  nounsCount   = 0;
  await loadNextNounsNoun();
}

async function loadNextNounsNoun() {
  // ✅ STOP after 3 nouns (exact verb match)
  if (nounsCount >= 3) {
    document.getElementById("nounsFeedback").textContent = "Noun quiz complete! (3 nouns)";
    document.getElementById("nounsCounter").textContent = "";
    alert("Noun Sorting Quiz complete!");
    loadVocab();
    showSection("vocab");
    return;
  }

  const res  = await fetch(`${API_BASE}/quiz/nouns/next?quizroundid=${nounsRoundId}`);
  const data = await res.json();
  if (data.error) {
    alert(data.error);
    loadVocab();
    showSection("vocab");
    return;
  }

  currentNounData = data;
  document.getElementById("nounCard").textContent = data.noun;
  document.getElementById("nounsCounter").textContent = `${++nounsCount}/3`;  // ✅ Increments 1→2→3
  document.getElementById("nounsFeedback").textContent = "Drag to declension!";
  resetNounCategories();
  document.getElementById("btnNextNoun").style.display = "none";
}

function resetNounCategories() {
  document.querySelectorAll("#nounCategories .category-box").forEach(box => {
    box.classList.remove("correct", "wrong");
    box.innerHTML = box.dataset.category;
  });
}

async function handleNounDrop(e) {
  e.preventDefault();
  const box      = e.currentTarget;
  const category = box.dataset.category;

  const res    = await fetch(`${API_BASE}/quiz/nouns/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quizroundid: nounsRoundId,
      noun: currentNounData.noun,
      category
    })
  });
  const result = await res.json();

  box.classList.add(result.correct ? "correct" : "wrong");
  box.innerHTML = result.message;
  document.getElementById("nounsFeedback").innerHTML =
    `Accuracy: ${result.score.toFixed(1)}`;
  document.getElementById("btnNextNoun").style.display = "inline-block";
}

document.getElementById("nounCard").addEventListener("dragstart", e => {
  e.dataTransfer.setData("text/plain", "");
});

document
  .querySelectorAll("#nounsQuizArea .category-box")
  .forEach(box => {
    box.addEventListener("dragover", e => e.preventDefault());
    box.addEventListener("drop", handleNounDrop);
  });

document.getElementById("btnNextNoun").onclick = () => {
  document.getElementById("btnNextNoun").style.display = "none";
  loadNextNounsNoun();
};

/* -------------------- Initial Load -------------------- */

loadVocab();
showSection("vocab");
