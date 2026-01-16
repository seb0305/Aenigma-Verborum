console.log("script.js loaded");

const API_BASE = "http://localhost:5000/api";

let currentUserId = null;
let currentUsername = 'Guest (Demo)';
let quizRoundId = null;
let mcVerbCount = 0;
let sortingVerbCount = 0;
let nounsRoundId = null;
let nounsCount = 0;
let currentNounData = null;
let currentVerbData = {};
let sortingRoundId = null;
let mcTargetLength = 0;
let sortingTargetLength = 0;
let nounsTargetLength = 0;

async function checkAuth() {
  try {
    const res = await fetch(`${API_BASE}/auth/status`);
    const data = await res.json();
    if (data.success && data.user_id) {
      currentUserId = data.user_id;
      currentUsername = data.username;
      const statusEl = document.getElementById('userStatus');
      statusEl.innerHTML = `👋 ${data.username} <button onclick="logout()" style="margin-left:10px;font-size:12px;padding:2px 8px;background:#dc3545;color:white;border:none;border-radius:3px;cursor:pointer;">Logout</button>`;
      statusEl.className = 'logged-in';
    }
  } catch(e) {
    console.log('No auth endpoint or guest mode OK');
  }
}

function addVocabFormSubmit(e) {
  e.preventDefault();
  // Inline your form logic here or call existing handler
  document.getElementById("addVocabForm").dispatchEvent(new Event('submit'));
}


// 🔥 DOM-Elemente werden in DOMContentLoaded initialisiert
let vocabSection, quizSection, cardsSection, sortingSection, nounsSection;

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM ready – Aenigma Verborum initialisiert');

    // 🔥 ALLE Elemente jetzt holen (garantiert existent)
    vocabSection = document.getElementById("vocabSection");
    quizSection = document.getElementById("quizSection");
    cardsSection = document.getElementById("cardsSection");
    sortingSection = document.getElementById("sortingSection");
    nounsSection = document.getElementById("nounsSection");

    // 🔥 Event-Handler Setup
    setupAuthHandlers();
    setupNavigationHandlers();
    setupDragDropHandlers();
    setupVocabHandlers();

    // 🔥 Initial Load
    checkAuth().then(() => {
        console.log("Auth complete → Vocab laden...");
        loadVocab();
        showSection("vocab");
    }).catch(err => {
        console.error("Auth failed:", err);
        loadVocab();
        showSection("vocab");
    });
});

function setupAuthHandlers() {
    document.getElementById('toggleAuth').onclick = toggleAuthMode;
    document.getElementById('authModal').onclick = closeModalOnOutsideClick;
    document.getElementById('loginBtn').onclick = () => {
        document.getElementById('authModal').style.display = 'block';
    };
    document.getElementById('authSubmit').onclick = handleAuthSubmit;
}

async function handleAuthSubmit() {
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const title = document.getElementById('authTitle').textContent.trim();
  const isLogin = title === 'Login';

  if (username.length < 3 || password.length < 6) {
    return alert(`Min lengths: username 3, password 6`);
  }

  try {
    const endpoint = isLogin ? 'login' : 'register';
    const res = await fetch(`${API_BASE}/auth/${endpoint}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username, password})
    });
    const data = await res.json();

    if (data.success) {
      currentUserId = data.user_id;
      currentUsername = data.username;

      // ✅ LOGGED-IN ONLY: Green status + logout button
      const statusEl = document.getElementById('userStatus');
      statusEl.innerHTML = `👋 ${data.username} <button onclick="logout()" style="margin-left:10px;font-size:12px;padding:2px 8px;background:#dc3545;color:white;border:none;border-radius:3px;cursor:pointer;">Logout</button>`;
      statusEl.className = 'logged-in';

      document.getElementById('authModal').style.display = 'none';
      document.getElementById('username').value = '';
      document.getElementById('password').value = '';

      showSection('vocab');
      loadVocab();
      console.log(`${endpoint} success → user ${data.username}`);
    } else {
      alert(data.message || `${endpoint} failed`);
    }
  } catch (err) {
    console.error('Auth error:', err);
    alert('Network/Server error');
  }
}


async function logout() {
  try {
    await fetch(`${API_BASE}/auth/logout`, {method: 'POST'});
  } catch(e) { console.log('Logout ok'); }  // Ignore errors

  currentUserId = null;
  currentUsername = 'Guest (Demo)';
  const statusEl = document.getElementById('userStatus');
  statusEl.innerHTML = 'Guest (Demo)';  // Clear button
  statusEl.className = 'guest';

  showSection('vocab');
  loadVocab();
}


function setupNavigationHandlers() {
    const handlers = {
        btnHomeVocab: () => { showSection("vocab"); loadVocab(); },
        btnHomeQuiz: startQuizFlow,
        btnHomeSorting: () => { showSection("sorting"); startSortingQuiz(); },
        btnHomeNounSorting: () => { showSection("nouns"); startNounsQuiz(); },
        btnHomeCards: loadCards,
        btnNextQuestion: nextMCQuestion,
        btnNextVerb: nextSortingVerb,
        btnNextNoun: nextNounsNoun
    };

    Object.entries(handlers).forEach(([id, handler]) => {
        const el = document.getElementById(id);
        if (el) {
            if (id.startsWith('btnNext')) {
                el.onclick = () => { el.style.display = 'none'; handler(); };
            } else {
                el.onclick = handler;
            }
            console.log(`✅ Attached handler to #${id}`);
        } else {
            console.warn(`❌ Element #${id} not found`);
        }
    });
}


function setupDragDropHandlers() {
    // Verb sorting
    const verbCard = document.getElementById("verbCard");
    if (verbCard) {
        verbCard.addEventListener("dragstart", dragStartHandler);
        console.log("✅ Verb drag attached");
    }

    document.querySelectorAll("#sortingQuizArea .category-box").forEach(box => {
        box.addEventListener("dragover", dragOverHandler);
        box.addEventListener("drop", handleVerbDrop);
        console.log("✅ Verb drop attached to", box.dataset.category);
    });

    // Noun sorting
    const nounCard = document.getElementById("nounCard");
    if (nounCard) {
        nounCard.addEventListener("dragstart", dragStartHandler);
        console.log("✅ Noun drag attached");
    }

    document.querySelectorAll("#nounsQuizArea .category-box").forEach(box => {
        box.addEventListener("dragover", dragOverHandler);
        box.addEventListener("drop", handleNounDrop);
        console.log("✅ Noun drop attached to", box.dataset.category);
    });
}


function setupVocabHandlers() {
    attachTypeFilters();  // Wird bei loadVocab() erweitert
}

function toggleAuthMode() {
    const title = document.getElementById('authTitle');
    title.textContent = title.textContent === 'Login' ? 'Register' : 'Login';
}

function closeModalOnOutsideClick(e) {
    if (e.target.id === 'authModal') {
        e.target.style.display = 'none';
    }
}

function dragStartHandler(e) {
    e.dataTransfer.setData("text/plain", "");
}

function dragOverHandler(e) {
    e.preventDefault();
}

function nextMCQuestion() {
    document.getElementById("btnNextQuestion").style.display = "none";
    loadNextMCQuestion();
}

function nextSortingVerb() {
    document.getElementById("btnNextVerb").style.display = "none";
    loadNextSortingVerb();
}

function nextNounsNoun() {
    document.getElementById("btnNextNoun").style.display = "none";
    resetNounCategories();
    loadNextNounsNoun();
}


// Show/hide sections
function showSection(name) {
    console.log("showSection", name);
    vocabSection.style.display = name === "vocab" ? "block" : "none";
    quizSection.style.display = name === "quiz" ? "block" : "none";
    cardsSection.style.display = name === "cards" ? "block" : "none";
    sortingSection.style.display = name === "sorting" ? "block" : "none";
    nounsSection.style.display = name === "nouns" ? "block" : "none";
}

/* -------------------- Vocab Book -------------------- */

let currentSortCol = null;
let currentSortDir = "asc";

async function loadVocab() {
  const res = await fetch(`${API_BASE}/vocab/`);
  const data = await res.json();
  renderVocabTable(data);
  attachSortListeners();
  attachTypeFilters();
}

function attachTypeFilters() {
  document.querySelectorAll(".type-radio").forEach(radio => {
    radio.onchange = filterByType;
  });
  filterByType();  // Initial "All"
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

  const latinCell = currentRow.children[0];
  const germanCell = currentRow.children[1];

  const currentLatin = latinCell.textContent;
  const currentGerman = germanCell.textContent;

  const newLatin = prompt("Edit Latin word:", currentLatin);
  if (newLatin === null) return;

  const newGerman = prompt("Edit German translation:", currentGerman);
  if (newGerman === null) return;

  const res = await fetch(`${API_BASE}/vocab/${id}`, {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
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

  const res = await fetch(`${API_BASE}/vocab/${id}`, {method: "DELETE"});

  if (!res.ok) {
    alert("Error deleting vocab entry.");
    return;
  }

  await loadVocab();
}

// Add vocab form
document.getElementById("addVocabForm").onsubmit = async e => {
  e.preventDefault();
  const latin = e.target.latin.value.trim();
  const german = e.target.german.value.trim();
  if (!latin) return alert("Latin required");

  const body = {latin_word: latin};
  if (german) body.german_translation = german;

  const res = await fetch(`${API_BASE}/vocab/`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
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
    headers: {"Content-Type": "application/json"},
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
  const startRes = await fetch(`${API_BASE}/quiz/start`, {method: "POST"});
  const startData = await startRes.json();
  quizRoundId = startData.quiz_round_id;
  mcTargetLength = startData.target_length;
  mcVerbCount = 0;
  document.getElementById("mcCounter").textContent = `0/${mcTargetLength}`;
  showSection("quiz");
  await loadNextMCQuestion();
}

function showCurrentQuestionStandalone(q) {
  const wordDiv = document.getElementById("quizWord");
  const optionsDiv = document.getElementById("quizOptions");
  const feedbackDiv = document.getElementById("quizFeedback");

  wordDiv.textContent = q.latin_word;
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
    btn.className = "quiz-option-btn";
    btn.onclick = () => submitChoice(opt, q);
    btn.style.margin = "0 !important";
    btn.style.flex = "0 0 auto";
    optionsDiv.appendChild(btn);
  });
}

async function loadNextMCQuestion() {
  if (mcVerbCount >= mcTargetLength) {
    document.getElementById("quizFeedback").textContent =
        "Multiple choice quiz complete!";
    alert("Multiple choice quiz complete!");
    await fetch(`${API_BASE}/quiz/finish`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({quiz_round_id: quizRoundId})
    });
    loadVocab();
    showSection("vocab");
    return;
  }

  const qRes = await fetch(`${API_BASE}/quiz/next?quizroundid=${quizRoundId}`);
  const response = await qRes.json();
  if (response.error) {
    document.getElementById("quizFeedback").textContent = response.error;
    return;
  }
  const q = response.question;
  showCurrentQuestionStandalone(q);
  document.getElementById("quizFeedback").textContent =
      `Choose right answer! (${mcVerbCount + 1}/${mcTargetLength})`;  // ✅ Closed + mcTargetLength
  mcVerbCount++;
  document.getElementById("mcCounter").textContent =
      `${mcVerbCount}/${mcTargetLength}`;  // ✅ Closed + mcTargetLength
  document.getElementById("btnNextQuestion").style.display = "none";
}

async function submitChoice(selectedOption, q) {
  const res = await fetch(`${API_BASE}/quiz/answer`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
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

/* -------------------- Verb Sorting Quiz -------------------- */

async function startSortingQuiz() {
  const res = await fetch(`${API_BASE}/quiz/verbs/start`, {method: "POST"});
  const startData = await res.json();
  sortingRoundId = startData.quiz_round_id;  // ✅ Consistent snake_case
  sortingTargetLength = startData.target_length;  // ✅ Local var
  sortingVerbCount = 0;
  document.getElementById("sortingCounter").textContent = `0/${sortingTargetLength}`;
  showSection("sorting");
  setupDragDropHandlers();
  await loadNextSortingVerb();
}

async function loadNextSortingVerb() {
  if (sortingVerbCount >= sortingTargetLength) {
    document.getElementById("sortingFeedback").textContent = "Sorting quiz complete!";
    document.getElementById("sortingCounter").textContent = "";
    alert(`Sorting complete! (${sortingVerbCount}/${sortingTargetLength})`);
    await fetch(`${API_BASE}/quiz/finish`, {  // ✅ Finish API
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({quiz_round_id: sortingRoundId})
    });
    await loadVocab();
    showSection("vocab");
    return;
  }

  const res = await fetch(`${API_BASE}/quiz/verbs/next?quizroundid=${sortingRoundId}`);
  const data = await res.json();
  if (data.error) {
    document.getElementById("sortingFeedback").textContent = data.error;
    return;
  }

  sortingVerbCount++;
  currentVerbData = data;
  document.getElementById("verbCard").textContent = data.verb;
  document.getElementById("sortingCounter").textContent = `${sortingVerbCount}/${sortingTargetLength}`;
  document.getElementById("sortingFeedback").textContent =
      `Drag to category! (${sortingVerbCount}/${sortingTargetLength})`;
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
  const box = e.currentTarget;
  const category = box.dataset.category;

  const res = await fetch(`${API_BASE}/quiz/verbs/answer`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
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
  const res = await fetch(`${API_BASE}/quiz/nouns/start`, {method: "POST"});
  const startData = await res.json();
  nounsRoundId = startData.quiz_round_id;  // ✅ snake_case
  nounsTargetLength = startData.target_length;
  nounsCount = 0;
  document.getElementById("nounsCounter").textContent = `0/${nounsTargetLength}`;
  showSection("nouns");
    setupDragDropHandlers();
  await loadNextNounsNoun();  // ✅ Pass
}

function resetNounCategories() {
  document.querySelectorAll("#nounsQuizArea .category-box").forEach(box => {
    box.classList.remove("correct", "wrong");
    box.innerHTML = box.dataset.category;
  });
}

async function loadNextNounsNoun() {
  if (nounsCount >= nounsTargetLength) {
    document.getElementById("nounsFeedback").textContent = "Noun quiz complete!";
    document.getElementById("nounsCounter").textContent = "";
    alert(`Noun quiz complete! (${nounsCount}/${nounsTargetLength})`);
    await fetch(`${API_BASE}/quiz/finish`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({quiz_round_id: nounsRoundId})
    });
    loadVocab();
    showSection("vocab");
    return;
  }

  const res = await fetch(`${API_BASE}/quiz/nouns/next?quizroundid=${nounsRoundId}`);
  const data = await res.json();
  if (data.error) {
    document.getElementById("nounsFeedback").textContent = data.error;
    return;
  }

  currentNounData = data;
  document.getElementById("nounCard").textContent = data.noun;
  nounsCount++;  // ✅ Increment AFTER backend fetch (post-answer)
  document.getElementById("nounsCounter").textContent = `${nounsCount}/${nounsTargetLength}`;
  document.getElementById("nounsFeedback").textContent =
      `Drag to declension! (${nounsCount}/${nounsTargetLength})`;
  resetNounCategories();
  document.getElementById("btnNextNoun").style.display = "none";
}


async function handleNounDrop(e) {
  e.preventDefault();
  const box = e.currentTarget;
  const category = box.dataset.category;

  const res = await fetch(`${API_BASE}/quiz/nouns/answer`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
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
  resetNounCategories();
  loadNextNounsNoun();
};
