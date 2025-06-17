#!/usr/bin/env bash
set -e

# 1) Применяем миграции
echo ">>> Applying migrations…"
alembic upgrade head

# 2) Запускаем сервер
echo ">>> Starting Uvicorn…"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 80
