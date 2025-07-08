#!/bin/bash

echo "Starting Heroku release phase..."

# Set up environment
export FLASK_APP=wsgi.py

# Run database migrations if needed
echo "Running database migrations..."
python -c "
from app import create_app, db
from flask_migrate import upgrade
import os

app = create_app()
with app.app_context():
    try:
        # Try to run migrations
        upgrade()
        print('Database migrations completed successfully')
    except Exception as e:
        print(f'Migration failed or no migrations needed: {e}')
        # Ensure tables are created
        db.create_all()
        print('Database tables created')
"

# Create default superadmin user if needed
echo "Setting up default admin user..."
python -c "
from app import create_app, db
from models import User
from werkzeug.security import generate_password_hash
import os

app = create_app()
with app.app_context():
    try:
        admin_email = 'nvm427@gmail.com'
        admin_password = '\$@MP\$0n9174201989'
        
        existing_admin = User.query.filter_by(email=admin_email).first()
        if not existing_admin:
            admin_user = User(
                username='superadmin',
                email=admin_email,
                password_hash=generate_password_hash(admin_password),
                role='superadmin'
            )
            db.session.add(admin_user)
            db.session.commit()
            print('Default superadmin user created')
        else:
            print('Default superadmin user already exists')
    except Exception as e:
        print(f'Error creating default user: {e}')
"

echo "Heroku release phase completed successfully!"