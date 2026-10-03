#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import base64
import os
from pathlib import Path
from urllib.parse import urlparse

path = Path('.env')
text = path.read_text() if path.exists() else Path('.env.example').read_text()
values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line and not line.startswith('#'))
if values.get('DJANGO_SETTINGS_MODULE') != 'config.settings.development':
    raise SystemExit('dev запускается только с config.settings.development в .env')
if urlparse(values.get('DATABASE_URL', '')).hostname != 'postgres':
    raise SystemExit('dev требует локальную Compose БД (hostname postgres), внешние БД не используются')
if not values.get('INVITATION_ENCRYPTION_KEY', '').strip():
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    text = text.replace('INVITATION_ENCRYPTION_KEY=', 'INVITATION_ENCRYPTION_KEY=' + key, 1)
if not path.exists() or path.read_text() != text:
    path.write_text(text)
    path.chmod(0o600)
    print('Локальный .env подготовлен; секреты не выводятся.')
PY
docker compose up --build --detach --wait --wait-timeout 180
docker compose exec -T api python manage.py migrate
docker compose exec -T api python manage.py demo_data
printf '\nИнтерфейс: http://localhost:5173\nAPI: http://localhost:8000/api/docs/\nПисьма: http://localhost:8025\nЛоги: npm run dev:logs\nОстановить: npm run dev:stop\n'
