from flask import Blueprint, jsonify
from flask_login import current_user
from extensions import db
from models import UserCard, Card, VocabEntry

cards_bp = Blueprint("cards", __name__, url_prefix="/api/cards")


def get_current_user_id():
    """Return current user's ID or fallback to demo user ID=1 if not authenticated."""
    return getattr(current_user, 'id', 1)


@cards_bp.get("/")
def list_cards():
    """
    Retrieve all bronze rarity cards for the current user.

    Joins UserCard, Card, and VocabEntry models to fetch card details
    including associated Latin-German vocabulary data.

    Returns:
        JSON list of user cards with rarity, title, description, image, and vocab info.
    """
    user_id = get_current_user_id()
    user_cards = (
        db.session.query(UserCard, Card, VocabEntry)
        .join(Card, UserCard.card_id == Card.id)
        .join(VocabEntry, Card.vocab_entry_id == VocabEntry.id)
        .filter(
            UserCard.user_id == user_id,
            Card.rarity == "bronze",
        )
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
            "accuracy_percent": vocab.accuracy_percent,
        })
    return jsonify(result)
