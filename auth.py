import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import User
from app import db, limiter
import logging

auth_bp = Blueprint('auth', __name__)


def validate_password_strength(password):
    """Validate password meets strength requirements.
    Returns (is_valid, error_message)."""
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one digit.'
    return True, ''


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")  # Strict limit to prevent spam account creation
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if not all([username, email, password, confirm]):
            flash('All fields are required.', 'error')
            return render_template('register.html')

        if len(username) < 3 or len(username) > 64:
            flash('Username must be between 3 and 64 characters.', 'error')
            return render_template('register.html')

        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            flash('Username can only contain letters, numbers, dots, hyphens, and underscores.', 'error')
            return render_template('register.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('register.html')

        try:
            if User.query.filter_by(email=email).first():
                flash('Email already registered.', 'error')
                return render_template('register.html')

            if User.query.filter_by(username=username).first():
                flash('Username already taken.', 'error')
                return render_template('register.html')

            # New users are always assigned the 'standard' role
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role='standard'
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful. Please log in.', 'success')
            logging.info(f"New user registered: {email} (role: standard)")
            return redirect(url_for('auth.login'))
        except Exception as e:
            logging.error(f"Database error during registration: {e}")
            db.session.rollback()
            flash('A server error occurred. Please try again in a moment.', 'error')
            return render_template('register.html')

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Prevent brute force login attacks
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html')

        try:
            user = User.query.filter_by(email=email).first()
        except Exception as e:
            logging.error(f"Database error during login query: {e}")
            db.session.rollback()
            flash('A server error occurred. Please try again in a moment.', 'error')
            return render_template('login.html')

        if user and check_password_hash(user.password_hash, password):
            if user.is_active:
                login_user(user)
                try:
                    user.last_login = datetime.utcnow()
                    db.session.commit()
                except Exception as e:
                    logging.error(f"Failed to update last_login for {email}: {e}")
                    db.session.rollback()
                logging.info(f"User {user.email} logged in successfully")
                next_page = request.args.get('next')
                try:
                    return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
                except Exception as redirect_error:
                    logging.error(f"Dashboard redirect error: {redirect_error}")
                    flash(f'Login successful! Welcome {user.username}', 'success')
                    return redirect('/')
            else:
                flash('Your account has been deactivated. Please contact an administrator.', 'error')
                logging.warning(f"Deactivated user attempted login: {email}")
        else:
            flash('Invalid email or password.', 'error')
            logging.warning(f"Failed login attempt for: {email}")

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logging.info(f"User {current_user.email} logged out")
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not all([current_password, new_password, confirm_password]):
        flash('All password fields are required.', 'error')
        return redirect(url_for('main.account'))

    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('main.account'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('main.account'))

    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('main.account'))

    current_user.password_hash = generate_password_hash(new_password)
    current_user.password_changed_at = datetime.utcnow()
    db.session.commit()

    flash('Password changed successfully.', 'success')
    logging.info(f"User {current_user.email} changed password")
    return redirect(url_for('main.account'))
