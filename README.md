# Arbion Dashboard

This project provides a Flask-based trading dashboard. The application uses SQLAlchemy for data storage and integrates with external APIs for trading operations.

## Development

Install dependencies and run the application. Python 3.11 is required.
You can install it with Homebrew (`brew install python@3.11`) or pyenv
(`pyenv install 3.11.x`). When working in the Codex environment, use the
provided setup script to install the Python packages:

```bash
pip install -r requirements.txt  # or ./codex_setup.sh in Codex
export SECRET_KEY=dev-secret
flask run
```

Before starting the server for the first time, create the database tables with:

```
flask db init
flask db migrate
flask db upgrade
```

Set `FLASK_DEBUG=1` while developing to enable debug mode. In production, omit this variable to disable debug features.

Database migrations are managed with **Flask-Migrate**. Initialize and upgrade the database with:

```bash
flask db init      # first time only
flask db migrate
flask db upgrade
```

Background tasks run with **Celery**. You should run both a worker and a beat
process so scheduled tasks execute consistently:

```bash
celery -A worker.celery worker
celery -A worker.celery beat
```

## Performance Improvements

- Removed the `db.create_all()` call from `app.py`. Run `flask db upgrade` to
  create tables using migrations.
- Market data helpers now cache results in memory to reduce repeated network
  requests and speed up backtests and trigger checks.

## Monitoring

If you provide a `SENTRY_DSN` environment variable the application will send
errors to Sentry for centralised monitoring.

## API Analytics

API requests made to routes under `/api/` are logged to the `api_usage_logs`
table. Admin users can view recent logs at `/api-usage`.

Run the unit tests using:

```bash
pytest
```

## OAuth 2.0 Support

The utilities now include a helper to refresh access tokens using the OAuth 2.0 refresh token grant as described in [RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749). This enables connectors like the Schwab integration to obtain new tokens when old ones expire.

The dashboard exposes a ``/refresh_schwab_token`` endpoint that uses this helper to update your stored Schwab access token. The API settings page now includes a **Generate Token** link which redirects you to Schwab's authorization page so you can obtain a refresh token and access token.

After approving the request you will be redirected back to ``/schwab_oauth/callback`` which exchanges the authorization code for tokens and stores them for your account.

To simplify authenticated API calls, the ``utils.oauth`` module also provides a
``bearer_request`` helper which sends an HTTP request with the access token in
the ``Authorization`` header according to
[RFC 6750](https://datatracker.ietf.org/doc/html/rfc6750).

## API Credential Management

API keys for Coinbase, Schwab and OpenAI can be entered directly in the
application. After logging in, navigate to ``/api-settings`` where you will find
form fields for each provider. Submitting the form stores the values in the
``api_keys`` table associated with your user account. The page also provides
**Test Connection** buttons which call ``/test_api/<provider>`` so you can verify
the credentials without modifying source code or environment variables.

When environment variables like ``OPENAI_API_KEY`` or ``COINBASE_API_KEY`` are
present, the application automatically stores them for the superadmin account on
startup. This keeps the connections active during automated deployments without
manually submitting the form.

## OpenAI Research Example

The utilities include a helper that uses the modern ``openai`` client. With a
valid ``OPENAI_API_KEY`` you can run advanced research queries:

```python
from utils.openai_utils import deep_research

query = """
Research the economic impact of semaglutide on global healthcare systems.
Do:
- Include specific figures, trends, statistics, and measurable outcomes.
- Prioritize reliable, up-to-date sources: peer-reviewed research, health
  organizations (e.g., WHO, CDC), regulatory agencies, or pharmaceutical
  earnings reports.
- Include inline citations and return all source metadata.

Be analytical, avoid generalities, and ensure that each section supports
data-backed reasoning that could inform healthcare policy or financial modeling.
"""

result = deep_research(query)
print(result["output"])
```

## Deployment

When deploying to Heroku (or any other production host) the application expects
certain environment variables. When using the `uv` package manager you must
specify the Python version with a `.python-version` file instead of
`runtime.txt`. This project requires **Python 3.11**, so create a
`.python-version` file containing `3.11`. The
most important environment variables are:

- `SECRET_KEY` – required for Flask's session management. The application will
  not boot if this variable is missing.
- `DATABASE_URL` – the database connection string. Heroku supplies this under
  the same name. Values beginning with `postgres://` are automatically
  converted to the modern `postgresql://` format by `config.py`.

Set these variables using the Heroku CLI before starting the application:

```bash
heroku config:set SECRET_KEY=<your secret key>
heroku config:set DATABASE_URL=<your database url>
```

After configuring the environment variables you can deploy and scale the app
using the provided `Procfile`, which runs `gunicorn wsgi:app`.
The `Procfile` now includes a `release` step that executes `scripts/heroku-release.sh` to run `flask db upgrade` automatically.

The application also calls `flask db upgrade` on startup to prevent boot
failures if the database schema is out of date.

If the `migrations` directory has not been created yet the startup routine
will simply log a warning and continue. Run the following once to initialise
the migration scripts:

```bash
flask db init
flask db migrate -m "initial"
flask db upgrade
```

## Superadmin Credentials

When the application starts it can automatically create an initial
superadmin account. Provide the email and password via the
`SUPERADMIN_EMAIL` and `SUPERADMIN_PASSWORD` environment variables before
launching the Flask app. If these variables are set the account will be
created on startup and you can log in with those credentials.

For example, to create a superadmin account with the provided credentials:

```bash
export SUPERADMIN_EMAIL=nvm427@gmail.com
export SUPERADMIN_PASSWORD='$@MP$0n9174201989'
flask run
```

## User Registration

Regular users can create an account by visiting `/auth/register` on the running
application. The form collects a username, email address and password. Submitted
passwords are hashed using Werkzeug's password hashing utilities before being
stored in the database. After registering, log in at `/auth/login`.


## Creating Pull Requests for Tasks

A helper script is provided to submit updates directly from the `main` branch
without creating feature branches. The script pushes the local `main` branch and
opens a pull request via the GitHub API.

```bash
export GITHUB_REPOSITORY=owner/repo
export GITHUB_TOKEN=<your token>
python scripts/create_pr_to_main.py "Update" "Optional description"
```

## Continuous Integration

The repository includes a simple GitHub Actions workflow that installs the
dependencies and runs the test suite on every push or pull request to the
`main` branch. This helps ensure the dashboard remains compatible with the
Coinbase style APIs and that new contributions do not break existing
functionality.

The workflow now uses **Python 3.11** to match the production runtime
specified in `.python-version`.

## Containerisation

The repository includes a `Dockerfile` and `docker-compose.yml` for running
the web application, Celery worker/beat, Redis and Postgres. Build and start
the stack with:

```bash
docker compose up --build
```

The Docker entrypoint automatically runs `flask db upgrade` so database
migrations are applied on startup.

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values before running the
containers or the development server. Important Schwab variables include
``SCHWAB_CLIENT_ID``, ``SCHWAB_CLIENT_SECRET``, ``SCHWAB_REDIRECT_URI``,
``SCHWAB_ACCESS_TOKEN`` and ``SCHWAB_REFRESH_TOKEN``.

## Security Settings

`config.py` now honours `SESSION_COOKIE_SECURE` and `SESSION_COOKIE_SAMESITE`
environment variables. Ensure these are set appropriately in production to
protect user sessions.

## Running Background Workers

If deploying without Docker, remember to start both the Celery worker and beat
processes so scheduled tasks and queued jobs run reliably.

## Database Backups and Monitoring

Set up regular backups of your Postgres database (for example using `pg_dump`
or your hosting provider's snapshot feature) and supply a `SENTRY_DSN` to enable
error monitoring in production.

