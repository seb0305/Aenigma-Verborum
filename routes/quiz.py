import os
import json
import re
import random
import logging
from flask import Blueprint, request, jsonify, current_app
import time
from sqlalchemy import func

import frag_caesar_crawl4ai
from extensions import db
from models import VocabEntry, QuizRound, QuizAnswer, Card, UserCard
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

class WrongOptions(BaseModel):
    options: list[str]

def normalize_german_strict(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[;.,!?:]+$", "", s)
    return s

def build_true_meanings_set_from_frag_caesar_and_db(correct: str, latin_word: str) -> set[str]:
    """
    Combine the main DB translation with all meanings scraped from FragCaesar.
    All normalized with normalize_german_strict.
    """
    s: set[str] = set()
    if correct:
        s.add(normalize_german_strict(correct))

    try:
        extra_meanings = frag_caesar_crawl4ai.get_german_meanings(latin_word) or []
    except Exception as ex:
        current_app.logger.error("FragCaesar error for %s: %s", latin_word, ex)
        extra_meanings = []

    for m in extra_meanings:
        norm = normalize_german_strict(m)
        if norm:
            s.add(norm)

    return s

quiz_bp = Blueprint("quiz", __name__)

def get_current_user_id():
    return 1

@quiz_bp.post("/start")
def start_quiz():
    user_id = get_current_user_id()
    qr = QuizRound(user_id=user_id)
    db.session.add(qr)
    db.session.commit()
    return jsonify({"quiz_round_id": qr.id})

@quiz_bp.get("/next")
def next_questions():
    client = current_app.config['client']
    user_id = get_current_user_id()
    quiz_round_id = request.args.get('quizroundid')

    # Get asked this round (optional uniqueness)
    if quiz_round_id:
        asked_ids = db.session.query(QuizAnswer.vocab_entry_id).filter(
            QuizAnswer.quiz_round_id == quiz_round_id
        ).subquery()

    # Single weak vocab (randomized, exclude asked)
    weak = VocabEntry.query.filter(
        VocabEntry.user_id == user_id,
        (VocabEntry.accuracy_percent < 95) | (VocabEntry.total_answers < 100)
    )
    if quiz_round_id:
        weak = weak.filter(~VocabEntry.id.in_(asked_ids))
    entry = weak.order_by(func.random()).first()

    if not entry:
        return jsonify({"error": "No weak vocabs available"}), 404

    # Generate distractors for THIS vocab only (1x Gemini ~2s)
    latin_word = entry.latin_word
    correct = entry.german_translation

    # Build full set of true meanings (DB + FragCaesar)
    true_meanings_set = build_true_meanings_set_from_frag_caesar_and_db(
        correct=correct,
        latin_word=latin_word,
    )

    # ---- OpenAI/Gemini call with fallback + short chat history ----
    system_msg = {
        "role": "system",
        "content": (
            "You are a helpful assistant for Latin–German vocabulary training. "
            "Always answer ONLY with a JSON array of strings, e.g. "
            "[\"Wort1\",\"Wort2\",\"Wort3\"]. No explanations."
        ),
    }

    base_user_prompt = (
        "You get a Latin–German vocabulary pair.\n"
        "Return EXACTLY three unique, wrong but plausible German translations for the Latin word.\n"
        "Important:\n"
        "- Do NOT repeat any of the other given true German meanings.\n"
        "- Answer ONLY with a JSON array of strings, no extra text.\n\n"
        f"Latin: {latin_word}\n"
        f"True German translation: {correct}\n"
        f"Other true German meanings: {sorted(true_meanings_set)}"
    )

    messages = [system_msg, {"role": "user", "content": base_user_prompt}]

    wrong_options_raw: list[str] = []
    max_wrong_responses = 3  # allow 3 "bad" attempts
    attempts = 0

    start_time = time.perf_counter()  # Speed

    while attempts < max_wrong_responses:
        attempts += 1
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                #model=GEMINI_MODEL,
                messages=messages,
                max_tokens=120,
            )

            # TIME + TOKENS!
            ai_duration = (time.perf_counter() - start_time) * 1000  # ms

            prompt_tokens = resp.usage.prompt_tokens
            completion_tokens = resp.usage.completion_tokens
            total_tokens = resp.usage.total_tokens

            content = resp.choices[0].message.content.strip()
            current_app.logger.info("AI content for %s (attempt %d): %s", latin_word, attempts, content)
            current_app.logger.info(
                f"'{latin_word}' → {ai_duration:.0f}ms | "
                f"T: {total_tokens} (P:{prompt_tokens}/C:{completion_tokens}) | "
                f"Response: {content[:50]}..."
            )
            wrong_options_raw = json.loads(content)
            if not isinstance(wrong_options_raw, list):
                raise ValueError("AI response is not a JSON list")

        except Exception as ex:
            current_app.logger.error("OpenAI error for %s (attempt %d): %s",
                                     latin_word, attempts, ex)
            wrong_options_raw = [
                "Falsche Übersetzung 1",
                "Falsche Übersetzung 2",
                "Falsche Übersetzung 3",
            ]
            break  # fall through to filtering once, no further retries

        # Filter out any distractor that matches a real meaning
        filtered = []
        violating = []  # those that matched a true meaning

        for w in wrong_options_raw:
            if not isinstance(w, str):
                continue
            norm = normalize_german_strict(w)
            if not norm:
                continue
            if norm in true_meanings_set:
                violating.append(w)
                continue
            filtered.append(w.strip())

        # If none of the options violated the true meanings, we accept this response
        if not violating:
            wrong_options_raw = filtered
            break

        # Otherwise, add a brief assistant + user message to the chat history and retry
        violation_text = ", ".join(f'"{v}"' for v in violating)
        messages.append({
            "role": "assistant",
            "content": json.dumps(wrong_options_raw, ensure_ascii=False),
        })
        messages.append({
            "role": "user",
            "content": (
                "Some of your previous suggestions were invalid because they match true German meanings "
                f"for this Latin word: {violation_text}.\n"
                "Please try again and return three different WRONG translations that do not match any true meaning."
            ),
        })

        # If filtered already has 3 or more safe distractors after removing violating ones, we can stop
        if len(filtered) >= 3:
            wrong_options_raw = filtered
            break

    # After loop, ensure we have a list of strings in wrong_options_raw (possibly filtered)
    if not wrong_options_raw:
        wrong_options_raw = [
            "Falsche Übersetzung 1",
            "Falsche Übersetzung 2",
            "Falsche Übersetzung 3",
        ]

    # Final filtering & padding to exactly 3
    final_filtered = []
    for w in wrong_options_raw:
        if not isinstance(w, str):
            continue
        norm = normalize_german_strict(w)
        if not norm or norm in true_meanings_set:
            continue
        final_filtered.append(w.strip())

    wrong_options = final_filtered[:3]
    while len(wrong_options) < 3:
        wrong_options.append(f"Other wrong translation {len(wrong_options) + 1}")

    options = wrong_options + [correct]
    random.shuffle(options)
    correct_index = options.index(correct)

    question = [{
        "id": entry.id,
        "latin_word": latin_word,
        "options": options,
        "correct_index": correct_index
    }]

    current_app.logger.info(f"Single MC question: {latin_word}")
    return jsonify(question)



@quiz_bp.route('/verbs/next')
def verbs_next():
    user_id = get_current_user_id()

    # Get current unfinished sorting round for user
    current_round = (QuizRound.query
                     .filter(QuizRound.user_id == user_id,
                             QuizRound.finished_at.is_(None))
                     .order_by(QuizRound.id.desc())
                     .first())

    if not current_round:
        return jsonify({"error": "No active sorting quiz round"}), 404

    # Asked verb IDs this round
    asked_ids = (db.session.query(QuizAnswer.vocab_entry_id)
                 .filter(QuizAnswer.quiz_round_id == current_round.id)
                 .subquery())

    verb = (VocabEntry.query
            .filter(VocabEntry.user_id == user_id,
                    VocabEntry.word_type == "Verb",
                    VocabEntry.flexion_type.isnot(None),
                    ~VocabEntry.id.in_(asked_ids))  # Exclude asked
            .order_by(func.random())
            .first())

    if not verb:
        current_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": "Quiz complete! All verbs asked once."}), 404

    return jsonify({
        'verb': verb.latin_word,
        'correct_category': verb.flexion_type
    })


@quiz_bp.post("/answer")
def answer_question():
    user_id = get_current_user_id()
    data = request.get_json()

    quiz_round_id = data.get("quiz_round_id")
    if not quiz_round_id:
        return jsonify({"error": "Missing quiz_round_id"}), 400
    vocab_entry_id = data.get("vocab_entry_id")
    selected_option = (data.get("selected_option") or "").strip().lower()

    # Reads the relevant VocabEntry row
    entry = VocabEntry.query.filter_by(id=vocab_entry_id, user_id=user_id).first_or_404()

    # correct translation from DB
    correct_translation = entry.german_translation.strip().lower()

    is_correct = (selected_option == correct_translation)

    # Creates a QuizAnswer row linking the quiz round and vocab entry
    qa = QuizAnswer(
        quiz_round_id=quiz_round_id,
        vocab_entry_id=vocab_entry_id,
        was_correct=is_correct,
    )
    db.session.add(qa)

    # Updates the stats
    entry.total_answers += 1
    if is_correct:
        entry.correct_answers += 1

    entry.accuracy_percent = (entry.correct_answers * 100.0) / entry.total_answers

    # 4) handle bronze card creation / removal
    card_change = None  # "created", "removed" or None
    card_id = None

    # find existing bronze card for this user + vocab (if any)
    bronze = (
        db.session.query(Card, UserCard)
        .join(UserCard, UserCard.card_id == Card.id)
        .filter(
            Card.vocab_entry_id == entry.id,
            Card.rarity == "bronze",
            UserCard.user_id == user_id,
        )
        .first()
    )

    # CREATE card if accuracy >= 90%, answer correct, enough attempts, and no card
    if (
        is_correct
        and entry.accuracy_percent >= 90.0
        and entry.total_answers >= 1
        and bronze is None
    ):
        # placeholder AI content for Milestone 1
        description = f"Bronze card for {entry.latin_word}"
        image_url = "https://placehold.co/240x320?text=Bronze+Card"


        card = Card(
            vocab_entry_id=entry.id,
            rarity="bronze",
            title=entry.latin_word,
            description=description,
            image_url=image_url,
        )
        db.session.add(card)
        db.session.flush()  # get card.id

        user_card = UserCard(
            user_id=user_id,
            card_id=card.id,
        )
        db.session.add(user_card)

        entry.has_bronze_card = True
        card_change = "created"
        card_id = card.id

    # REMOVE card if accuracy < 90% and card exists
    elif entry.accuracy_percent < 90.0 and bronze is not None:
        card, user_card = bronze
        db.session.delete(user_card)

        # optionally delete Card if no other user owns it
        others = UserCard.query.filter(
            UserCard.card_id == card.id,
            UserCard.user_id != user_id,
        ).count()
        if others == 0:
            db.session.delete(card)

        entry.has_bronze_card = False
        card_change = "removed"
        card_id = card.id

    db.session.commit()

    return jsonify({
        "correct": is_correct,
        "accuracy_percent": entry.accuracy_percent,
        "card_change": card_change,
        "card_id": card_id,
    })

@quiz_bp.route('/verbs/start', methods=['POST'])
def verbs_start():
    user_id = get_current_user_id()
    qr = QuizRound(user_id=user_id)
    db.session.add(qr)
    db.session.commit()
    return jsonify({"quizroundid": qr.id})


@quiz_bp.route('/verbs/answer', methods=['POST'])
def verbs_answer():
    user_id = get_current_user_id()
    data = request.get_json()
    verb = data['verb']
    category = data['category']

    # Find vocab entry by latin word
    entry = VocabEntry.query.filter_by(
        user_id=user_id,
        latin_word=verb
    ).first()

    if not entry:
        return jsonify({"error": "Verb not found"}), 404

    # Find active round
    current_round = QuizRound.query.filter(
        QuizRound.user_id == user_id,
        QuizRound.finished_at.is_(None)
    ).order_by(QuizRound.id.desc()).first()

    if not current_round:
        return jsonify({"error": "No active quiz round"}), 404

    # Check answer
    is_correct = (category == entry.flexion_type)

    # Create QuizAnswer record (CRITICAL for tracking)
    qa = QuizAnswer(
        quiz_round_id=current_round.id,
        vocab_entry_id=entry.id,
        was_correct=is_correct
    )
    db.session.add(qa)

    # Update vocab stats
    entry.total_answers += 1
    if is_correct:
        entry.correct_answers += 1
    entry.accuracy_percent = (entry.correct_answers / entry.total_answers) * 100

    db.session.commit()

    message = "Richtig!" if is_correct else "Falsch!"
    return jsonify({
        "correct": is_correct,
        "score": entry.accuracy_percent,
        "message": message
    })

    return jsonify({
        "correct": is_correct,
        "score": entry.accuracy_percent,
        "message": "Richtig!" if is_correct else "Falsch!"
    })

@quiz_bp.route('/nouns/start', methods=['POST'])
def nouns_start():  # Copy of verbs_start
    user_id = get_current_user_id()
    qr = QuizRound(user_id=user_id)
    db.session.add(qr)
    db.session.commit()
    return jsonify({"quizroundid": qr.id})

@quiz_bp.route('/nouns/next')
def nouns_next():  # Copy of verbs_next → word_type="Noun"
    user_id = get_current_user_id()
    current_round = QuizRound.query.filter(
        QuizRound.user_id == user_id, QuizRound.finished_at.is_(None)
    ).order_by(QuizRound.id.desc()).first()
    if not current_round:
        return jsonify({"error": "No active sorting quiz round"}), 404

    asked_ids = db.session.query(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == current_round.id
    ).subquery()

    noun = VocabEntry.query.filter(
        VocabEntry.user_id == user_id,
        VocabEntry.word_type == "Nomen",
        VocabEntry.flexion_type.isnot(None),
        ~VocabEntry.id.in_(asked_ids)
    ).order_by(func.random()).first()

    if not noun:
        current_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": "Quiz complete! All nouns covered."}), 404

    return jsonify({'noun': noun.latin_word, 'correct_category': noun.flexion_type})

@quiz_bp.route('/nouns/answer', methods=['POST'])
def nouns_answer():  # Copy of verbs_answer → 'noun'
    user_id = get_current_user_id()
    data = request.get_json()
    noun = data['noun']  # vs 'verb'
    category = data['category']

    # Find vocab entry by latin_word
    entry = VocabEntry.query.filter_by(
        user_id=user_id,
        latin_word=noun
    ).first()

    if not entry:
        return jsonify({"error": "Noun not found"}), 404

    # Find active round
    current_round = QuizRound.query.filter(
        QuizRound.user_id == user_id,
        QuizRound.finished_at.is_(None)
    ).order_by(QuizRound.id.desc()).first()

    if not current_round:
        return jsonify({"error": "No active quiz round"}), 404

    # Check answer
    is_correct = (category == entry.flexion_type)

    # Create QuizAnswer record
    qa = QuizAnswer(
        quiz_round_id=current_round.id,
        vocab_entry_id=entry.id,
        was_correct=is_correct
    )
    db.session.add(qa)

    # Update vocab stats
    entry.total_answers += 1
    if is_correct:
        entry.correct_answers += 1
    entry.accuracy_percent = (entry.correct_answers / entry.total_answers) * 100

    db.session.commit()

    message = "Richtig!" if is_correct else "Falsch!"
    return jsonify({
        "correct": is_correct,
        "score": entry.accuracy_percent,
        "message": message
    })



# lets the DB store complete round histories
@quiz_bp.post("/finish")
def finish_quiz():
    data = request.get_json()
    quiz_round_id = data.get("quiz_round_id")
    qr = QuizRound.query.get_or_404(quiz_round_id)
    qr.finished_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "ok"})