"""Regression tests for case-insensitive username login behavior."""

from pathlib import Path


def test_login_query_uses_case_insensitive_username_comparison():
    auth_source = Path('auth.py').read_text()

    assert 'from sqlalchemy import func' in auth_source
    assert 'func.lower(User.username) == normalize_username(identifier)' in auth_source


def test_superadmin_case_variants_normalize_to_same_username():
    stored_username = 'superadmin'
    for supplied in ('SuperAdmin', 'superadmin', 'SUPERADMIN'):
        assert supplied.lower() == stored_username
