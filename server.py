from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats, leagueleaders
from nba_api.stats.static import teams
from nba_api.stats.library.http import NBAStatsHTTP
from collections import defaultdict
from logging.handlers import RotatingFileHandler
import logging, os, time, json

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Headers CRÍTICOS para que NBA.com no bloquee las peticiones
NBAStatsHTTP.headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Host': 'stats.nba.com',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Configuración de temporada - intentamos playoffs primero, luego regular
SEASON = '2025-26'
SEASON_TYPES = ['Playoffs', 'Regular Season']
TEAM_BY_ID = {}

# Cache en memoria para no saturar la API
CACHE = {}
CACHE_TTL = 300  # 5 minutos

def setup_logging():
    os.makedirs('logs', exist_ok=True)
    h = RotatingFileHandler('logs/app.log', maxBytes=10_000_000, backupCount=5)
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    h.setLevel(logging.INFO)
    app.logger.addHandler(h)
    app.logger.setLevel(logging.INFO)
setup_logging()

def get_teams_cached():
    global TEAM_BY_ID
    if not TEAM_BY_ID:
        try:
            TEAM_BY_ID = {t['id']: t for t in teams.get_teams()}
        except Exception as e:
            app.logger.warning(f"Error cargando equipos estáticos: {e}")
            TEAM_BY_ID = {}
    return TEAM_BY_ID

def safe_float(v, d=0.0):
    try:
        return d if v in (None, '') else float(v)
    except Exception:
        return d

def safe_int(v, d=0):
    try:
        return d if v in (None, '') else int(float(v))
    except Exception:
        return d

def fplayer(r):
    return {
        'id': r.get('PLAYER_ID'),
        'name': r.get('PLAYER_NAME'),
        'team': r.get('TEAM_NAME'),
        'pts': safe_float(r.get('PTS')),
        'reb': safe_float(r.get('REB')),
        'ast': safe_float(r.get('AST')),
        'stl': safe_float(r.get('STL')),
        'blk': safe_float(r.get('BLK')),
        'tov': safe_float(r.get('TOV')),
        'min': safe_float(r.get('MIN')),
        'games': safe_int(r.get('GP')),
        'fg_pct': safe_float(r.get('FG_PCT')),
        'fg3_pct': safe_float(r.get('FG3_PCT')),
        'ft_pct': safe_float(r.get('FT_PCT')),
        'fgm': safe_float(r.get('FGM')),
        'fga': safe_float(r.get('FGA')),
        'fg3m': safe_float(r.get('FG3M')),
        'fg3a': safe_float(r.get('FG3A')),
    }

def fteam(r):
    return {
        'id': r.get('TEAM_ID'),
        'name': r.get('TEAM_NAME'),
        'w': safe_int(r.get('W')),
        'l': safe_int(r.get('L')),
        'pts': safe_float(r.get('PTS')),
        'reb': safe_float(r.get('REB')),
        'ast': safe_float(r.get('AST')),
        'stl': safe_float(r.get('STL')),
        'blk': safe_float(r.get('BLK')),
        'tov': safe_float(r.get('TOV')),
        'fg_pct': safe_float(r.get('FG_PCT')),
        'fg3_pct': safe_float(r.get('FG3_PCT')),
        'ft_pct': safe_float(r.get('FT_PCT')),
        'pf': safe_float(r.get('PF')),
        'pace': safe_float(r.get('PACE')),
    }

def get_cache_key(endpoint, season, season_type):
    return f"{endpoint}_{season}_{season_type}"

def get_cached(key):
    if key in CACHE:
        data, timestamp = CACHE[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
    return None

def set_cache(key, data):
    CACHE[key] = (data, time.time())

def fetch_endpoint(endpoint_class, season, season_type, max_retries=3):
    """Obtiene datos con retry, cache y fallback automático."""
    cache_key = get_cache_key(endpoint_class.__name__, season, season_type)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached, season_type

    for attempt in range(max_retries):
        try:
            app.logger.info(f"[{endpoint_class.__name__}] Intento {attempt+1}/{max_retries} | Season: {season} | Type: {season_type}")
            endpoint = endpoint_class(
                season=season,
                season_type_all_star=season_type,
                timeout=30
            )
            df = endpoint.get_data_frames()[0]

            if df is not None and not df.empty:
                app.logger.info(f"[{endpoint_class.__name__}] ÉXITO: {len(df)} filas")
                set_cache(cache_key, df)
                return df, season_type
            else:
                app.logger.warning(f"[{endpoint_class.__name__}] Respuesta vacía")

        except Exception as e:
            app.logger.warning(f"[{endpoint_class.__name__}] Intento {attempt+1} fallido: {str(e)[:200]}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None, None

def fetch_with_fallback(endpoint_class, season, season_types):
    """Intenta cada season_type hasta que uno funcione."""
    for st in season_types:
        df, used_type = fetch_endpoint(endpoint_class, season, st)
        if df is not None:
            return df, used_type, season

    # Si nada funciona, intentamos temporada anterior
    prev_season = f"{int(season.split('-')[0])-1}-{int(season.split('-')[0])}"
    app.logger.warning(f"Intentando temporada anterior: {prev_season}")
    for st in season_types:
        df, used_type = fetch_endpoint(endpoint_class, prev_season, st)
        if df is not None:
            return df, used_type, prev_season

    return None, None, season

@app.route('/api/health')
def health():
    return jsonify({
        'ok': True,
        'season': SEASON,
        'seasonTypes': SEASON_TYPES,
        'source': 'NBA official stats via nba_api',
        'version': '2.0',
        'timestamp': time.time()
    })

@app.route('/api/players')
def api_players():
    try:
        df, used_type, used_season = fetch_with_fallback(
            leaguedashplayerstats.LeagueDashPlayerStats, 
            SEASON, 
            SEASON_TYPES
        )

        if df is None or df.empty:
            return jsonify({
                'season': SEASON,
                'usedSeason': used_season,
                'usedType': used_type,
                'count': 0,
                'players': [],
                'warning': 'No hay datos disponibles. Intenta más tarde.'
            }), 200

        rows = [fplayer(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)

        return jsonify({
            'season': used_season,
            'seasonType': used_type,
            'count': len(rows),
            'players': rows[:200]
        })
    except Exception as e:
        app.logger.exception(f"Error en api_players: {e}")
        return jsonify({
            'season': SEASON,
            'count': 0,
            'players': [],
            'error': str(e)
        }), 200

@app.route('/api/teams')
def api_teams():
    try:
        df, used_type, used_season = fetch_with_fallback(
            leaguedashteamstats.LeagueDashTeamStats,
            SEASON,
            SEASON_TYPES
        )

        if df is None or df.empty:
            return jsonify({
                'season': SEASON,
                'usedSeason': used_season,
                'usedType': used_type,
                'count': 0,
                'teams': [],
                'warning': 'No hay datos disponibles.'
            }), 200

        rows = [fteam(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)

        return jsonify({
            'season': used_season,
            'seasonType': used_type,
            'count': len(rows),
            'teams': rows
        })
    except Exception as e:
        app.logger.exception(f"Error en api_teams: {e}")
        return jsonify({
            'season': SEASON,
            'count': 0,
            'teams': [],
            'error': str(e)
        }), 200

@app.route('/api/leaders/<category>')
def api_leaders(category):
    valid_cats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT']
    if category.upper() not in valid_cats:
        return jsonify({'error': f'Categoría inválida. Usa: {valid_cats}'}), 400

    try:
        # Intentar con cada season type
        for st in SEASON_TYPES:
            try:
                ll = leagueleaders.LeagueLeaders(
                    season=SEASON,
                    season_type_all_star=st,
                    stat_category_abbreviation=category.upper(),
                    per_mode48='PerGame'
                )
                df = ll.get_data_frames()[0]
                if df is not None and not df.empty:
                    rows = [{
                        'rank': int(r.get('RANK', 0)),
                        'name': r.get('PLAYER'),
                        'team': r.get('TEAM'),
                        'value': safe_float(r.get(category.upper()))
                    } for _, r in df.head(20).iterrows()]
                    return jsonify({'category': category, 'seasonType': st, 'leaders': rows})
            except:
                continue

        return jsonify({'error': 'No leaders data available'}), 200
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': str(e)}), 200

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'nba-stats-platform.html')

@app.route('/index.html')
def index_html():
    return send_from_directory(app.static_folder, 'nba-stats-platform.html')

@app.route('/<path:path>')
def static_proxy(path):
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(app.static_folder, path)

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, 'nba-stats-platform.html')

@app.errorhandler(500)
def server_error(e):
    app.logger.exception(f"Error 500: {e}")
    return jsonify({'error': 'Internal server error', 'detail': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
