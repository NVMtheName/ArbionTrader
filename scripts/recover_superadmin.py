"""Ops-only superadmin recovery utility with strict safeguards.

Usage example:
  export ALLOW_SUPERADMIN_RECOVERY=true
  export SUPERADMIN_RECOVERY_CONFIRM_TOKEN='<one-time-token>'
  python scripts/recover_superadmin.py \
    --email admin@example.com \
    --confirm-token '<one-time-token>' \
    --set-active \
    --rotate-password
"""

import argparse
import getpass
import json
import logging
import os
import secrets
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from models import User
from utils.auth_security import hash_password, normalize_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ops-only superadmin recovery utility")
    parser.add_argument("--email", required=True, help="Target account email")
    parser.add_argument(
        "--confirm-token",
        required=True,
        help="One-time confirmation token that must match SUPERADMIN_RECOVERY_CONFIRM_TOKEN",
    )
    parser.add_argument(
        "--set-active",
        action="store_true",
        help="Set target user is_active=True",
    )
    parser.add_argument(
        "--rotate-password",
        action="store_true",
        help="Rotate password to a cryptographically-random value (force-reset flow)",
    )
    return parser.parse_args()


def ensure_authorized(confirm_token: str) -> None:
    if os.environ.get("ALLOW_SUPERADMIN_RECOVERY", "").strip().lower() != "true":
        raise PermissionError(
            "Blocked: set ALLOW_SUPERADMIN_RECOVERY=true to run this recovery utility."
        )

    expected = os.environ.get("SUPERADMIN_RECOVERY_CONFIRM_TOKEN", "")
    if not expected:
        raise PermissionError(
            "Blocked: SUPERADMIN_RECOVERY_CONFIRM_TOKEN must be set for one-time confirmation."
        )

    if len(confirm_token) < 12:
        raise PermissionError("Blocked: --confirm-token must be at least 12 characters.")

    if not secrets.compare_digest(confirm_token, expected):
        raise PermissionError("Blocked: --confirm-token does not match confirmation token.")


def build_audit_event(*, target: User, changed_fields: dict[str, dict], rotate_password: bool) -> dict:
    return {
        "event": "superadmin_recovery",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": {
            "os_user": getpass.getuser(),
            "invoker": os.environ.get("SUDO_USER") or os.environ.get("USER") or "unknown",
            "hostname": socket.gethostname(),
        },
        "target": {
            "user_id": target.id,
            "email": target.email,
            "username": target.username,
        },
        "changes": changed_fields,
        "operations": {
            "ensure_superadmin": True,
            "set_active": "is_active" in changed_fields,
            "rotate_password": rotate_password,
        },
    }


def main() -> int:
    args = parse_args()

    try:
        ensure_authorized(args.confirm_token)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    app = create_app()
    with app.app_context():
        email = normalize_email(args.email)
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"No user found for email: {email}", file=sys.stderr)
            return 1

        changed_fields: dict[str, dict] = {}

        if user.role != "superadmin":
            changed_fields["role"] = {"from": user.role, "to": "superadmin"}
            user.role = "superadmin"

        if args.set_active and user.is_active is not True:
            changed_fields["is_active"] = {"from": user.is_active, "to": True}
            user.is_active = True

        if args.rotate_password:
            replacement_password = secrets.token_urlsafe(48)
            user.password_hash = hash_password(replacement_password)
            changed_fields["password_hash"] = {"from": "<redacted>", "to": "<rotated>"}
            changed_fields["password_changed_at"] = {
                "from": user.password_changed_at.isoformat() if user.password_changed_at else None,
                "to": datetime.utcnow().isoformat(),
            }
            user.password_changed_at = datetime.utcnow()

        db.session.commit()

        audit_event = build_audit_event(
            target=user,
            changed_fields=changed_fields,
            rotate_password=args.rotate_password,
        )
        logging.info(json.dumps(audit_event, sort_keys=True))

        print(
            "Recovery complete for "
            f"{user.email}. changed_fields={','.join(changed_fields.keys()) or 'none'}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
