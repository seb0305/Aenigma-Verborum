import os
import json
import re
import logging
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from extensions import db
from models import VocabEntry, QuizRound, QuizAnswer, Card, UserCard
from openai import OpenAI
from pydantic import BaseModel
from frag_caesar import get_word_information

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

class WrongOptions(BaseModel):
    options: list[str]

def normalize_german(s: str) -> str:
    """Lowercase, trim, collapse whitespace for robust equality checks."""
    return re.sub(r"\s+", " ", s.strip().lower())


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
        (VocabEntry.accuracy_percent < 95) | (VocabEntry.total_answers < 30)
    ).limit(10).all()



    questions = []
    for e in weak:
        correct = e.german_translation

        # Webscraping context
        context = ""

        # 1) Get FragCaesar info for this Latin word
        frag_result = get_word_information(e.latin_word)  # uses frag_caesar_py.py [web:1]
        if frag_result:
            german_raw = frag_result.get("german", "") or ""
            # split all true meanings: "sie werden genannt|sie werden angeredet|..."
            true_meanings = [
                normalize_german(p) for p in german_raw.split("|") if p.strip()
            ]
        else:
            true_meanings = []

        # also include your stored correct translation as true
        true_meanings.append(normalize_german(correct))
        true_meanings_set = set(true_meanings)

        # 2) Ask OpenAI for three wrong but plausible options
        all_true_german_for_prompt = frag_result.get("german", correct) if frag_result else correct

        prompt = (
            "You get a Latin–German vocabulary pair.\n"
            "Return EXACTLY three wrong but plausible German translations for the Latin word.\n"
            "Important:\n"
            "- Do NOT repeat any of the given true translations.\n"
            "- Answer ONLY with a JSON array of strings, no extra text.\n\n"
            f"Latin: {e.latin_word}\n"
            f"True German translation(s): {all_true_german_for_prompt}"
        )

        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant for Latin–German vocabulary training. "
                            "Always answer ONLY with a JSON array of strings, e.g. "
                            "[\"Wort1\",\"Wort2\",\"Wort3\"]. No explanations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=120,
            )
            content = resp.choices[0].message.content.strip()
            current_app.logger.info("OpenAI content for %s: %s", e.latin_word, content)
            wrong_options_raw = json.loads(content)
        except Exception as ex:
            current_app.logger.error("OpenAI error for %s: %s", e.latin_word, ex)
            wrong_options_raw = [
                "Falsche Übersetzung 1",
                "Falsche Übersetzung 2",
                "Falsche Übersetzung 3",
            ]

        # 3) Filter out any distractor that matches a real meaning
        filtered = []
        for w in wrong_options_raw:
            if not isinstance(w, str):
                continue
            norm = normalize_german(w)
            if not norm:
                continue
            if norm in true_meanings_set:
                continue
            filtered.append(w.strip())

        # 4) Ensure exactly 3 distractors
        wrong_options = filtered[:3]
        while len(wrong_options) < 3:
            wrong_options.append(f"Other wrong translation {len(wrong_options) + 1}")

        import random
        options = wrong_options + [correct]
        random.shuffle(options)
        correct_index = options.index(correct)

        questions.append({
            "id": e.id,
            "latin_word": e.latin_word,
            "options": options,
            "correct_index": correct_index,
        })

    return jsonify(questions)

@quiz_bp.post("/answer")
def answer_question():
    user_id = get_current_user_id()
    data = request.get_json()

    quiz_round_id = data.get("quiz_round_id")
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

# lets the DB store complete round histories
@quiz_bp.post("/finish")
def finish_quiz():
    data = request.get_json()
    quiz_round_id = data.get("quiz_round_id")
    qr = QuizRound.query.get_or_404(quiz_round_id)
    qr.finished_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "ok"})
