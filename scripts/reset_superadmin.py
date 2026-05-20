"""Emergency superadmin password reset utility.

Usage examples:
  ALLOW_ADMIN_RESET=true ENCRYPTION_KEY='<fernet-key>' DATABASE_URL='sqlite:///arbion.db' \
  python scripts/reset_superadmin.py --email admin@example.com --new-password 'StrongPassw0rd!'

  ALLOW_ADMIN_RESET=true ENCRYPTION_KEY='<fernet-key>' DATABASE_URL='sqlite:///arbion.db' \
  python scripts/reset_superadmin.py --username superadmin --new-password 'StrongPassw0rd!' --normalize-username
"""

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from models import User
from utils.auth_security import hash_password, normalize_email, normalize_username


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emergency superadmin recovery utility")
    parser.add_argument("--email", help="Superadmin email address")
    parser.add_argument("--username", help="Superadmin username")
    parser.add_argument("--new-password", required=True, help="New password value")
    parser.add_argument(
        "--normalize-username",
        action="store_true",
        help="Normalize username to lowercase/trimmed format",
    )
    return parser.parse_args()


def ensure_authorized() -> None:
    allow_admin_reset = os.environ.get("ALLOW_ADMIN_RESET", "").strip().lower()
    if allow_admin_reset != "true":
        raise PermissionError(
            "Blocked: set ALLOW_ADMIN_RESET=true to run emergency admin recovery."
        )


def main() -> int:
    args = parse_args()

    if not args.email and not args.username:
        print("Error: pass either --email or --username.", file=sys.stderr)
        return 2

    ensure_authorized()

    app = create_app()
    with app.app_context():
        user = None

        if args.email:
            user = User.query.filter_by(email=normalize_email(args.email)).first()

        if not user and args.username:
            user = User.query.filter_by(username=normalize_username(args.username)).first()

        if not user:
            lookup = args.email or args.username
            print(f"No user found for identifier: {lookup}", file=sys.stderr)
            return 1

        if user.role != "superadmin":
            print(
                f"Refusing reset: target account '{user.email}' is role '{user.role}', not superadmin.",
                file=sys.stderr,
            )
            return 1

        user.password_hash = hash_password(args.new_password)
        user.is_active = True

        if args.normalize_username:
            user.username = normalize_username(user.username)

        db.session.commit()

        logging.info(
            "Emergency admin recovery executed for user_id=%s email=%s username=%s role=%s is_active=%s",
            user.id,
            user.email,
            user.username,
            user.role,
            user.is_active,
        )
        print(f"Superadmin recovery complete for: {user.email}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
