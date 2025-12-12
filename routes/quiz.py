from flask import Blueprint, request, jsonify
from datetime import datetime
from extensions import db
from models import VocabEntry, QuizRound, QuizAnswer, Card, UserCard

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
    user_id = get_current_user_id()

    # weak word condition: accuracy below 70% or fewer than 3 total answers
    # limit to 10 vocabs

    weak = VocabEntry.query.filter(
        VocabEntry.user_id == user_id,
        (VocabEntry.accuracy_percent < 70) | (VocabEntry.total_answers < 3)
    ).limit(10).all()

    return jsonify([
        {
            "id": e.id,
            "latin_word": e.latin_word,
            "german_translation": e.german_translation,  # frontend can hide this until checking
        }
        for e in weak
    ])

@quiz_bp.post("/answer")
def answer_question():
    user_id = get_current_user_id()
    data = request.get_json()
    quiz_round_id = data.get("quiz_round_id")
    vocab_entry_id = data.get("vocab_entry_id")
    user_answer = (data.get("user_answer") or "").strip().lower()
    # Reads the relevant VocabEntry row
    entry = VocabEntry.query.filter_by(id=vocab_entry_id, user_id=user_id).first_or_404()

    is_correct = user_answer == entry.german_translation.strip().lower()

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

    card_unlocked = False
    card_id = None

    # if criteria met, create bronze Card row and UserCard row
    if is_correct and not entry.has_bronze_card and entry.total_answers >= 3 and entry.accuracy_percent >= 80:
        # TODO: integrate real AI image + text here
        description = f"AI flavor text for {entry.latin_word}"
        image_url = "https://example.com/generated-image.png"

        card = Card(
            vocab_entry_id=entry.id,
            rarity="bronze",
            title=entry.latin_word,
            description=description,
            image_url=image_url,
        )
        db.session.add(card)
        db.session.flush()

        user_card = UserCard(
            user_id=user_id,
            card_id=card.id,
        )
        db.session.add(user_card)

        entry.has_bronze_card = True
        card_unlocked = True
        card_id = card.id

    db.session.commit()

    return jsonify({
        "correct": is_correct,
        "accuracy_percent": entry.accuracy_percent,
        "card_unlocked": card_unlocked,
        "card_id": card_id,
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
