import os
import json
import re
import random
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user
from datetime import datetime
from sqlalchemy import func, select

import frag_caesar_bs4
from extensions import db
from models import VocabEntry, QuizRound, QuizAnswer, Card, UserCard
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")


class WrongOptions(BaseModel):
    """Pydantic model for validating AI-generated wrong options."""
    options: list[str]


def normalize_german_strict(s: str) -> str:
    """
    Normalize German text for strict comparison during distractor filtering.

    Strips whitespace, lowercases, normalizes multiple spaces to single space,
    and removes trailing punctuation.
    """
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[;.,!?:]+$", "", s)
    return s


def build_true_meanings_set_from_frag_caesar_and_db(correct: str, latin_word: str) -> set[str]:
    """
    Build set of true German meanings from database and FragCaesar API.

    Combines provided correct translation with additional meanings from
    FragCaesar to filter out real meanings from AI-generated distractors.
    """
    true_meanings = set()
    if correct:
        true_meanings.add(normalize_german_strict(correct))

    try:
        extra_meanings = frag_caesar_bs4.get_german_meanings(latin_word) or []
    except Exception as ex:
        current_app.logger.error("FragCaesar error for %s: %s", latin_word, ex)
        extra_meanings = []

    for meaning in extra_meanings:
        normalized = normalize_german_strict(meaning)
        if normalized:
            true_meanings.add(normalized)

    return true_meanings


def get_current_user_id() -> int:
    """Get current user ID, defaults to demo user ID=1 if not logged in."""
    return getattr(current_user, 'id', 1)


quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.post("/start")
def start_quiz():
    """
    Start multiple-choice vocabulary quiz.

    Creates QuizRound with random length (3-7 questions) and returns
    quiz_round_id and target_length for client-side progress tracking.
    """
    user_id = get_current_user_id()
    quiz_length = random.randint(3, 7)

    quiz_round = QuizRound(
        user_id=user_id,
        random_length=quiz_length,
        asked_count=0
    )
    db.session.add(quiz_round)
    db.session.commit()

    logger.info(f"MC Quiz started: ID={quiz_round.id}, target={quiz_length}")
    return jsonify({
        'quiz_round_id': quiz_round.id,
        'target_length': quiz_length
    })


@quiz_bp.get("/next")
def next_question():
    """
    Serve next multiple-choice question from weak vocabulary entries.

    Prioritizes entries with accuracy <95% or <100 total answers.
    Generates AI distractors filtered against real meanings.
    Increments asked_count when question is served.
    """
    client = current_app.config['client']
    user_id = get_current_user_id()
    quiz_round_id = request.args.get('quiz_round_id') or request.args.get('quizroundid')

    quiz_round = QuizRound.query.get(quiz_round_id)
    if not quiz_round:
        return jsonify({"error": "Invalid quiz_round_id"}), 404

    if quiz_round.finished_at or quiz_round.asked_count >= quiz_round.random_length:
        if not quiz_round.finished_at:
            quiz_round.finished_at = datetime.utcnow()
            db.session.commit()
        return jsonify({
            "error": f"Quiz complete! ({quiz_round.asked_count}/{quiz_round.random_length})"
        }), 404

    # Exclude already asked vocabulary entries
    asked_subquery = select(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == quiz_round_id
    ).subquery()

    # Query weak vocabulary (low accuracy or few answers)
    weak_entries = VocabEntry.query.filter(
        VocabEntry.user_id == user_id,
        (VocabEntry.accuracy_percent < 95) | (VocabEntry.total_answers < 100),
        VocabEntry.id.notin_(asked_subquery)
    ).order_by(func.random())

    vocab_entry = weak_entries.first()
    if not vocab_entry:
        quiz_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "error": f"No vocabulary left ({quiz_round.asked_count}/{quiz_round.random_length})"
        }), 404

    # Generate AI distractors
    latin_word = vocab_entry.latin_word
    correct_translation = vocab_entry.german_translation
    true_meanings = build_true_meanings_set_from_frag_caesar_and_db(
        correct_translation, latin_word
    )

    # AI prompt for wrong options
    system_prompt = {
        "role": "system",
        "content": (
            "You are a helpful assistant for Latin-German vocabulary training. "
            "Always answer ONLY with a JSON array of strings, e.g. "
            "[\"Wort1\",\"Wort2\",\"Wort3\"]. No explanations."
        )
    }

    user_prompt = (
        f"Latin: {latin_word}\nTrue German: {correct_translation}\n"
        f"Other meanings: {sorted(true_meanings)}\n"
        "Return EXACTLY 3 wrong plausible translations (JSON array only)."
    )

    messages = [system_prompt, {"role": "user", "content": user_prompt}]

    # Generate and validate distractors (max 3 attempts)
    wrong_options = []
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=120
            )
            content = response.choices[0].message.content.strip()
            wrong_options = json.loads(content)
            logger.info(f"AI generated distractors for {latin_word} (attempt {attempt + 1}): {content[:50]}")
        except Exception:
            wrong_options = ["Fehler 1", "Fehler 2", "Fehler 3"]
            break

        # Filter out real meanings
        filtered_options = [
            w.strip() for w in wrong_options
            if isinstance(w, str) and normalize_german_strict(w) not in true_meanings
        ]

        if len(filtered_options) >= 3:
            wrong_options = filtered_options
            break

    # Ensure exactly 3 valid distractors
    valid_distractors = [
                            w for w in wrong_options[:3]
                            if normalize_german_strict(w) not in true_meanings
                        ][:3]

    while len(valid_distractors) < 3:
        valid_distractors.append("Platzhalter falsch")

    # Shuffle options
    all_options = valid_distractors + [correct_translation]
    random.shuffle(all_options)
    correct_index = all_options.index(correct_translation)

    question = {
        "id": vocab_entry.id,
        "latin_word": latin_word,
        "options": all_options,
        "correct_index": correct_index
    }

    # Increment asked count
    quiz_round.asked_count += 1
    db.session.commit()

    logger.info(f"MC Question served: {latin_word} ({quiz_round.asked_count}/{quiz_round.random_length})")
    return jsonify({"question": question})


@quiz_bp.post("/answer")
def submit_answer():
    """
    Process multiple-choice answer submission.

    Updates vocabulary statistics and handles bronze card logic
    based on accuracy thresholds.
    """
    user_id = get_current_user_id()
    data = request.get_json()
    quiz_round_id = data.get("quiz_round_id")

    if not quiz_round_id:
        return jsonify({"error": "Missing quiz_round_id"}), 400

    vocab_entry = VocabEntry.query.filter_by(
        id=data["vocab_entry_id"],
        user_id=user_id
    ).first_or_404()

    is_correct = normalize_german_strict(
        data["selected_option"]
    ) == normalize_german_strict(vocab_entry.german_translation)

    # Record answer
    quiz_answer = QuizAnswer(
        quiz_round_id=quiz_round_id,
        vocab_entry_id=vocab_entry.id,
        was_correct=is_correct
    )
    db.session.add(quiz_answer)

    # Update statistics
    vocab_entry.total_answers += 1
    if is_correct:
        vocab_entry.correct_answers += 1
    vocab_entry.accuracy_percent = (
            (vocab_entry.correct_answers / vocab_entry.total_answers) * 100
    )

    # Bronze card logic
    card_change = None
    card_id = None

    bronze_card = db.session.query(Card, UserCard).join(UserCard).filter(
        Card.vocab_entry_id == vocab_entry.id,
        Card.rarity == "bronze",
        UserCard.user_id == user_id
    ).first()

    if (is_correct and vocab_entry.accuracy_percent >= 90 and
            vocab_entry.total_answers >= 1 and not bronze_card):

        # Create bronze card
        card = Card(
            vocab_entry_id=vocab_entry.id,
            rarity="bronze",
            title=vocab_entry.latin_word,
            description=f"Bronze card for {vocab_entry.latin_word}",
            image_url="https://placehold.co/240x320?text=Bronze"
        )
        db.session.add(card)
        db.session.flush()

        user_card = UserCard(user_id=user_id, card_id=card.id)
        db.session.add(user_card)
        vocab_entry.has_bronze_card = True
        card_change = "created"
        card_id = card.id

    elif vocab_entry.accuracy_percent < 90 and bronze_card:
        # Remove bronze card
        card, user_card = bronze_card
        db.session.delete(user_card)

        if not UserCard.query.filter(
                UserCard.card_id == card.id,
                UserCard.user_id != user_id
        ).count():
            db.session.delete(card)

        vocab_entry.has_bronze_card = False
        card_change = "removed"
        card_id = card.id

    db.session.commit()

    return jsonify({
        "correct": is_correct,
        "accuracy_percent": round(vocab_entry.accuracy_percent, 1),
        "card_change": card_change,
        "card_id": card_id
    })


def get_active_quiz_round(user_id: int) -> QuizRound:
    """Retrieve most recent active quiz round for user."""
    return QuizRound.query.filter(
        QuizRound.user_id == user_id,
        QuizRound.finished_at.is_(None)
    ).order_by(QuizRound.id.desc()).first()


@quiz_bp.route('/verbs/start', methods=['POST'])
def verbs_start_quiz():
    """Start verb conjugation type sorting quiz."""
    user_id = get_current_user_id()
    quiz_length = random.randint(3, 7)

    quiz_round = QuizRound(
        user_id=user_id,
        random_length=quiz_length,
        asked_count=0
    )
    db.session.add(quiz_round)
    db.session.commit()

    return jsonify({
        'quiz_round_id': quiz_round.id,
        'target_length': quiz_length
    })


@quiz_bp.route('/verbs/next')
def verbs_next_question():
    """
    Serve next verb for conjugation type identification.

    Filters for verbs with defined flexion_type, excludes previously asked.
    """
    user_id = get_current_user_id()
    quiz_round = get_active_quiz_round(user_id)

    if not quiz_round:
        return jsonify({"error": "No active verb quiz"}), 404

    if quiz_round.asked_count >= quiz_round.random_length:
        quiz_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "error": f"Verb quiz complete! ({quiz_round.asked_count}/{quiz_round.random_length})"
        }), 404

    asked_subquery = db.session.query(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == quiz_round.id
    ).subquery()

    verb_entry = VocabEntry.query.filter(
        VocabEntry.user_id == user_id,
        VocabEntry.word_type == "Verb",
        VocabEntry.flexion_type.isnot(None),
        ~VocabEntry.id.in_(asked_subquery)
    ).order_by(func.random()).first()

    if not verb_entry:
        quiz_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "error": f"All verbs asked ({quiz_round.asked_count}/{quiz_round.random_length})"
        }), 404

    quiz_round.asked_count += 1
    db.session.commit()

    return jsonify({
        'verb': verb_entry.latin_word,
        'correct_category': verb_entry.flexion_type
    })


@quiz_bp.route('/verbs/answer', methods=['POST'])
def verbs_submit_answer():
    """Process verb conjugation type answer and update statistics."""
    user_id = get_current_user_id()
    data = request.get_json()

    vocab_entry = VocabEntry.query.filter_by(
        user_id=user_id,
        latin_word=data['verb']
    ).first_or_404()

    quiz_round = get_active_quiz_round(user_id)
    if not quiz_round:
        return jsonify({"error": "No active quiz"}), 404

    is_correct = data['category'] == vocab_entry.flexion_type

    quiz_answer = QuizAnswer(
        quiz_round_id=quiz_round.id,
        vocab_entry_id=vocab_entry.id,
        was_correct=is_correct
    )
    db.session.add(quiz_answer)

    vocab_entry.total_answers += 1
    if is_correct:
        vocab_entry.correct_answers += 1
    vocab_entry.accuracy_percent = (
            (vocab_entry.correct_answers / vocab_entry.total_answers) * 100
    )

    db.session.commit()

    return jsonify({
        "correct": is_correct,
        "score": round(vocab_entry.accuracy_percent, 1),
        "message": "Richtig!" if is_correct else "Falsch!"
    })


@quiz_bp.route('/nouns/start', methods=['POST'])
def nouns_start_quiz():
    """Start noun declension type sorting quiz."""
    user_id = get_current_user_id()
    quiz_length = random.randint(3, 7)

    quiz_round = QuizRound(
        user_id=user_id,
        random_length=quiz_length,
        asked_count=0
    )
    db.session.add(quiz_round)
    db.session.commit()

    return jsonify({
        'quiz_round_id': quiz_round.id,
        'target_length': quiz_length
    })


@quiz_bp.route('/nouns/next')
def nouns_next_question():
    """
    Serve next noun for declension type identification.

    Filters for nouns with defined flexion_type, excludes previously asked.
    """
    user_id = get_current_user_id()
    quiz_round = get_active_quiz_round(user_id)

    if not quiz_round:
        return jsonify({"error": "No active noun quiz"}), 404

    if quiz_round.asked_count >= quiz_round.random_length:
        quiz_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "error": f"Noun quiz complete! ({quiz_round.asked_count}/{quiz_round.random_length})"
        }), 404

    asked_subquery = db.session.query(QuizAnswer.vocab_entry_id).filter(
        QuizAnswer.quiz_round_id == quiz_round.id
    ).subquery()

    noun_entry = VocabEntry.query.filter(
        VocabEntry.user_id == user_id,
        VocabEntry.word_type == "Nomen",
        VocabEntry.flexion_type.isnot(None),
        ~VocabEntry.id.in_(asked_subquery)
    ).order_by(func.random()).first()

    if not noun_entry:
        quiz_round.finished_at = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "error": f"All nouns asked ({quiz_round.asked_count}/{quiz_round.random_length})"
        }), 404

    quiz_round.asked_count += 1
    db.session.commit()

    return jsonify({
        'noun': noun_entry.latin_word,
        'correct_category': noun_entry.flexion_type
    })


@quiz_bp.route('/nouns/answer', methods=['POST'])
def nouns_submit_answer():
    """Process noun declension type answer and update statistics."""
    user_id = get_current_user_id()
    data = request.get_json()

    vocab_entry = VocabEntry.query.filter_by(
        user_id=user_id,
        latin_word=data['noun']
    ).first_or_404()

    quiz_round = get_active_quiz_round(user_id)
    if not quiz_round:
        return jsonify({"error": "No active quiz"}), 404

    is_correct = data['category'] == vocab_entry.flexion_type

    quiz_answer = QuizAnswer(
        quiz_round_id=quiz_round.id,
        vocab_entry_id=vocab_entry.id,
        was_correct=is_correct
    )
    db.session.add(quiz_answer)

    vocab_entry.total_answers += 1
    if is_correct:
        vocab_entry.correct_answers += 1
    vocab_entry.accuracy_percent = (
            (vocab_entry.correct_answers / vocab_entry.total_answers) * 100
    )

    db.session.commit()

    return jsonify({
        "correct": is_correct,
        "score": round(vocab_entry.accuracy_percent, 1),
        "message": "Richtig!" if is_correct else "Falsch!"
    })


@quiz_bp.post("/finish")
def finish_quiz():
    """Manually complete active quiz round."""
    data = request.get_json()
    quiz_round_id = data.get("quiz_round_id")

    quiz_round = QuizRound.query.get_or_404(quiz_round_id)
    quiz_round.finished_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"status": "ok"})
