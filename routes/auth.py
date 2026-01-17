"""
Authentication Blueprint for Aenigma Verborum.
Handles user registration, login, logout, and profile retrieval using Flask-Login.
Integrates with User model for secure password management and session handling.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and start session."""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'success': False, 'message': 'Missing credentials'}), 400

    user = User.query.filter_by(username=data['username']).first()
    if user and user.check_password(data['password']):
        login_user(user)
        return jsonify({
            'success': True,
            'user_id': user.id,
            'username': user.username
        }), 200

    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@auth_bp.route('/register', methods=['POST'])
def register():
    """Create new user account and auto-login."""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'success': False, 'message': 'Missing username or password'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400

    user = User(username=data['username'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({
        'success': True,
        'user_id': user.id,
        'username': user.username
    }), 201


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """End user session."""
    logout_user()
    return jsonify({'success': True}), 200


@auth_bp.route('/me')
@login_required
def me():
    """Return current authenticated user details."""
    return jsonify({
        'user_id': current_user.id,
        'username': current_user.username
    }), 200
