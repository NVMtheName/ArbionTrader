web: gunicorn --bind 0.0.0.0:$PORT --reuse-port --reload main:app
worker: celery -A worker worker --loglevel=info
release: python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"