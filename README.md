# NBA Stats Platform — lista para Render

## Archivos
- `server.py` → backend Flask
- `web/nba-stats-platform.html` → frontend
- `requirements.txt` → dependencias Python
- `render.yaml` → configuración de Render para web service

## Deploy en Render

### Pasos exactos:

1. **Sube este proyecto a GitHub**
   ```bash
   git init
   git add .
   git commit -m "NBA Stats Platform para Render"
   git branch -M main
   git remote add origin TU_REPO_GITHUB
   git push -u origin main
   ```

2. **En Render Dashboard**
   - Click en **New > Web Service**
   - Conecta tu repositorio de GitHub
   - Configura estos valores:

   | Setting | Value |
   |---------|-------|
   | Name | nba-stats-platform (o el que quieras) |
   | Region | Elige el más cercano a ti |
   | Branch | main |
   | Root | (deja vacío) |
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn --bind 0.0.0.0:$PORT server:app` |
   | Plan | Free (o Starter si quieres más recursos) |

3. **Click Create Web Service**

4. **Espera el deploy** (3-5 minutos normalmente)

5. **Tu app estará en**: `https://nba-stats-platform.onrender.com`

## Variables de entorno

No necesitas variables obligatorias para arrancar. Si quieres logs más detallados:
```
- key: FLASK_ENV
  value: production
```

## Local

```bash
pip install -r requirements.txt
python server.py
```

Luego abre `http://127.0.0.1:5000/`

## Nota importante

La app depende de `nba_api` y consulta datos de NBA Stats en tiempo real.
No es un static site — debes desplegarla como **Web Service**, no como Static Site.
