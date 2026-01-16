from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
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
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'message': 'Username exists'}), 400

    user = User(username=data['username'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    login_user(user)  # Auto-login after register
    return jsonify({
        'success': True,
        'user_id': user.id,
        'username': user.username
    }), 201


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True}), 200



@auth_bp.get('/me')
def me():
    if current_user.is_authenticated:
        return jsonify({'user_id': current_user.id, 'username': current_user.username})
    return jsonify({'user_id': None, 'username': 'Guest'}), 200  # ✅ Guest OK
