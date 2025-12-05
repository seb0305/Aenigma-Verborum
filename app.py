from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from routes.vocab import vocab_bp
from models import User, VocabEntry, QuizRound, QuizAnswer, Card, UserCard


db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///latin_vocab.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "change-me"

    db.init_app(app)
    CORS(app)  # allow local frontend to call API

    app.register_blueprint(vocab_bp, url_prefix="/api/vocab")

    with app.app_context():
        db.create_all()

    return app

app = create_app()

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(debug=True)
