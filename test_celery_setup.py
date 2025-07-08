#!/usr/bin/env python3
"""
Test script to verify Celery setup for Heroku deployment
"""
import os
import sys

def test_celery_setup():
    """Test if Celery is properly configured"""
    print("Testing Celery setup for Heroku deployment...")
    
    # Test 1: Check if required files exist
    required_files = ['wsgi.py', 'worker.py', 'Procfile', 'scripts/heroku-release.sh']
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file} exists")
        else:
            print(f"✗ {file} missing")
            return False
    
    # Test 2: Check Procfile content
    try:
        with open('Procfile', 'r') as f:
            content = f.read()
            if 'web: gunicorn wsgi:app' in content:
                print("✓ Procfile has correct web process")
            else:
                print("✗ Procfile web process incorrect")
                return False
            
            if 'worker: celery -A worker.celery worker --loglevel=info' in content:
                print("✓ Procfile has correct worker process")
            else:
                print("✗ Procfile worker process incorrect")
                return False
                
            if 'release: sh scripts/heroku-release.sh' in content:
                print("✓ Procfile has correct release process")
            else:
                print("✗ Procfile release process incorrect")
                return False
    except Exception as e:
        print(f"✗ Error reading Procfile: {e}")
        return False
    
    # Test 3: Test imports
    try:
        from wsgi import app
        print("✓ WSGI app imports successfully")
    except Exception as e:
        print(f"✗ WSGI app import failed: {e}")
        return False
    
    try:
        from worker import celery
        print("✓ Celery worker imports successfully")
    except Exception as e:
        print(f"✗ Celery worker import failed: {e}")
        return False
    
    # Test 4: Check if scheduler is Celery-aware
    try:
        from utils.scheduler import TaskScheduler
        scheduler = TaskScheduler(use_celery=True)
        print("✓ TaskScheduler supports Celery mode")
    except Exception as e:
        print(f"✗ TaskScheduler Celery mode failed: {e}")
        return False
    
    # Test 5: Check release script
    if os.path.exists('scripts/heroku-release.sh'):
        if os.access('scripts/heroku-release.sh', os.X_OK):
            print("✓ Release script is executable")
        else:
            print("✗ Release script not executable")
            return False
    
    print("\n🎉 All tests passed! Ready for Heroku deployment with Celery.")
    return True

if __name__ == '__main__':
    success = test_celery_setup()
    sys.exit(0 if success else 1)