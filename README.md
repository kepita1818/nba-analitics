NBA Stats Platform para Render
Build: pip install --upgrade pip setuptools wheel && pip install --only-binary=:all: -r requirements.txt
Start: gunicorn --bind 0.0.0.0:$PORT server:app
Cambios clave v2.0:
Auto-detecta Playoffs vs Regular Season
Fallback automático a temporada anterior si no hay datos
Headers NBA.com para evitar bloqueos
Cache en memoria (5 min) para no saturar la API
Auto-refresh cada 5 minutos + al volver a la pestaña
Manejo de errores robusto (nunca 500 al usuario)
Diseño dark mode profesional estilo props.cash
