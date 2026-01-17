import os
from dotenv import load_dotenv
import frag_caesar_bs4

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from extensions import db
from flask_login import LoginManager, current_user, AnonymousUserMixin
from werkzeug.security import generate_password_hash
from models import User
from openai import OpenAI

load_dotenv()


def create_app():
    """
    Factory function to create and configure the Flask application.

    Initializes Flask app with database, blueprints, authentication,
    CORS, and demo user. Returns fully configured app instance.
    """
    # Import blueprints after load_dotenv to ensure env vars available
    from routes.vocab import vocab_bp
    from routes.quiz import quiz_bp
    from routes.cards import cards_bp
    from routes.auth import auth_bp

    app = Flask(__name__)

    # Configuration from environment variables
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///latin_vocab.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # AI configuration for quizzes and features
    app.config['OPENAI_MODEL'] = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    app.config['GEMINI_MODEL'] = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    # Global OpenAI client (used by quiz blueprint)
    app.config['client'] = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Register API blueprints for modular routing
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(vocab_bp, url_prefix='/api/vocab')
    app.register_blueprint(quiz_bp, url_prefix='/api/quiz')
    app.register_blueprint(cards_bp, url_prefix='/api/cards')

    # Initialize extensions
    db.init_app(app)
    CORS(app)

    # Flask-Login configuration for user authentication
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.anonymous_user = AnonymousUserMixin

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create database tables and demo user
    with app.app_context():
        db.create_all()
        _create_demo_user_if_missing()

    return app


def _create_demo_user_if_missing():
    """Create demo user 'demo'/'demo' if not exists for testing."""
    demo_user = User.query.filter_by(username='demo').first()
    if not demo_user:
        demo_user = User(
            username='demo',
            password_hash=generate_password_hash('demo')
        )
        db.session.add(demo_user)
        db.session.commit()
        print("✅ Demo user created: username='demo', password='demo'")


# Create and configure app
app = create_app()


@app.route("/")
def index():
    """Serve static index.html for frontend."""
    return send_from_directory("static", "index.html")


@app.route('/api/kurzuebersicht/<word>')
def api_kurzuebersicht(word):
    """
    API endpoint for Latin word lookup using FragCaesar crawler.

    Fetches morphological data (declensions, conjugations) from frag-caesar.de
    and returns structured JSON response.

    Args:
        word (str): Latin word to lookup (e.g., 'nox')

    Returns:
        JSON: List of dicts with latin, type, Geschlecht, flexion_type, form, german
    """
    data = frag_caesar_bs4.get_kurzuebersicht(word)
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)
