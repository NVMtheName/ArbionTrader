import ast
import os
from pathlib import Path

class SQLAlchemyError(Exception):
    pass


class _Logger:
    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


def _load_helpers():
    source = Path('auth.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    funcs = {
        node.name: ast.get_source_segment(source, node)
        for node in module.body
        if isinstance(node, ast.FunctionDef)
    }
    code = funcs['_legacy_is_active_compat_enabled'] + '\n\n' + funcs['resolve_user_active_status']
    calls = []

    class _Session:
        def rollback(self):
            calls.append('rollback')

    namespace = {
        'os': os,
        'logging': _Logger(),
        'SQLAlchemyError': SQLAlchemyError,
        'db': type('DB', (), {'session': _Session()})(),
        'normalize_username': lambda s: str(s).strip().lower(),
    }
    exec(code, namespace)
    return namespace['resolve_user_active_status'], calls


class _MissingActiveAttributeUser:
    pass


class _ActiveUser:
    is_active = True


class _DeactivatedUser:
    is_active = False


class _DbErrorUser:
    @property
    def is_active(self):
        raise _SyntheticDbReadError('read failed')


class _SyntheticDbReadError(SQLAlchemyError):
    pass


def test_load_only_includes_is_active_for_primary_and_fallback_queries():
    auth_source = Path('auth.py').read_text(encoding='utf-8')
    assert auth_source.count('User.is_active') >= 2


def test_active_user_login_success_resolution(monkeypatch):
    monkeypatch.delenv('AUTH_LEGACY_IS_ACTIVE_COMPAT', raising=False)
    resolve, _ = _load_helpers()
    is_active, reason = resolve(_ActiveUser(), 'active@example.com')
    assert is_active is True
    assert reason == 'active'


def test_deactivated_user_denied_resolution(monkeypatch):
    monkeypatch.delenv('AUTH_LEGACY_IS_ACTIVE_COMPAT', raising=False)
    resolve, _ = _load_helpers()
    is_active, reason = resolve(_DeactivatedUser(), 'off@example.com')
    assert is_active is False
    assert reason == 'deactivated'


def test_legacy_missing_column_behavior_flag_off(monkeypatch):
    monkeypatch.delenv('AUTH_LEGACY_IS_ACTIVE_COMPAT', raising=False)
    resolve, _ = _load_helpers()
    is_active, reason = resolve(_MissingActiveAttributeUser(), 'legacy-off@example.com')
    assert is_active is False
    assert reason == 'deactivated'


def test_legacy_missing_column_behavior_flag_on(monkeypatch):
    monkeypatch.setenv('AUTH_LEGACY_IS_ACTIVE_COMPAT', 'true')
    resolve, _ = _load_helpers()
    is_active, reason = resolve(_MissingActiveAttributeUser(), 'legacy-on@example.com')
    assert is_active is True
    assert reason == 'legacy_compat'


def test_db_read_error_denies_login(monkeypatch):
    monkeypatch.delenv('AUTH_LEGACY_IS_ACTIVE_COMPAT', raising=False)
    resolve, calls = _load_helpers()
    is_active, reason = resolve(_DbErrorUser(), 'db-error@example.com')
    assert is_active is False
    assert reason == 'db_error'
    assert calls == ['rollback']
