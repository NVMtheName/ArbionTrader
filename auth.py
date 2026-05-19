from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from app import db, limiter
from sqlalchemy.orm import load_only
from utils.auth_security import (
    hash_password,
    normalize_email,
    normalize_username,
    validate_password_strength,
    validate_username,
    verify_password,
    verify_password_with_legacy_support,
)
import logging

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")  # Strict limit to prevent spam account creation
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = normalize_username(request.form.get('username', ''))
        email = normalize_email(request.form.get('email', ''))
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if not all([username, email, password, confirm]):
            flash('All fields are required.', 'error')
            return render_template('register.html')

        is_username_valid, username_err = validate_username(username)
        if not is_username_valid:
            flash(username_err, 'error')
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
                password_hash=hash_password(password),
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
        identifier = request.form.get('email', '').strip()
        password = request.form.get('password')

        if not identifier or not password:
            flash('Please enter both email/username and password.', 'error')
            return render_template('login.html')

        normalized_identifier = normalize_email(identifier)

        user = None
        try:
            # Primary lookup supports both email and username.
            # This can fail on older databases that don't have a username column.
            user = User.query.options(
                load_only(
                    User.id,
                    User.username,
                    User.email,
                    User.password_hash,
                )
            ).filter(
                (User.email == normalized_identifier) | (User.username == normalize_username(identifier))
            ).first()
        except Exception as e:
            logging.warning(f"Primary login query failed, trying email-only fallback: {e}")
            db.session.rollback()
            try:
                # Fallback for legacy schemas: authenticate by email only.
                user = User.query.options(
                    load_only(
                        User.id,
                        User.email,
                        User.password_hash,
                    )
                ).filter(User.email == normalized_identifier).first()
            except Exception as fallback_error:
                logging.error(f"Database error during login query fallback: {fallback_error}")
                db.session.rollback()
                flash('A server error occurred. Please try again in a moment.', 'error')
                return render_template('login.html')

        if user:
            is_password_valid, used_legacy_hash = verify_password_with_legacy_support(user.password_hash, password)
        else:
            is_password_valid, used_legacy_hash = (False, False)

        if user and is_password_valid:
            # Some legacy databases may not have `is_active` yet. Treat missing
            # column as active to avoid blocking valid logins.
            try:
                raw_is_active = user.is_active
                # Legacy rows may have NULL is_active values even when the column
                # exists. Treat NULL as active so valid historical accounts are
                # not blocked from logging in.
                is_user_active = True if raw_is_active is None else bool(raw_is_active)
            except Exception as active_error:
                logging.warning(f"Unable to read is_active for {identifier}: {active_error}. Defaulting to active.")
                db.session.rollback()
                is_user_active = True

            if is_user_active:
                if used_legacy_hash:
                    try:
                        user.password_hash = hash_password(password)
                        db.session.commit()
                        logging.info(f"Legacy hash migrated for user: {user.email}")
                    except Exception as migration_error:
                        logging.warning(f"Legacy hash migration failed for {identifier}: {migration_error}")
                        db.session.rollback()
                login_user(user)
                try:
                    user.last_login = datetime.utcnow()
                    db.session.commit()
                except Exception as e:
                    logging.error(f"Failed to update last_login for {identifier}: {e}")
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
                logging.warning(f"Deactivated user attempted login: {identifier}")
        else:
            flash('Invalid email or password.', 'error')
            logging.warning(f"Failed verification for: {identifier}")

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

    if not verify_password(current_user.password_hash, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('main.account'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('main.account'))

    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('main.account'))

    current_user.password_hash = hash_password(new_password)
    current_user.password_changed_at = datetime.utcnow()
    db.session.commit()

    flash('Password changed successfully.', 'success')
    logging.info(f"User {current_user.email} changed password")
    return redirect(url_for('main.account'))
