from flask import Blueprint, request, jsonify
from extensions import db
from models import VocabEntry

vocab_bp = Blueprint("vocab", __name__)

def get_current_user_id():
    # TODO: replace with real auth later
    return 1

@vocab_bp.get("/")
def list_vocab():
    user_id = get_current_user_id()
    entries = VocabEntry.query.filter_by(user_id=user_id).order_by(VocabEntry.created_at.desc()).all()
    return jsonify([
        {
            "id": e.id,
            "latin_word": e.latin_word,
            "german_translation": e.german_translation,
            "accuracy_percent": e.accuracy_percent,
            "has_bronze_card": e.has_bronze_card,
        }
        for e in entries
    ])

@vocab_bp.post("/")
def add_vocab():
    user_id = get_current_user_id()
    data = request.get_json()
    latin = data.get("latin_word", "").strip()
    german = data.get("german_translation", "").strip()

    if not latin:
        return jsonify({"error": "latin_word required"}), 400

    if not german:
        # In real app, call AI here to propose translations.
        # For now return suggestions so frontend can ask again.
        return jsonify({
            "need_translation_choice": True,
            "suggestions": ["<AI-translation-1>", "<AI-translation-2>"]
        }), 200

    entry = VocabEntry(
        user_id=user_id,
        latin_word=latin,
        german_translation=german,
    )
    db.session.add(entry)
    db.session.commit()

    return jsonify({"id": entry.id}), 201
