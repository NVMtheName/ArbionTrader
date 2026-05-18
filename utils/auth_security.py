import os
import re
from typing import Tuple
from werkzeug.security import check_password_hash, generate_password_hash

# Scrypt is the default in modern Werkzeug and offers strong password storage.
# We make it explicit so app behavior is consistent across versions/environments.
PASSWORD_HASH_METHOD = os.environ.get('PASSWORD_HASH_METHOD', 'scrypt')

# Optional server-side pepper to protect hashes if DB is leaked.
PASSWORD_PEPPER = os.environ.get('PASSWORD_PEPPER', '')


def normalize_username(username: str) -> str:
    """Normalize username for consistent storage and uniqueness checks."""
    return (username or '').strip().lower()


def normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def validate_username(username: str) -> Tuple[bool, str]:
    if len(username) < 3 or len(username) > 64:
        return False, 'Username must be between 3 and 64 characters.'
    if not re.match(r'^[a-z0-9_.-]+$', username):
        return False, 'Username can only contain lowercase letters, numbers, dots, hyphens, and underscores.'
    return True, ''


def validate_password_strength(password: str) -> Tuple[bool, str]:
    if len(password or '') < 12:
        return False, 'Password must be at least 12 characters long.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one digit.'
    if not re.search(r'[^A-Za-z0-9]', password):
        return False, 'Password must contain at least one special character.'
    return True, ''


def hash_password(password: str) -> str:
    return generate_password_hash(f"{password}{PASSWORD_PEPPER}", method=PASSWORD_HASH_METHOD)


def verify_password(stored_hash: str, password: str) -> bool:
    return check_password_hash(stored_hash, f"{password}{PASSWORD_PEPPER}")
