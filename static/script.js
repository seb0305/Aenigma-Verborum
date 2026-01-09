console.log("script.js loaded");

const API_BASE = "http://localhost:5000/api";

let quizRoundId = null;
let mcVerbCount = 0;
let sortingVerbCount = 0;

/*
Vocab section calls /api/vocab/ to list and create VocabEntry rows
 */
const vocabSection = document.getElementById("vocabSection");
/*
Quiz section calls /api/quiz/
 */
const quizSection = document.getElementById("quizSection");
/*
Cards section calls /api/cards/ to read the joined UserCard + Card + VocabEntry data
 */
const cardsSection = document.getElementById("cardsSection");

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
document.getElementById("btnHomeCards").onclick = () => loadCards();

// Show/hide sections
function showSection(name) {
  console.log("showSection", name);
  vocabSection.style.display = name === "vocab" ? "block" : "none";
  quizSection.style.display  = name === "quiz"  ? "block" : "none";
  cardsSection.style.display = name === "cards" ? "block" : "none";
  document.getElementById("sortingSection").style.display = name === "sorting" ? "block" : "none";
}

// Load vocab table
async function loadVocab() {
  const res = await fetch(`${API_BASE}/vocab/`);
  const data = await res.json();
  const tbody = document.querySelector("#vocabTable tbody");
  tbody.innerHTML = "";
  data.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.latin_word}</td>
      <td>${row.german_translation}</td>
      <td>${row.accuracy_percent.toFixed(1)}%</td>
      <td>${row.has_bronze_card ? "🟤" : ""}</td>
      <td>
        <button class="small-btn" data-action="edit" data-id="${row.id}">Edit</button>
        <button class="small-btn" data-action="delete" data-id="${row.id}">Delete</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // attach click events for edit/delete
  tbody.querySelectorAll("button[data-action='edit']").forEach(btn => {
    btn.onclick = () => editVocab(btn.dataset.id);
  });
  tbody.querySelectorAll("button[data-action='delete']").forEach(btn => {
    btn.onclick = () => deleteVocab(btn.dataset.id);
  });
}

async function editVocab(id) {
  // simple prompt-based editing for Milestone 1
  const currentRow = Array.from(document.querySelectorAll("#vocabTable tbody tr"))
    .find(tr => tr.querySelector("button[data-id='" + id + "']"));

  if (!currentRow) return;

  const latinCell = currentRow.children[0];
  const germanCell = currentRow.children[1];

  const currentLatin = latinCell.textContent;
  const currentGerman = germanCell.textContent;

  const newLatin = prompt("Edit Latin word:", currentLatin);
  if (newLatin === null) return; // cancel

  const newGerman = prompt("Edit German translation:", currentGerman);
  if (newGerman === null) return; // cancel

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

  const res = await fetch(`${API_BASE}/vocab/${id}`, {
    method: "DELETE"
  });

  if (!res.ok) {
    alert("Error deleting vocab entry.");
    return;
  }

  await loadVocab();
}

// Add vocab form
document.getElementById("addVocabForm").onsubmit = async (e) => {
  e.preventDefault();
  const latin = e.target.latin.value;
  const german = e.target.german.value;

  const res = await fetch(`${API_BASE}/vocab/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      latin_word: latin,
      german_translation: german || null
    })
  });
  const data = await res.json();


  if (data.need_translation_choice) {
    alert("AI suggestions: " + data.suggestions.join(", "));
  } else {
    e.target.reset();
    loadVocab();
  }
};

// Start quiz (multiple choice)
async function startQuizFlow() {
  console.log("startQuizFlow called");
  const startRes = await fetch(`${API_BASE}/quiz/start`, { method: "POST" });
  const startData = await startRes.json();
  quizRoundId = startData.quiz_round_id;
  mcVerbCount = 0;
  document.getElementById('mcCounter').textContent = '';  // Clear
  showSection("quiz");
  await loadNextMCQuestion();  // Loads 1st, sets "1/3"
}

// Render one quiz question (Horizontal buttons like sorting)
function showCurrentQuestionStandalone(q) {
  console.log("showCurrentQuestionStandalone", q);
  const wordDiv = document.getElementById("quizWord");
  const optionsDiv = document.getElementById("quizOptions");
  const feedbackDiv = document.getElementById("quizFeedback");

  wordDiv.textContent = q.latin_word;
  feedbackDiv.textContent = "";

  // FORCE Horizontal Layout (matches .categories-container exactly)
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
    btn.className = "quiz-option-btn";
    btn.onclick = () => submitChoice(opt, q);
    btn.style.margin = "0 !important";  // Kill button margins
    btn.style.flex = "0 0 auto";        // Fixed size like .category-box
    optionsDiv.appendChild(btn);
  });
}

async function loadNextMCQuestion() {
  if (mcVerbCount >= 3) {
    // EXACT sorting match
    document.getElementById('quizFeedback').textContent = 'Multiple choice quiz complete! (3 words)';
    alert('Multiple choice quiz complete!');
    await fetch(`${API_BASE}/quiz/finish`, {  // Close round
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quiz_round_id: quizRoundId })
    });
    loadVocab();
    showSection('vocab');
    return;
  }

  const qRes = await fetch(`${API_BASE}/quiz/next?quizroundid=${quizRoundId}`);
  const newQuestions = await qRes.json();
  if (!newQuestions || newQuestions.length === 0) {
    document.getElementById('quizFeedback').textContent = 'No more questions.';
    return;
  }

  // Use first question (backend sends array, take [0])
  const q = newQuestions[0];
  showCurrentQuestionStandalone(q);  // New func below
  document.getElementById('quizFeedback').textContent = `Choose the right answer! (${mcVerbCount + 1}/3 words)`;  // Initial instruction
  mcVerbCount++;
  document.getElementById('mcCounter').textContent = `${mcVerbCount}/3`;

  document.getElementById('btnNextQuestion').style.display = 'none';
}


// Handle answer click
async function submitChoice(selectedOption, q) {
  const res = await fetch(`${API_BASE}/quiz/answer`, {
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

  // Disable buttons after answer
  const optionButtons = document.querySelectorAll(".quiz-option-btn");
  optionButtons.forEach(b => b.disabled = true);

  document.getElementById('btnNextQuestion').style.display = 'block';
}

// Next question button
document.getElementById("btnNextQuestion").onclick = async () => {
  document.getElementById("btnNextQuestion").style.display = 'none';
  await loadNextMCQuestion();  // Sequential next (no currentIndex)
};

// Load cards
async function loadCards() {
  const res = await fetch(`${API_BASE}/cards/`);
  const cards = await res.json();
  const grid = document.getElementById("cardsGrid");
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

// DB-Driven Sorting Quiz (ersetzt hardcoded)
let currentVerbData = {};
let sortingRoundId = null;

async function startSortingQuiz() {
  const res = await fetch(`${API_BASE}/quiz/verbs/start`, { method: 'POST' });
  sortingRoundId = (await res.json()).quizroundid;
  sortingVerbCount = 0;  // Reset
  document.getElementById('sortingCounter').textContent = '';  // Clear
  await loadNextSortingVerb();
}

async function loadNextSortingVerb() {
    // Stop after 3 verbs
  if (sortingVerbCount >= 3) {
    document.getElementById('sortingFeedback').textContent = 'Sorting quiz complete! (3 verbs)';
    document.getElementById('sortingCounter').textContent = '';
    alert('Sorting quiz complete!');
    loadVocab();
    showSection('vocab');
    return;
  }

  const res = await fetch(`${API_BASE}/quiz/verbs/next?quizroundid=${sortingRoundId}`);
  const data = await res.json();
  if (data.error) {
    document.getElementById('sortingFeedback').textContent = data.error;
    alert('Sorting quiz complete! All verbs covered.');
    loadVocab();
    showSection('vocab');
    return;
  }
  sortingVerbCount++;
  currentVerbData = data;
  document.getElementById('verbCard').textContent = data.verb;
  document.getElementById('sortingCounter').textContent = `${sortingVerbCount}/3`;  // Header counter
  document.getElementById('sortingFeedback').textContent = `Drag to category! (${sortingVerbCount}/3 verbs)`;
  resetCategories();
  // Re-attach drop listeners if needed
}


// Drag-Drop (update drop handler)
document.querySelectorAll('.category-box').forEach(box => {
  box.addEventListener('drop', async (e) => {
    e.preventDefault();
    const category = box.dataset.category;

    const res = await fetch(`${API_BASE}/quiz/verbs/answer`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        quizroundid: sortingRoundId,
        verb: currentVerbData.verb,  // ← FIX: currentVerbData!
        category
      })
    });

    const result = await res.json();
    box.classList.add(result.correct ? 'correct' : 'wrong');
    box.innerHTML += ` (${result.message})`;

    document.getElementById('sortingFeedback').innerHTML =
      `<strong>${result.message}</strong> ${result.score.toFixed(1)}%`;

    document.getElementById('btnNextVerb').style.display = 'inline-block';
  });
});

document.getElementById('btnNextVerb').onclick = loadNextSortingVerb;

function resetCategories() {
  document.querySelectorAll('.category-box').forEach(box => {
    box.classList.remove('correct', 'wrong');
    box.innerHTML = box.dataset.category;
  });
}

document.getElementById('verbCard').addEventListener('dragstart', e => {
  e.dataTransfer.setData('text/plain', '');  // Required for Firefox
});

document.querySelectorAll('.category-box').forEach(box => {
  box.addEventListener('dragover', e => e.preventDefault());
  box.addEventListener('drop', async e => {  // Existing async handler
    e.preventDefault();
    const category = box.dataset.category;
    try {
      const res = await fetch(`${APIBASE}/quiz/verbsanswer`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          quizroundid: sortingRoundId,
          verb: currentVerbData.verb,
          category: category
        })
      });
      const result = await res.json();
      box.classList.add(result.correct ? 'correct' : 'wrong');
      box.innerHTML = result.message;
      document.getElementById('sortingFeedback').innerHTML = `<strong>${result.message}</strong> ${result.score.toFixed(1)}%`;
      document.getElementById('btnNextVerb').style.display = 'inline-block';
    } catch (err) {
      console.error('Drop error:', err);
      document.getElementById('sortingFeedback').textContent = 'Error submitting answer';
    }
  });
});


// initial load
loadVocab();
showSection("vocab");