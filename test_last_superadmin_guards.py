import pytest
from flask import Flask
from types import SimpleNamespace

import routes


class _FakeFilterResult:
    def __init__(self, count):
        self._count = count

    def count(self):
        return self._count


class _FakeUserQuery:
    def __init__(self, users_by_id, active_superadmin_count):
        self.users_by_id = users_by_id
        self.active_superadmin_count = active_superadmin_count

    def get(self, user_id):
        return self.users_by_id.get(str(user_id))

    def filter(self, *args, **kwargs):
        return _FakeFilterResult(self.active_superadmin_count)


class _DummySession:
    def __init__(self):
        self.committed = False
        self.deleted = None

    def commit(self):
        self.committed = True

    def delete(self, user):
        self.deleted = user


def _setup_common(monkeypatch, target_user, active_superadmin_count):
    actor = SimpleNamespace(id=99, email='actor@example.com', is_superadmin=lambda: True)
    monkeypatch.setattr(routes, 'current_user', actor)

    fake_query = _FakeUserQuery({str(target_user.id): target_user}, active_superadmin_count)
    monkeypatch.setattr(routes.User, 'query', fake_query)

    flashes = []
    monkeypatch.setattr(routes, 'flash', lambda msg, category: flashes.append((msg, category)))
    monkeypatch.setattr(routes, 'url_for', lambda endpoint: f'/{endpoint}')
    monkeypatch.setattr(routes, 'redirect', lambda location: f'REDIRECT:{location}')

    dummy_session = _DummySession()
    monkeypatch.setattr(routes.db, 'session', dummy_session)

    return flashes, dummy_session


@pytest.fixture
def app():
    return Flask(__name__)


def _invoke(view_func, app, data):
    inner = view_func.__wrapped__.__wrapped__
    with app.test_request_context(method='POST', data=data):
        return inner()


def test_toggle_user_status_blocks_last_superadmin(monkeypatch, app):
    user = SimpleNamespace(id=1, username='root', role='superadmin', is_active=True)
    flashes, session = _setup_common(monkeypatch, user, active_superadmin_count=1)

    resp = _invoke(routes.toggle_user_status, app, {'user_id': '1'})

    assert resp == 'REDIRECT:/main.user_management'
    assert ('Cannot remove the last active superadmin.', 'error') in flashes
    assert user.is_active is True
    assert session.committed is False


def test_toggle_user_status_allows_non_last_superadmin(monkeypatch, app):
    user = SimpleNamespace(id=1, username='root', role='superadmin', is_active=True)
    flashes, session = _setup_common(monkeypatch, user, active_superadmin_count=2)

    resp = _invoke(routes.toggle_user_status, app, {'user_id': '1'})

    assert resp == 'REDIRECT:/main.user_management'
    assert user.is_active is False
    assert session.committed is True
    assert any('deactivated successfully' in msg for msg, _ in flashes)


def test_change_user_role_blocks_last_superadmin(monkeypatch, app):
    user = SimpleNamespace(id=1, username='root', role='superadmin', is_active=True)
    flashes, session = _setup_common(monkeypatch, user, active_superadmin_count=1)

    resp = _invoke(routes.change_user_role, app, {'user_id': '1', 'role': 'admin'})

    assert resp == 'REDIRECT:/main.user_management'
    assert ('Cannot remove the last active superadmin.', 'error') in flashes
    assert user.role == 'superadmin'
    assert session.committed is False


def test_change_user_role_allows_non_last_superadmin(monkeypatch, app):
    user = SimpleNamespace(id=1, username='root', role='superadmin', is_active=True)
    flashes, session = _setup_common(monkeypatch, user, active_superadmin_count=3)

    resp = _invoke(routes.change_user_role, app, {'user_id': '1', 'role': 'admin'})

    assert resp == 'REDIRECT:/main.user_management'
    assert user.role == 'admin'
    assert session.committed is True
    assert any('role changed from superadmin to admin' in msg for msg, _ in flashes)


def test_delete_user_blocks_last_superadmin(monkeypatch, app):
    user = SimpleNamespace(id=1, username='root', role='superadmin', is_active=True)
    flashes, session = _setup_common(monkeypatch, user, active_superadmin_count=1)

    resp = _invoke(routes.delete_user, app, {'user_id': '1'})

    assert resp == 'REDIRECT:/main.user_management'
    assert ('Cannot remove the last active superadmin.', 'error') in flashes
    assert session.deleted is None
    assert session.committed is False


def test_delete_user_allows_non_last_superadmin(monkeypatch, app):
    user = SimpleNamespace(id=1, username='root', role='superadmin', is_active=True)
    flashes, session = _setup_common(monkeypatch, user, active_superadmin_count=2)

    resp = _invoke(routes.delete_user, app, {'user_id': '1'})

    assert resp == 'REDIRECT:/main.user_management'
    assert session.deleted is user
    assert session.committed is True
    assert any('deleted successfully' in msg for msg, _ in flashes)
