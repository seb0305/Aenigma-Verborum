from flask import Blueprint, jsonify
from extensions import db
from models import UserCard, Card, VocabEntry

cards_bp = Blueprint("cards", __name__)

def get_current_user_id():
    # TODO: implement user management
    return 1

# returns each card for current user
@cards_bp.get("/")
def list_cards():
    user_id = get_current_user_id()
    user_cards = (
        db.session.query(UserCard, Card, VocabEntry)
        .join(Card, UserCard.card_id == Card.id)
        .join(VocabEntry, Card.vocab_entry_id == VocabEntry.id)
        .filter(UserCard.user_id == user_id)
        .all()
    )

    result = []
    for uc, card, vocab in user_cards:
        result.append({
            "card_id": card.id,
            "rarity": card.rarity,
            "title": card.title,
            "description": card.description,
            "image_url": card.image_url,
            "latin_word": vocab.latin_word,
            "german_translation": vocab.german_translation,
        })
    return jsonify(result)
