from datetime import datetime
from extensions import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class VocabEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    latin_word = db.Column(db.String(120), nullable=False)
    german_translation = db.Column(db.String(255), nullable=False)
    total_answers = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    accuracy_percent = db.Column(db.Float, default=0.0)
    has_bronze_card = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuizRound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)

class QuizAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_round_id = db.Column(db.Integer, db.ForeignKey("quiz_round.id"), nullable=False)
    vocab_entry_id = db.Column(db.Integer, db.ForeignKey("vocab_entry.id"), nullable=False)
    was_correct = db.Column(db.Boolean, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vocab_entry_id = db.Column(db.Integer, db.ForeignKey("vocab_entry.id"), nullable=False)
    rarity = db.Column(db.String(20), default="bronze")
    title = db.Column(db.String(120))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))

class UserCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("card.id"), nullable=False)
    acquired_at = db.Column(db.DateTime, default=datetime.utcnow)
