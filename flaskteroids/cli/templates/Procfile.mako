web: gunicorn wsgi:app -b 0.0.0.0:$PORT --workers 4
worker: celery -A jobs worker --loglevel=info
