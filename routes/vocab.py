from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user
from extensions import db
from models import VocabEntry
import json
import frag_caesar_crawl4ai
from sqlalchemy import or_

vocab_bp = Blueprint("vocab", __name__)

def get_current_user_id():
    """Fallback to demo user ID=1 if not logged in"""
    return getattr(current_user, 'id', 1)

# read my vocab entries
@vocab_bp.get("/")
def list_vocab():
    user_id = get_current_user_id()
    query = VocabEntry.query.filter_by(user_id=user_id).order_by(VocabEntry.created_at.desc())

    # Type filter
    word_type = request.args.get('type')
    if word_type:
        query = query.filter_by(word_type=word_type)

    # Live search
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
        "id": e.id, "latin_word": e.latin_word, "german_translation": e.german_translation,
        "accuracy_percent": e.accuracy_percent, "has_bronze_card": e.has_bronze_card,
        "word_type": e.word_type,  # ✅ Already exposed
    } for e in entries])

# new VocabEntry-row for the current user
@vocab_bp.post("/")
def add_vocab():
    user_id = get_current_user_id()
    data = request.get_json()
    latin = data.get("latin_word", "").strip()
    german = data.get("german_translation", "").strip()

    if not latin:
        return jsonify({"error": "latin_word required"}), 400

    # Check if already exists
    if VocabEntry.query.filter_by(user_id=user_id, latin_word=latin).first():
        return jsonify({"error": "Latin word already exists"}), 409

    # Save if german provided
    if german and german.strip():
        # Auto classify
        try:
            word_type = frag_caesar_crawl4ai.get_word_type(latin)
            flexion_type = frag_caesar_crawl4ai.get_flexion_type(latin) if word_type == "Verb" or word_type == "Nomen" else None
        except:
            word_type, flexion_type = "unknown", None

        entry = VocabEntry(
            user_id=user_id, latin_word=latin, german_translation=german,
            word_type=word_type, flexion_type=flexion_type
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({"id": entry.id}), 201

    # No german → OpenAI translations
    client = current_app.config['client']
    messages = [{
        "role": "user",
        "content": f"List exactly 3 most common German translations for Latin '{latin}' as JSON array only (no other text): [\"trans1\", \"trans2\", \"trans3\"]. Example: amare → [\"lieben\", \"mögen\", \"hasse\"]"
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

        # Auto word_type
        word_type = frag_caesar_crawl4ai.get_word_type(latin)
        flexion_type = frag_caesar_crawl4ai.get_flexion_type(latin) if word_type == "Verb" or word_type == "Nomen" else None

        return jsonify({
            "latin_word": latin,
            "word_type": word_type,
            "flexion_type": flexion_type,
            "translations": translations
        }), 200

    except Exception as ex:
        current_app.logger.error("OpenAI error for %s: %s", latin, ex)
        return jsonify({"error": "Translation failed"}), 500
    """
    if not german:
        # TODO: In later stage, call AI here to propose translations.
        # For now return suggestions so frontend can ask again.
        return jsonify({
            "need_translation_choice": True,
            "suggestions": ["<AI-translation-1>", "<AI-translation-2>"]
        }), 200

    try:
        word_type = frag_caesar_crawl4ai.get_word_type(latin)
        flexion_type = frag_caesar_crawl4ai.get_verb_flexion_type(latin) if word_type == "Verb" else None
    except:
        word_type, flexion_type = "unknown", None

    entry = VocabEntry(
        user_id=user_id,
        latin_word=latin,
        german_translation=german,
        word_type=word_type,
        flexion_type=flexion_type,
    )
    db.session.add(entry)
    db.session.commit()

    return jsonify({"id": entry.id}), 201
    """



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