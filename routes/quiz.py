import os
import json
import re
import random
import logging
from flask import Blueprint, request, jsonify, current_app
import time
from datetime import datetime
from sqlalchemy import func, select

import frag_caesar_crawl4ai
from extensions import db
from models import VocabEntry, QuizRound, QuizAnswer, Card, UserCard
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

class WrongOptions(BaseModel):
    """Pydantic model for AI-generated wrong options validation."""
    options: list[str]

def normalize_german_strict(s: str) -> str:
    """
    Normalize German text for strict comparison (distractor filtering).
    Strips, lowercases, normalizes whitespace, removes trailing punctuation.
    """
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[;.,!?:]+$", "", s)
    return s

def build_true_meanings_set_from_frag_caesar_and_db(correct: str, latin_word: str) -> set[str]:
    """
    Combine DB translation + FragCaesar meanings into normalized set.
    Used to filter AI distractors that accidentally match real meanings.
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
    """Hardcoded user ID for demo (replace with auth)."""
    return 1

@quiz_bp.post("/start")
def start_quiz():
    """
    Start MC quiz round.
    Generates random_length (3-7), creates QuizRound, returns ID + target for JS counter.
    """
    user_id = get_current_user_id()
    random_length = random.randint(3, 7)  # 🎯 Variable 3-7 questions
    qr = QuizRound(user_id=user_id, random_length=random_length, asked_count=0)
    db.session.add(qr)
    db.session.commit()
    logger.info(f"MC Quiz started: ID={qr.id}, target={random_length}")
    return jsonify({'quiz_round_id': qr.id, 'target_length': random_length})

@quiz_bp.get("/next")
def next_questions():
    """
    Get next MC question (weak vocab, AI distractors).
    🚨 Checks asked_count >= random_length → finish early.
    Increments asked_count on serve (question-first model).
    Adaptive: fewer vocabs → all asked → finish.
    """
    client = current_app.config['client']
    user_id = get_current_user_id()
    quiz_round_id = request.args.get('quiz_round_id') or request.args.get('quizroundid')

    qr = QuizRound.query.get(quiz_round_id)
    if not qr:
        return jsonify({"error": "Invalid quiz_round_id"}), 404
    if qr.finished_at:
        return jsonify({"error": f"Quiz finished ({qr.asked_count}/{qr.random_length})"}), 404
    if qr.asked_count >= qr.random_length:
        qr.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": f"Quiz complete! ({qr.asked_count}/{qr.random_length})"}), 404

    # ✅ FIXED: Always create subquery, filter if exists
    asked_subq = db.session.query(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == quiz_round_id
    ).subquery()

    asked_select = select(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == quiz_round_id
    )

    weak = VocabEntry.query.filter(
        VocabEntry.user_id == user_id,
        (VocabEntry.accuracy_percent < 95) | (VocabEntry.total_answers < 100)
    ).filter(VocabEntry.id.notin_(asked_select.subquery()))

    entry = weak.order_by(func.random()).first()
    if not entry:
        qr.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": f"No vocabs left ({qr.asked_count}/{qr.random_length})"}), 404

    # AI distractors (unchanged complex logic)
    latin_word = entry.latin_word
    correct = entry.german_translation
    true_meanings_set = build_true_meanings_set_from_frag_caesar_and_db(correct, latin_word)

    system_msg = {
        "role": "system",
        "content": (
            "You are a helpful assistant for Latin–German vocabulary training. "
            "Always answer ONLY with a JSON array of strings, e.g. "
            "[\"Wort1\",\"Wort2\",\"Wort3\"]. No explanations."
        ),
    }
    base_user_prompt = (
        f"Latin: {latin_word}\nTrue German: {correct}\n"
        f"Other meanings: {sorted(true_meanings_set)}\n"
        "Return EXACTLY 3 wrong plausible translations (JSON array only)."
    )
    messages = [system_msg, {"role": "user", "content": base_user_prompt}]

    wrong_options_raw: list[str] = []
    attempts = 0
    while attempts < 3:  # Max 3 AI retries
        attempts += 1
        try:
            resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages, max_tokens=120)
            content = resp.choices[0].message.content.strip()
            wrong_options_raw = json.loads(content)
            logger.info(f"AI gen for {latin_word} (attempt {attempts}): {content[:50]}")
        except Exception:
            wrong_options_raw = ["Falsche 1", "Falsche 2", "Falsche 3"]
            break

        # Filter real meanings → retry/add feedback if needed
        filtered = [w.strip() for w in wrong_options_raw if isinstance(w, str)
                    and normalize_german_strict(w) not in true_meanings_set]
        if len(filtered) >= 3:
            wrong_options_raw = filtered
            break

    # Pad/filter to exactly 3 safe distractors
    wrong_options = [w for w in wrong_options_raw[:3]
                     if normalize_german_strict(w) not in true_meanings_set][:3]
    while len(wrong_options) < 3:
        wrong_options.append("Dummy wrong")

    options = wrong_options + [correct]
    random.shuffle(options)
    correct_index = options.index(correct)

    question = {
        "id": entry.id,
        "latin_word": latin_word,
        "options": options,
        "correct_index": correct_index
    }

    # 📊 Increment counter (question served = asked)
    qr.asked_count += 1
    db.session.commit()
    logger.info(f"MC Q served: {latin_word} ({qr.asked_count}/{qr.random_length})")

    return jsonify({"question": question})


@quiz_bp.post("/answer")
def answer_question():
    """
    Submit MC answer, update stats/cards.
    No asked_count change (incremented on /next serve).
    """
    user_id = get_current_user_id()
    data = request.get_json()
    quiz_round_id = data.get("quiz_round_id")
    if not quiz_round_id:
        return jsonify({"error": "Missing quiz_round_id"}), 400

    entry = VocabEntry.query.filter_by(id=data["vocab_entry_id"], user_id=user_id).first_or_404()
    is_correct = normalize_german_strict(data["selected_option"]) == normalize_german_strict(entry.german_translation)

    qa = QuizAnswer(quiz_round_id=quiz_round_id, vocab_entry_id=entry.id, was_correct=is_correct)
    db.session.add(qa)

    entry.total_answers += 1
    if is_correct:
        entry.correct_answers += 1
    entry.accuracy_percent = (entry.correct_answers / entry.total_answers) * 100

    # Bronze card logic (unchanged)
    card_change = None
    card_id = None
    bronze = db.session.query(Card, UserCard).join(UserCard).filter(
        Card.vocab_entry_id == entry.id, Card.rarity == "bronze", UserCard.user_id == user_id
    ).first()

    if is_correct and entry.accuracy_percent >= 90 and entry.total_answers >= 1 and not bronze:
        # Create card
        card = Card(vocab_entry_id=entry.id, rarity="bronze", title=entry.latin_word,
                    description=f"Bronze for {entry.latin_word}", image_url="https://placehold.co/240x320?text=Bronze")
        db.session.add(card)
        db.session.flush()
        db.session.add(UserCard(user_id=user_id, card_id=card.id))
        entry.has_bronze_card = True
        card_change = "created"
        card_id = card.id
    elif entry.accuracy_percent < 90 and bronze:
        # Remove card
        card, user_card = bronze
        db.session.delete(user_card)
        if not UserCard.query.filter(UserCard.card_id == card.id, UserCard.user_id != user_id).count():
            db.session.delete(card)
        entry.has_bronze_card = False
        card_change = "removed"
        card_id = card.id

    db.session.commit()
    return jsonify({"correct": is_correct, "accuracy_percent": entry.accuracy_percent,
                    "card_change": card_change, "card_id": card_id})

@quiz_bp.route('/verbs/start', methods=['POST'])
def verbs_start():
    """Start verb sorting quiz (random 3-7)."""
    user_id = get_current_user_id()
    random_length = random.randint(3, 7)
    qr = QuizRound(user_id=user_id, random_length=random_length, asked_count=0)
    db.session.add(qr)
    db.session.commit()
    return jsonify({'quiz_round_id': qr.id, 'target_length': random_length})

@quiz_bp.route('/verbs/next')
def verbs_next():
    """
    Next verb for sorting.
    Checks length/no verbs → finish. Increments asked_count.
    """
    user_id = get_current_user_id()
    current_round = QuizRound.query.filter(
        QuizRound.user_id == user_id, QuizRound.finished_at.is_(None)
    ).order_by(QuizRound.id.desc()).first()
    if not current_round:
        return jsonify({"error": "No active verb quiz"}), 404

    if current_round.asked_count >= current_round.random_length:
        current_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": f"Verb quiz complete! ({current_round.asked_count}/{current_round.random_length})"}), 404

    asked_ids = db.session.query(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == current_round.id).subquery()

    verb = VocabEntry.query.filter(
        VocabEntry.user_id == user_id, VocabEntry.word_type == "Verb",
        VocabEntry.flexion_type.isnot(None), ~VocabEntry.id.in_(asked_ids)
    ).order_by(func.random()).first()

    if not verb:
        current_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": f"All verbs asked ({current_round.asked_count}/{current_round.random_length})"}), 404

    current_round.asked_count += 1
    db.session.commit()
    return jsonify({'verb': verb.latin_word, 'correct_category': verb.flexion_type})

@quiz_bp.route('/verbs/answer', methods=['POST'])
def verbs_answer():
    """Submit verb category answer, update stats (no count increment)."""
    user_id = get_current_user_id()
    data = request.get_json()
    entry = VocabEntry.query.filter_by(user_id=user_id, latin_word=data['verb']).first_or_404()
    current_round = QuizRound.query.filter(QuizRound.user_id == user_id, QuizRound.finished_at.is_(None)).order_by(QuizRound.id.desc()).first_or_404()

    is_correct = data['category'] == entry.flexion_type
    qa = QuizAnswer(quiz_round_id=current_round.id, vocab_entry_id=entry.id, was_correct=is_correct)
    db.session.add(qa)
    entry.total_answers += 1
    if is_correct: entry.correct_answers += 1
    entry.accuracy_percent = (entry.correct_answers / entry.total_answers) * 100
    db.session.commit()

    return jsonify({"correct": is_correct, "score": entry.accuracy_percent,
                    "message": "Richtig!" if is_correct else "Falsch!"})

@quiz_bp.route('/nouns/start', methods=['POST'])
def nouns_start():
    """Start noun sorting quiz (random 3-7)."""
    user_id = get_current_user_id()
    random_length = random.randint(3, 7)
    qr = QuizRound(user_id=user_id, random_length=random_length, asked_count=0)
    db.session.add(qr)
    db.session.commit()
    return jsonify({'quiz_round_id': qr.id, 'target_length': random_length})

@quiz_bp.route('/nouns/next')
def nouns_next():
    """
    Next noun for declension sorting.
    Same length/adaptive logic as verbs.
    """
    user_id = get_current_user_id()
    current_round = QuizRound.query.filter(
        QuizRound.user_id == user_id, QuizRound.finished_at.is_(None)
    ).order_by(QuizRound.id.desc()).first()
    if not current_round:
        return jsonify({"error": "No active noun quiz"}), 404

    if current_round.asked_count >= current_round.random_length:
        current_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": f"Noun quiz complete! ({current_round.asked_count}/{current_round.random_length})"}), 404

    asked_ids = db.session.query(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == current_round.id).subquery()

    noun = VocabEntry.query.filter(
        VocabEntry.user_id == user_id, VocabEntry.word_type == "Nomen",
        VocabEntry.flexion_type.isnot(None), ~VocabEntry.id.in_(asked_ids)
    ).order_by(func.random()).first()

    if not noun:
        current_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": f"All nouns asked ({current_round.asked_count}/{current_round.random_length})"}), 404

    current_round.asked_count += 1
    db.session.commit()
    return jsonify({'noun': noun.latin_word, 'correct_category': noun.flexion_type})

@quiz_bp.route('/nouns/answer', methods=['POST'])
def nouns_answer():
    """Submit noun category answer (mirror verbs)."""
    user_id = get_current_user_id()
    data = request.get_json()
    entry = VocabEntry.query.filter_by(user_id=user_id, latin_word=data['noun']).first_or_404()
    current_round = QuizRound.query.filter(QuizRound.user_id == user_id, QuizRound.finished_at.is_(None)).order_by(QuizRound.id.desc()).first_or_404()

    is_correct = data['category'] == entry.flexion_type
    qa = QuizAnswer(quiz_round_id=current_round.id, vocab_entry_id=entry.id, was_correct=is_correct)
    db.session.add(qa)
    entry.total_answers += 1
    if is_correct: entry.correct_answers += 1
    entry.accuracy_percent = (entry.correct_answers / entry.total_answers) * 100
    db.session.commit()

    return jsonify({"correct": is_correct, "score": entry.accuracy_percent,
                    "message": "Richtig!" if is_correct else "Falsch!"})

@quiz_bp.post("/finish")
def finish_quiz():
    """Manually finish round (JS fallback)."""
    data = request.get_json()
    quiz_round_id = data.get("quiz_round_id")
    qr = QuizRound.query.get_or_404(quiz_round_id)
    qr.finished_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "ok"})
