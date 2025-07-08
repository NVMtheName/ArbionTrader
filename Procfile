web: gunicorn wsgi:app
worker: celery -A worker.celery worker --loglevel=info
release: sh scripts/heroku-release.sh