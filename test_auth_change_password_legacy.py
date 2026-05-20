from types import SimpleNamespace

from werkzeug.security import check_password_hash, generate_password_hash

import auth
import utils.auth_security as auth_security


def test_change_password_accepts_legacy_hash_and_rotates_to_peppered_hash(monkeypatch):
    current_password = "LegacyPass123!"
    new_password = "NewCompliant456!"

    # Simulate production peppering while user still has an old unpeppered hash.
    monkeypatch.setattr(auth_security, "PASSWORD_PEPPER", "pepper")

    user = SimpleNamespace(
        password_hash=generate_password_hash(current_password),
        email="legacy@example.com",
        password_changed_at=None,
    )

    commit_calls = []

    monkeypatch.setattr(auth, "current_user", user)
    monkeypatch.setattr(auth.db.session, "commit", lambda: commit_calls.append(True))
    monkeypatch.setattr(auth, "flash", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth, "url_for", lambda *args, **kwargs: "/account")
    monkeypatch.setattr(auth, "redirect", lambda location: location)

    with auth.auth_bp.test_request_context(
        "/auth/change-password",
        method="POST",
        data={
            "current_password": current_password,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    ):
        result = auth.change_password.__wrapped__()

    assert result == "/account"
    assert len(commit_calls) == 1

    # New password should now verify with pepper-aware path (i.e., newly compliant hash).
    assert auth_security.verify_password(user.password_hash, new_password)
    # And old password should not work anymore.
    assert not auth_security.verify_password_with_legacy_support(user.password_hash, current_password)[0]
    # Stored hash should no longer be the old unpeppered hash.
    assert not check_password_hash(user.password_hash, current_password)
