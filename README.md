# NBA Stats Platform para Render

## Deploy
- Build: `pip install --upgrade pip setuptools wheel && pip install --only-binary=:all: -r requirements.txt`
- Start: `gunicorn --bind 0.0.0.0:$PORT server:app`

## Temporada
- Usa la temporada actual 2025-26.

## Estructura
- `server.py`
- `web/nba-stats-platform.html`
- `requirements.txt`
- `render.yaml`
