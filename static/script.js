console.log("script.js loaded");

const API_BASE = "http://localhost:5000/api";

let quizRoundId = null;
let quizQuestions = [];
let currentIndex = 0;

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
document.getElementById("btnHomeSorting").onclick = () => showSection("sorting");
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

  const qRes = await fetch(`${API_BASE}/quiz/next`);
  quizQuestions = await qRes.json();
  console.log("quizQuestions:", quizQuestions);

  currentIndex = 0;

  if (!quizQuestions || quizQuestions.length === 0) {
    alert("No quiz questions available. Add vocab and/or lower accuracy first.");
    return;
  }

  showSection("quiz");
  showCurrentQuestion();
}

// Render one quiz question
function showCurrentQuestion() {
  console.log("showCurrentQuestion", currentIndex, quizQuestions[currentIndex]);
  const q = quizQuestions[currentIndex];

  const wordDiv = document.getElementById("quizWord");
  const optionsDiv = document.getElementById("quizOptions");
  const feedbackDiv = document.getElementById("quizFeedback");
  const nextBtn = document.getElementById("btnNextQuestion");

  console.log("DOM quiz elements:", wordDiv, optionsDiv, feedbackDiv, nextBtn);

  wordDiv.textContent = q.latin_word;
  feedbackDiv.textContent = "";
  nextBtn.style.display = "none";

  optionsDiv.innerHTML = "";
  q.options.forEach(opt => {
    const btn = document.createElement("button");
    btn.textContent = opt;
    btn.className = "quiz-option-btn";
    btn.onclick = () => submitChoice(opt, q);
    optionsDiv.appendChild(btn);
  });
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

  document.getElementById("btnNextQuestion").style.display = "inline-block";
}

// Next question button
document.getElementById("btnNextQuestion").onclick = async () => {
  currentIndex++;
  if (currentIndex >= quizQuestions.length) {
    await fetch(`${API_BASE}/quiz/finish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quiz_round_id: quizRoundId })
    });
    alert("Quiz finished!");
    loadVocab();
    showSection("vocab");
  } else {
    showCurrentQuestion();
  }
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

// 3 Test Verbs Data
const testVerbs = [
  { verb: 'audire', correct: 'I-Konjugation' },
  { verb: 'petere', correct: 'konsonantische Konjugation' },
  { verb: 'vocare', correct: 'A-Konjugation' }
];

let currentVerbIndex = 0;
let gameActive = false;

// Sorting Quiz Logic
document.addEventListener('DOMContentLoaded', function() {
  const verbCard = document.getElementById('verbCard');
  const feedback = document.getElementById('sortingFeedback');
  const nextBtn = document.getElementById('btnNextVerb');
  const categories = document.querySelectorAll('.category-box');

  // Start game with first verb
  function loadNextVerb() {
    if (currentVerbIndex >= testVerbs.length) {
      feedback.innerHTML = 'Quiz komplett! Alle 3 Verben gemeistert! 🎉';
      feedback.style.color = '#28a745';
      verbCard.style.display = 'none';
      nextBtn.style.display = 'none';
      return;
    }

    const verbData = testVerbs[currentVerbIndex];
    verbCard.textContent = verbData.verb;
    verbCard.style.display = 'flex';
    feedback.textContent = 'Drag to sort!';
    feedback.style.color = '#007bff';
    nextBtn.style.display = 'none';
    gameActive = true;

    resetCategories();
  }

  function resetCategories() {
    categories.forEach(box => {
      box.classList.remove('correct', 'wrong');
      box.innerHTML = box.dataset.category;
      box.style.background = '#f8f9fa';
    });
  }

  // Drag start
  verbCard.addEventListener('dragstart', function(e) {
    if (!gameActive) return;
    e.dataTransfer.setData('text/plain', JSON.stringify(testVerbs[currentVerbIndex]));
  });

  // Category events
  categories.forEach(box => {
    box.addEventListener('dragover', function(e) {
      if (!gameActive) return;
      e.preventDefault();
      this.style.background = '#e3f2fd';
    });

    box.addEventListener('dragleave', function(e) {
      this.style.background = '#f8f9fa';
    });

    box.addEventListener('drop', function(e) {
      if (!gameActive) return;
      e.preventDefault();
      this.style.background = '#f8f9fa';

      const verbData = JSON.parse(e.dataTransfer.getData('text/plain'));
      const selectedCategory = this.dataset.category;
      gameActive = false;

      // Check answer
      if (selectedCategory === verbData.correct) {
        this.classList.add('correct');
        this.innerHTML += ' ✓ Richtig!';
        feedback.innerHTML = `Perfekt! <strong>${verbData.verb}</strong> → <strong>${verbData.correct}</strong>`;
        feedback.style.color = '#28a745';
      } else {
        this.classList.add('wrong');
        this.innerHTML += ' ✗ Falsch';
        feedback.innerHTML = `${verbData.verb} gehört zur <strong>${verbData.correct}</strong>, nicht ${selectedCategory}`;
        feedback.style.color = '#dc3545';
      }

      nextBtn.style.display = 'inline-block';
    });
  });

  // Next verb button
  nextBtn.onclick = function() {
    currentVerbIndex++;
    loadNextVerb();
  };

  // Auto-start first verb when sorting section shows
  const sortingSection = document.getElementById('sortingSection');
  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
        if (sortingSection.style.display === 'block') {
          currentVerbIndex = 0;
          loadNextVerb();
        }
      }
    });
  });
  observer.observe(sortingSection, { attributes: true });
});



// initial load
loadVocab();
showSection("vocab");