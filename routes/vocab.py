from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user
from extensions import db
from models import VocabEntry
import json
import frag_caesar_bs4
from sqlalchemy import or_

vocab_bp = Blueprint("vocab", __name__)


def get_current_user_id():
    """Return current user's ID or fallback to demo user ID=1 if not logged in."""
    return getattr(current_user, 'id', 1)


@vocab_bp.get("/")
def list_vocab():
    """
    Retrieve vocabulary entries for current user with optional filtering.

    Supports:
    - 'type' query param for word_type filtering
    - 'search' query param for live search across latin_word and german_translation
    """
    user_id = get_current_user_id()
    query = VocabEntry.query.filter_by(user_id=user_id).order_by(VocabEntry.created_at.desc())

    # Apply type filter
    word_type = request.args.get('type')
    if word_type:
        query = query.filter_by(word_type=word_type)

    # Apply live search
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                VocabEntry.latin_word.ilike(f'%{search}%'),
                VocabEntry.german_translation.ilike(f'%{search}%')
            )
        )

    entries = query.all()
    return jsonify([{
        "id": e.id,
        "latin_word": e.latin_word,
        "german_translation": e.german_translation,
        "accuracy_percent": e.accuracy_percent,
        "has_bronze_card": e.has_bronze_card,
        "word_type": e.word_type,
    } for e in entries])


@vocab_bp.post("/")
def add_vocab():
    """
    Add new vocabulary entry for current user.

    - If german_translation provided: saves entry immediately
    - If no german_translation: returns OpenAI-generated German translations (3 options)
      for frontend selection, plus word_type and flexion_type
    """
    user_id = get_current_user_id()
    data = request.get_json()
    latin = data.get("latin_word", "").strip()
    german = (data.get("german_translation", "") or "").strip()

    if not latin:
        return jsonify({"error": "latin_word required"}), 400

    # Prevent duplicates
    if VocabEntry.query.filter_by(user_id=user_id, latin_word=latin).first():
        return jsonify({"error": "Latin word already exists"}), 409

    # Case 1: German translation provided → save immediately
    if german:
        try:
            word_type = frag_caesar_bs4.get_word_type(latin)
            flexion_type = frag_caesar_bs4.get_flexion_type(latin) if word_type in ("Verb", "Nomen") else None
        except Exception:
            word_type, flexion_type = "unknown", None

        entry = VocabEntry(
            user_id=user_id,
            latin_word=latin,
            german_translation=german,
            word_type=word_type,
            flexion_type=flexion_type
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({"id": entry.id}), 201

    # Case 2: No German → get OpenAI translations
    client = current_app.config['client']
    messages = [{
        "role": "user",
        "content": (
            f"List exactly 3 most common German translations for Latin '{latin}' "
            f"as JSON array only (no other text): [\"trans1\", \"trans2\", \"trans3\"]. "
            f"Example: amare → [\"lieben\", \"mögen\", \"hasse\"]"
        )
    }]

    try:
        resp = client.chat.completions.create(
            model=current_app.config['OPENAI_MODEL'],
            messages=messages,
            max_tokens=120,
        )
        content = resp.choices[0].message.content.strip()
        current_app.logger.info("OpenAI translations for %s: %s", latin, content)

        translations = json.loads(content)
        if not isinstance(translations, list) or len(translations) != 3:
            raise ValueError("Invalid translation list")

        # Auto-classify word
        word_type = frag_caesar_bs4.get_word_type(latin)
        flexion_type = frag_caesar_bs4.get_flexion_type(latin) if word_type in ("Verb", "Nomen") else None

        return jsonify({
            "latin_word": latin,
            "word_type": word_type,
            "flexion_type": flexion_type,
            "translations": translations
        }), 200

    except Exception as ex:
        current_app.logger.error("OpenAI error for %s: %s", latin, ex)
        return jsonify({"error": "Translation failed"}), 500


@vocab_bp.put("/<int:entry_id>")
def update_vocab(entry_id):
    """Update latin_word and/or german_translation for specific entry."""
    user_id = get_current_user_id()
    data = request.get_json() or {}

    entry = VocabEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()

    if "latin_word" in data:
        entry.latin_word = data["latin_word"].strip()
    if "german_translation" in data:
        entry.german_translation = data["german_translation"].strip()

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
    """Delete vocabulary entry and its stats (quiz history preserved)."""
    user_id = get_current_user_id()
    entry = VocabEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()

    db.session.delete(entry)
    db.session.commit()
    return jsonify({"status": "deleted"})


@vocab_bp.route("/import/<latin_word>", methods=["POST"])
def import_vocab(latin_word):
    """Import searched vocab to user's book if not already present."""
    user_id = get_current_user_id()
    existing = VocabEntry.query.filter_by(user_id=user_id, latin_word=latin_word).first()
    if existing:
        return jsonify({"status": "already_exists", "id": existing.id}), 200

    data = frag_caesar_bs4.get_kurzuebersicht(latin_word)
    german = data[0]["german"] if data and data[0].get("german") else "Übersetzung fehlt"
    # Auto-classify word
    word_type = frag_caesar_bs4.get_word_type(latin_word)
    flexion_type = frag_caesar_bs4.get_flexion_type(latin_word) if word_type in ("Verb", "Nomen") else None
    entry = VocabEntry(
        user_id=user_id,
        latin_word=latin_word,
        german_translation=german.split()[0],
        word_type=word_type,
        flexion_type = flexion_type
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({"status": "imported", "id": entry.id}), 201