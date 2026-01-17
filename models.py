"""
SQLAlchemy models for Aenigma Verborum Latin vocabulary quiz application.

Defines core domain entities: users with authentication, vocabulary entries
with accuracy tracking and morphology, quiz rounds and answers for session history,
collectible cards with rarity system, and user-card ownership.
"""

from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    """User account model with secure password authentication."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, password)


class VocabEntry(db.Model):
    """Latin vocabulary entry with German translation, usage stats, and morphology."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    latin_word = db.Column(db.String(120), nullable=False)
    german_translation = db.Column(db.String(255), nullable=False)
    total_answers = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    accuracy_percent = db.Column(db.Float, default=0.0)
    has_bronze_card = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    word_type = db.Column(db.String(20), default="unknown")  # e.g., "Noun", "Verb"
    flexion_type = db.Column(db.String(50), default=None, nullable=True)


class QuizRound(db.Model):
    """Quiz session tracking start/finish times, length, and question count."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    random_length = db.Column(db.Integer)  # Number of questions (3-7)
    asked_count = db.Column(db.Integer, default=0)


class QuizAnswer(db.Model):
    """Individual quiz question response with correctness and timestamp."""
    id = db.Column(db.Integer, primary_key=True)
    quiz_round_id = db.Column(db.Integer, db.ForeignKey("quiz_round.id"), nullable=False)
    vocab_entry_id = db.Column(db.Integer, db.ForeignKey("vocab_entry.id"), nullable=False)
    was_correct = db.Column(db.Boolean, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)


class Card(db.Model):
    """Collectible card template with rarity, title, description, and image."""
    id = db.Column(db.Integer, primary_key=True)
    vocab_entry_id = db.Column(db.Integer, db.ForeignKey("vocab_entry.id"), nullable=False)
    rarity = db.Column(db.String(20), default="bronze")
    title = db.Column(db.String(120))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))


class UserCard(db.Model):
    """User ownership of specific cards with acquisition timestamp."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("card.id"), nullable=False)
    acquired_at = db.Column(db.DateTime, default=datetime.utcnow)
