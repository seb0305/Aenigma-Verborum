from flask import Flask, send_from_directory
from flask_cors import CORS
from extensions import db
from models import User, VocabEntry, QuizRound, QuizAnswer, Card, UserCard
from routes.vocab import vocab_bp
from routes.quiz import quiz_bp
from routes.cards import cards_bp

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///latin_vocab.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # app.config["SECRET_KEY"] = "change-me"

    db.init_app(app)
    CORS(app)  # allow local frontend to call API

    # adds blueprints whose routes map directly to common operations on SQLite tables
    app.register_blueprint(vocab_bp, url_prefix="/api/vocab")
    app.register_blueprint(quiz_bp, url_prefix="/api/quiz")
    app.register_blueprint(cards_bp, url_prefix="/api/cards")

    with app.app_context():
        # ORM definitions turned into real SQLite tables before any API logic runs
        db.create_all()

    return app

app = create_app()

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(debug=True)
