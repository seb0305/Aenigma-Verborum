console.log("script.js loaded");

const API_BASE = "http://localhost:5000/api";

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

document.getElementById("btnHomeVocab").onclick = () => showSection("vocab");
document.getElementById("btnHomeQuiz").onclick = () => startQuizFlow();
document.getElementById("btnHomeCards").onclick = () => loadCards();

function showSection(name) {
  vocabSection.style.display = name === "vocab" ? "block" : "none";
  quizSection.style.display = name === "quiz" ? "block" : "none";
  cardsSection.style.display = name === "cards" ? "block" : "none";
}

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
    `;
    tbody.appendChild(tr);
  });
  showSection("vocab");
}

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
    // For M1 you can manually type the chosen one and submit again
  } else {
    e.target.reset();
    loadVocab();
  }
};


let quizRoundId = null;
let quizQuestions = [];
let currentIndex = 0;

async function startQuizFlow() {
  // start round
  const startRes = await fetch(`${API_BASE}/quiz/start`, { method: "POST" });
  const startData = await startRes.json();
  quizRoundId = startData.quiz_round_id;

  const qRes = await fetch(`${API_BASE}/quiz/next`);
  quizQuestions = await qRes.json();
  currentIndex = 0;

  if (quizQuestions.length === 0) {
    alert("No weak words yet. Add vocab first.");
    return;
  }
  showSection("quiz");
  showCurrentQuestion();
}

function showCurrentQuestion() {
  const q = quizQuestions[currentIndex];
  document.getElementById("quizWord").textContent = q.latin_word;
  document.getElementById("quizAnswer").value = "";
  document.getElementById("quizFeedback").textContent = "";
  document.getElementById("btnNextQuestion").style.display = "none";
}

document.getElementById("btnSubmitAnswer").onclick = async () => {
  const q = quizQuestions[currentIndex];
  const ans = document.getElementById("quizAnswer").value;

  const res = await fetch(`${API_BASE}/quiz/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quiz_round_id: quizRoundId,
      vocab_entry_id: q.id,
      user_answer: ans
    })
  });
  const data = await res.json();

  let msg = data.correct ? "Correct!" : `Wrong. Correct: ${q.german_translation}`;
  msg += ` | Accuracy now: ${data.accuracy_percent.toFixed(1)}%`;
  if (data.card_unlocked) {
    msg += " | Bronze card unlocked!";
  }
  document.getElementById("quizFeedback").textContent = msg;
  document.getElementById("btnNextQuestion").style.display = "inline-block";
};

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
  } else {
    showCurrentQuestion();
  }
};


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

// auto-load vocab first
loadVocab();
