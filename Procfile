web: gunicorn --bind 0.0.0.0:$PORT --reuse-port --reload main:app
worker: celery -A worker.celery worker --loglevel=info --concurrency=2 --max-memory-per-child=400000
beat: celery -A worker.celery beat --loglevel=info
release: python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"