/**
 * Aenigma Verborum - Latin Vocabulary Learning App
 * Frontend JavaScript for interactive quizzes, vocabulary management, and drag-and-drop sorting games.
 * Connects to Flask backend API at http://localhost:5000/api
 */

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

// DOM elements (initialized after DOMContentLoaded)
let vocabSection, quizSection, cardsSection, sortingSection, nounsSection;
let currentSortCol = null;
let currentSortDir = "asc";

/**
 * Initialize application on DOM load
 */
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM ready – Aenigma Verborum initialized');
    
    // Initialize DOM elements and event handlers
    initDOMElements();
    setupEventHandlers();
    
    // Check authentication and show landing page
    await checkAuth();
    showSection("landing");
});

/**
 * Initialize references to DOM sections
 */
function initDOMElements() {
    vocabSection = document.getElementById("vocabSection");
    quizSection = document.getElementById("quizSection");
    cardsSection = document.getElementById("cardsSection");
    sortingSection = document.getElementById("sortingSection");
    nounsSection = document.getElementById("nounsSection");
}

/**
 * Setup all event handlers for authentication, navigation, drag-drop, and vocab
 */
function setupEventHandlers() {
    setupAuthHandlers();
    setupNavigationHandlers();
    setupDragDropHandlers();
    setupVocabHandlers();
}

/**
 * Check current authentication status
 */
async function checkAuth() {
    try {
        const res = await fetch(`${API_BASE}/auth/status`);
        const data = await res.json();
        if (data.success && data.user_id) {
            currentUserId = data.user_id;
            currentUsername = data.username;
            updateUserStatus(data.username, true);
        }
    } catch(e) {
        console.log('Guest mode active');
    }
}

/**
 * Update user status display with login/logout state
 */
function updateUserStatus(username, isLoggedIn) {
    const statusEl = document.getElementById('userStatus');
    if (isLoggedIn) {
        statusEl.innerHTML = `👋 ${username} <button onclick="logout()" style="margin-left:10px;font-size:12px;padding:2px 8px;background:#dc3545;color:white;border:none;border-radius:3px;cursor:pointer;">Logout</button>`;
        statusEl.className = 'logged-in';
    } else {
        statusEl.innerHTML = 'Guest (Demo)';
        statusEl.className = 'guest';
    }
}

/**
 * Setup authentication modal and form handlers
 */
function setupAuthHandlers() {
    document.getElementById('toggleAuth').onclick = toggleAuthMode;
    document.getElementById('authModal').onclick = closeModalOnOutsideClick;
    document.getElementById('loginBtn').onclick = () => {
        document.getElementById('authModal').style.display = 'block';
    };
    document.getElementById('authSubmit').onclick = handleAuthSubmit;
}

/**
 * Handle login/register form submission
 */
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
            updateUserStatus(data.username, true);
            
            document.getElementById('authModal').style.display = 'none';
            document.getElementById('username').value = '';
            document.getElementById('password').value = '';
            showSection('vocab');
            loadVocab();
        } else {
            alert(data.message || `${endpoint} failed`);
        }
    } catch (err) {
        console.error('Auth error:', err);
        alert('Network/Server error');
    }
}

/**
 * Logout current user
 */
async function logout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, {method: 'POST'});
    } catch(e) {
        console.log('Logout completed');
    }

    currentUserId = null;
    currentUsername = 'Guest (Demo)';
    updateUserStatus('', false);
    showSection('vocab');
    loadVocab();
}

/**
 * Toggle between login and register mode
 */
function toggleAuthMode() {
    const title = document.getElementById('authTitle');
    title.textContent = title.textContent === 'Login' ? 'Register' : 'Login';
}

/**
 * Close auth modal when clicking outside
 */
function closeModalOnOutsideClick(e) {
    if (e.target.id === 'authModal') {
        e.target.style.display = 'none';
    }
}

/**
 * Setup navigation button handlers
 */
function setupNavigationHandlers() {
    const handlers = {
        btnHomeLanding: () => showSection("landing"),
        btnStartFromLanding: startQuizFlow,
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
            el.onclick = id.startsWith('btnNext') 
                ? () => { el.style.display = 'none'; handler(); }
                : handler;
        }
    });
}

/**
 * Search vocabulary by Latin word
 */
async function searchVocab() {
    const input = document.getElementById('vocabSearchInput');
    const word = input.value.trim().toLowerCase();
    if (!word) return alert('Latin word eingeben');

    const loading = document.getElementById('searchLoading');
    const results = document.getElementById('searchResults');
    const info = document.getElementById('landingVocabInfo');

    loading.style.display = 'block';
    info.style.display = 'block';
    results.innerHTML = '';

    try {
        const res = await fetch(`${API_BASE}/kurzuebersicht/${word}`);  // ← Your working endpoint
        const data = await res.json();

        if (data.length === 0) {
            results.innerHTML = '<p>Keine Ergebnisse. Anderes Wort versuchen.</p>';
            return;
        }

        data.forEach(row => {
            const div = document.createElement('div');
            div.className = 'result-card';  // Dark CSS ready
            div.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                    <h3 style="margin: 0; font-size: 1.3em;">${row.latin}</h3>
                    <span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold;">${row.type}</span>
                </div>
                <p style="margin: 8px 0; font-size: 1.1em; color: #34d399; font-weight: 500;">${row.german}</p>
                <div style="font-size: 0.9em; color: #94a3b8; display: flex; flex-wrap: wrap; gap: 12px;">
                    <span>📚 ${row.flexion_type}</span>
                    <span>♀ ${row.Geschlecht}</span>
                    <span>📝 ${row.form}</span>
                </div>
                <!-- ➕ IMPORT BUTTON -->
                <button class="import-btn" data-latin="${row.latin}" style="margin-top: 16px;">
                    ➕ In Vocab Book importieren
                </button>
            `;
            results.appendChild(div);
        });

        document.querySelectorAll('.import-btn').forEach(btn => {
            btn.onclick = async function() {
                const latin = this.dataset.latin;
                this.disabled = true;
                this.textContent = '⏳ Importiere...';

                try {
                    const res = await fetch(`${API_BASE}/vocab/import/${latin}`, { method: 'POST' });
                    const json = await res.json();

                    if (json.status === 'imported') {
                        this.textContent = '✅ Importiert';
                        this.style.background = '#10b981';
                        loadVocab();  // Refresh table
                    } else {
                        this.textContent = '💾 Bereits da';
                        this.style.background = '#f59e0b';
                    }
                } catch (e) {
                    this.textContent = '❌ Fehler';
                    this.style.background = '#ef4444';
                }
                this.disabled = false;
            };
        });

    } catch(err) {
        results.innerHTML = '<p>Suche fehlgeschlagen. Console prüfen.</p>';
        console.error('Search error:', err);
    } finally {
        loading.style.display = 'none';
    }
}


/**
 * Setup drag and drop handlers for verb and noun sorting quizzes
 */
function setupDragDropHandlers() {
    // Verb sorting handlers
    const verbCard = document.getElementById("verbCard");
    if (verbCard) {
        verbCard.addEventListener("dragstart", dragStartHandler);
    }

    document.querySelectorAll("#sortingQuizArea .category-box").forEach(box => {
        box.addEventListener("dragover", dragOverHandler);
        box.addEventListener("drop", handleVerbDrop);
    });

    // Noun sorting handlers
    const nounCard = document.getElementById("nounCard");
    if (nounCard) {
        nounCard.addEventListener("dragstart", dragStartHandler);
    }

    document.querySelectorAll("#nounsQuizArea .category-box").forEach(box => {
        box.addEventListener("dragover", dragOverHandler);
        box.addEventListener("drop", handleNounDrop);
    });
}

/**
 * Setup vocabulary management handlers
 */
function setupVocabHandlers() {
    document.getElementById('vocabSearchBtn').onclick = searchVocab;
    document.getElementById('vocabSearchInput').onkeypress = (e) => {
        if (e.key === 'Enter') searchVocab();
    };
    document.getElementById("addVocabForm").onsubmit = handleAddVocab;
}

/**
 * Drag start handler for sortable cards
 */
function dragStartHandler(e) {
    e.dataTransfer.setData("text/plain", "");
}

/**
 * Drag over handler - prevent default to allow drop
 */
function dragOverHandler(e) {
    e.preventDefault();
}

/**
 * Show/hide specific section of the app
 */
function showSection(name) {
    const sections = {
        landing: document.getElementById("landingSection"),
        vocab: vocabSection,
        quiz: quizSection,
        cards: cardsSection,
        sorting: sortingSection,
        nouns: nounsSection
    };

    Object.entries(sections).forEach(([key, element]) => {
        if (element) {
            element.style.display = key === name ? "block" : "none";
        }
    });
}

/* ==================== VOCABULARY MANAGEMENT ==================== */

/**
 * Load and display vocabulary table
 */
async function loadVocab() {
    const res = await fetch(`${API_BASE}/vocab/`);
    const data = await res.json();
    renderVocabTable(data);
    attachSortListeners();
    attachTypeFilters();
}

/**
 * Attach sorting listeners to table headers
 */
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
            document.querySelectorAll(".sortable").forEach(h => h.classList.remove("sort-asc", "sort-desc"));
            th.classList.add(`sort-${currentSortDir}`);
            loadVocab();
        };
    });
}

/**
 * Attach type filter radio button listeners
 */
function attachTypeFilters() {
    document.querySelectorAll(".type-radio").forEach(radio => {
        radio.onchange = filterByType;
    });
    filterByType(); // Apply initial "All" filter
}

/**
 * Filter vocab table by word type
 */
function filterByType() {
    const selectedType = document.querySelector('input[name="typeFilter"]:checked').value;
    document.querySelectorAll("#vocabTable tbody tr").forEach(row => {
        const typeCell = row.cells[2].textContent.toLowerCase();
        row.style.display = selectedType === "all" || typeCell === selectedType ? "" : "none";
    });
}

/**
 * Render vocabulary data into sortable table
 */
function renderVocabTable(data) {
    // Apply current sorting
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
    tbody.innerHTML = data.map(row => `
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
    `).join("");

    // Attach edit/delete handlers
    tbody.querySelectorAll('button[data-action="edit"]').forEach(btn => {
        btn.onclick = () => editVocab(btn.dataset.id);
    });
    tbody.querySelectorAll('button[data-action="delete"]').forEach(btn => {
        btn.onclick = () => deleteVocab(btn.dataset.id);
    });
}

/**
 * Edit existing vocabulary entry
 */
async function editVocab(id) {
    const currentRow = Array.from(document.querySelectorAll("#vocabTable tbody tr"))
        .find(tr => tr.querySelector(`button[data-id='${id}']`));

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

/**
 * Delete vocabulary entry
 */
async function deleteVocab(id) {
    if (!confirm("Really delete this vocab entry?")) return;

    const res = await fetch(`${API_BASE}/vocab/${id}`, {method: "DELETE"});

    if (!res.ok) {
        alert("Error deleting vocab entry.");
        return;
    }

    await loadVocab();
}

/**
 * Handle new vocabulary form submission
 */
async function handleAddVocab(e) {
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
        showTranslationButtons(data.latin_word, data.translations, data.word_type, data.flexion_type);
    } else {
        e.target.reset();
        loadVocab();
    }
}

/**
 * Show translation selection buttons after AI lookup
 */
function showTranslationButtons(latin, translations, word_type, flexion_type) {
    document.getElementById("addVocabForm").style.display = "none";
    document.getElementById("translationOptions").style.display = "block";

    const buttonsDiv = document.getElementById("transButtons");
    buttonsDiv.innerHTML = translations.map((trans, i) => `
        <button class="trans-btn" onclick="selectTranslation('${latin}', '${trans}', '${word_type}', '${flexion_type}')">
            ${i + 1}. ${trans}
        </button>
    `).join("<br>");
}

/**
 * Save selected translation as vocabulary entry
 */
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

/* ==================== MULTIPLE CHOICE QUIZ ==================== */

/**
 * Start multiple choice quiz session
 */
async function startQuizFlow() {
    const startRes = await fetch(`${API_BASE}/quiz/start`, {method: "POST"});
    const startData = await startRes.json();
    quizRoundId = startData.quiz_round_id;
    mcTargetLength = startData.target_length;
    mcVerbCount = 0;
    document.getElementById("mcCounter").textContent = `0/${mcTargetLength}`;
    showSection("quiz");
    await loadNextMCQuestion();
}

/**
 * Load and display next multiple choice question
 */
async function loadNextMCQuestion() {
    if (mcVerbCount >= mcTargetLength) {
        document.getElementById("quizFeedback").textContent = "Multiple choice quiz complete!";
        alert("Multiple choice quiz complete!");
        await finishQuiz(quizRoundId);
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
    document.getElementById("quizFeedback").textContent = `Choose right answer! (${mcVerbCount + 1}/${mcTargetLength})`;
    mcVerbCount++;
    document.getElementById("mcCounter").textContent = `${mcVerbCount}/${mcTargetLength}`;
    document.getElementById("btnNextQuestion").style.display = "none";
}

/**
 * Display question with multiple choice options
 */
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

/**
 * Submit multiple choice answer
 */
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

/**
 * Proceed to next multiple choice question
 */
function nextMCQuestion() {
    document.getElementById("btnNextQuestion").style.display = "none";
    loadNextMCQuestion();
}

/* ==================== CARDS VIEW ==================== */

/**
 * Load and display bronze cards gallery
 */
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

/* ==================== VERB SORTING QUIZ ==================== */

/**
 * Start verb categorization sorting quiz
 */
async function startSortingQuiz() {
    const res = await fetch(`${API_BASE}/quiz/verbs/start`, {method: "POST"});
    const startData = await res.json();
    sortingRoundId = startData.quiz_round_id;
    sortingTargetLength = startData.target_length;
    sortingVerbCount = 0;
    document.getElementById("sortingCounter").textContent = `0/${sortingTargetLength}`;
    showSection("sorting");
    setupDragDropHandlers();
    await loadNextSortingVerb();
}

/**
 * Load next verb for sorting quiz
 */
async function loadNextSortingVerb() {
    if (sortingVerbCount >= sortingTargetLength) {
        document.getElementById("sortingFeedback").textContent = "Sorting quiz complete!";
        document.getElementById("sortingCounter").textContent = "";
        alert(`Sorting complete! (${sortingVerbCount}/${sortingTargetLength})`);
        await finishQuiz(sortingRoundId);
        loadVocab();
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
    document.getElementById("sortingFeedback").textContent = `Drag to category! (${sortingVerbCount}/${sortingTargetLength})`;
    resetVerbCategories();
    document.getElementById("btnNextVerb").style.display = "none";
}

/**
 * Reset verb category boxes to initial state
 */
function resetVerbCategories() {
    document.querySelectorAll("#sortingQuizArea .category-box").forEach(box => {
        box.classList.remove("correct", "wrong");
        box.innerHTML = box.dataset.category;
    });
}

/**
 * Handle verb drop into category box
 */
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
    document.getElementById("sortingFeedback").innerHTML = `<strong>${result.message}</strong> ${result.score.toFixed(1)}%`;
    document.getElementById("btnNextVerb").style.display = "inline-block";
}

/**
 * Proceed to next verb sorting question
 */
function nextSortingVerb() {
    document.getElementById("btnNextVerb").style.display = "none";
    loadNextSortingVerb();
}

/* ==================== NOUN SORTING QUIZ ==================== */

/**
 * Start noun declension sorting quiz
 */
async function startNounsQuiz() {
    const res = await fetch(`${API_BASE}/quiz/nouns/start`, {method: "POST"});
    const startData = await res.json();
    nounsRoundId = startData.quiz_round_id;
    nounsTargetLength = startData.target_length;
    nounsCount = 0;
    document.getElementById("nounsCounter").textContent = `0/${nounsTargetLength}`;
    showSection("nouns");
    setupDragDropHandlers();
    await loadNextNounsNoun();
}

/**
 * Load next noun for declension sorting
 */
async function loadNextNounsNoun() {
    if (nounsCount >= nounsTargetLength) {
        document.getElementById("nounsFeedback").textContent = "Noun quiz complete!";
        document.getElementById("nounsCounter").textContent = "";
        alert(`Noun quiz complete! (${nounsCount}/${nounsTargetLength})`);
        await finishQuiz(nounsRoundId);
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
    nounsCount++;
    document.getElementById("nounsCounter").textContent = `${nounsCount}/${nounsTargetLength}`;
    document.getElementById("nounsFeedback").textContent = `Drag to declension! (${nounsCount}/${nounsTargetLength})`;
    resetNounCategories();
    document.getElementById("btnNextNoun").style.display = "none";
}

/**
 * Reset noun category boxes to initial state
 */
function resetNounCategories() {
    document.querySelectorAll("#nounsQuizArea .category-box").forEach(box => {
        box.classList.remove("correct", "wrong");
        box.innerHTML = box.dataset.category;
    });
}

/**
 * Handle noun drop into declension category
 */
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
    document.getElementById("nounsFeedback").innerHTML = `Accuracy: ${result.score.toFixed(1)}%`;
    document.getElementById("btnNextNoun").style.display = "inline-block";
}

/**
 * Proceed to next noun sorting question
 */
function nextNounsNoun() {
    document.getElementById("btnNextNoun").style.display = "none";
    resetNounCategories();
    loadNextNounsNoun();
}

/**
 * Finish any quiz round and save results
 */
async function finishQuiz(roundId) {
    await fetch(`${API_BASE}/quiz/finish`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({quiz_round_id: roundId})
    });
}
