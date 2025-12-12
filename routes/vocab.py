from flask import Blueprint, request, jsonify
from extensions import db
from models import VocabEntry

vocab_bp = Blueprint("vocab", __name__)

def get_current_user_id():
    # TODO: replace with real auth later
    return 1

# read my vocab entries
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

# new VocabEntry-row for the current user
@vocab_bp.post("/")
def add_vocab():
    user_id = get_current_user_id()
    data = request.get_json()
    latin = data.get("latin_word", "").strip()
    german = data.get("german_translation", "").strip()

    if not latin:
        return jsonify({"error": "latin_word required"}), 400

    if not german:
        # TODO: In later stage, call AI here to propose translations.
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

@vocab_bp.put("/<int:entry_id>")
def update_vocab(entry_id):
    """Update Latin and/or German for one vocab entry."""
    user_id = get_current_user_id()
    data = request.get_json() or {}

    entry = VocabEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()

    latin = data.get("latin_word")
    german = data.get("german_translation")

    if latin is not None:
        entry.latin_word = latin.strip()
    if german is not None:
        entry.german_translation = german.strip()

    db.session.commit()
    return jsonify({
        "id": entry.id,
        "latin_word": entry.latin_word,
        "german_translation": entry.german_translation,
        "accuracy_percent": entry.accuracy_percent,
        "has_bronze_card": entry.has_bronze_card,
    })

@vocab_bp.delete("/<int:entry_id>")
def delete_vocab(entry_id):
    """Completely delete a vocab entry and its stats (does not touch quiz history)."""
    user_id = get_current_user_id()
    entry = VocabEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()

    db.session.delete(entry)
    db.session.commit()
    return jsonify({"status": "deleted"})