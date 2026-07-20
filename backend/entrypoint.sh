#!/bin/sh

set -e

echo "🚀 Starting Vyapar Margadarshan..."

echo "📦 Running migrations..."
python manage.py migrate --noinput

echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "🌐 Starting Gunicorn..."
exec gunicorn vyapar_margadarshan.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120
    