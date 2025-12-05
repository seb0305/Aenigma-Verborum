from datetime import datetime
from extensions import db

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

