#!/bin/sh
set -e
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 0.5
done
python manage.py migrate
python manage.py runserver 0.0.0.0:8000