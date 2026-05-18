"""Create or update a local test account.

Usage:
  ENCRYPTION_KEY='<fernet-key>' DATABASE_URL='sqlite:///arbion.db' \
  python scripts/create_test_account.py
"""

import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from models import User

TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "arbiontrader"


def main() -> None:
    app = create_app()

    with app.app_context():
        user = User.query.filter_by(email=TEST_EMAIL).first()

        if user:
            user.password_hash = generate_password_hash(TEST_PASSWORD)
            user.username = user.username or TEST_EMAIL
            user.is_active = True
            action = "Updated"
        else:
            user = User(
                username=TEST_EMAIL,
                email=TEST_EMAIL,
                password_hash=generate_password_hash(TEST_PASSWORD),
                role="standard",
                is_active=True,
            )
            db.session.add(user)
            action = "Created"

        db.session.commit()
        print(f"{action} account: id={user.id}, email={user.email}")


if __name__ == "__main__":
    main()