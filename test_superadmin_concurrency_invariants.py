from types import SimpleNamespace

from flask import Flask

from app import db
from models import User
import routes


def _build_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app


def _seed_users():
    actor = User(username='actor', email='actor@example.com', password_hash='x', role='superadmin', is_active=True)
    target = User(username='target', email='target@example.com', password_hash='x', role='superadmin', is_active=True)
    db.session.add_all([actor, target])
    db.session.commit()
    return actor, target

def test_concurrent_role_changes_do_not_remove_last_active_superadmin(monkeypatch):
    app = _build_app()
    flashes = []

    with app.app_context():
        actor, target = _seed_users()
        target_id = str(target.id)

        monkeypatch.setattr(routes, 'flash', lambda msg, category: flashes.append((msg, category)))
        monkeypatch.setattr(routes, 'url_for', lambda *_a, **_k: '/user-management')
        monkeypatch.setattr(routes, 'redirect', lambda loc: loc)

        # Request A demotes one superadmin.
        monkeypatch.setattr(routes, 'current_user', actor)
        with app.test_request_context('/change-user-role', method='POST', data={'user_id': target_id, 'role': 'admin'}):
            routes.change_user_role.__wrapped__.__wrapped__()

        # Request B races and tries to demote the final active superadmin.
        updated_actor = db.session.get(User, actor.id)
        monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=9999, email='other@example.com', is_superadmin=lambda: True))
        with app.test_request_context('/change-user-role', method='POST', data={'user_id': str(updated_actor.id), 'role': 'admin'}):
            routes.change_user_role.__wrapped__.__wrapped__()

        actor_after = db.session.get(User, actor.id)
        assert actor_after.role == 'superadmin'
        assert User.query.filter_by(role='superadmin', is_active=True).count() == 1
        assert any('last active superadmin' in msg.lower() for msg, _ in flashes)


def test_concurrent_deactivate_then_delete_keeps_one_active_superadmin(monkeypatch):
    app = _build_app()
    flashes = []

    with app.app_context():
        actor, target = _seed_users()

        monkeypatch.setattr(routes, 'flash', lambda msg, category: flashes.append((msg, category)))
        monkeypatch.setattr(routes, 'url_for', lambda *_a, **_k: '/user-management')
        monkeypatch.setattr(routes, 'redirect', lambda loc: loc)

        monkeypatch.setattr(routes, 'current_user', actor)
        with app.test_request_context('/toggle-user-status', method='POST', data={'user_id': str(target.id)}):
            routes.toggle_user_status.__wrapped__.__wrapped__()

        # Simulated competing request to delete what is now the last active superadmin.
        actor_db = db.session.get(User, actor.id)
        monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=9999, email='other@example.com', is_superadmin=lambda: True))
        with app.test_request_context('/delete-user', method='POST', data={'user_id': str(actor_db.id)}):
            routes.delete_user.__wrapped__.__wrapped__()

        assert db.session.get(User, actor.id) is not None
        assert User.query.filter_by(role='superadmin', is_active=True).count() == 1
        assert any('last active superadmin' in msg.lower() for msg, _ in flashes)
