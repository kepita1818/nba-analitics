from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats
from nba_api.stats.static import teams
from nba_api.stats.library.http import NBAStatsHTTP
from collections import defaultdict
from logging.handlers import RotatingFileHandler
import logging, os, time

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# CONFIGURACIÓN CRÍTICA: Headers para que NBA.com no bloquee
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
}

SEASON = '2025-26'
SEASON_TYPE = 'Regular Season'
TEAM_BY_ID = {}

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
    }

def avg(rows, keys):
    if not rows:
        return {k: 0 for k in keys}
    out = defaultdict(float)
    for r in rows:
        for k in keys:
            out[k] += safe_float(r.get(k))
    n = len(rows)
    return {k: round(out[k] / n, 2) for k in keys}

def fetch_with_retry(endpoint_class, season, season_type, max_retries=3):
    """Intenta obtener datos con retry y delay exponencial."""
    for attempt in range(max_retries):
        try:
            app.logger.info(f"Intentando {endpoint_class.__name__} (intento {attempt + 1}/{max_retries})")
            endpoint = endpoint_class(
                season=season,
                season_type_all_star=season_type,
                timeout=30
            )
            df = endpoint.get_data_frames()[0]
            app.logger.info(f"Éxito: {len(df)} filas obtenidas")
            return df
        except Exception as e:
            app.logger.warning(f"Intento {attempt + 1} fallido: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
            else:
                raise
    return None

@app.route('/api/health')
def health():
    return jsonify({
        'ok': True,
        'season': SEASON,
        'seasonType': SEASON_TYPE,
        'source': 'NBA official stats via nba_api',
        'version': '1.11.4'
    })

@app.route('/api/players')
def api_players():
    try:
        df = fetch_with_retry(leaguedashplayerstats.LeagueDashPlayerStats, SEASON, SEASON_TYPE)
        if df is None or df.empty:
            return jsonify({
                'season': SEASON,
                'count': 0,
                'players': [],
                'warning': 'No hay datos disponibles para esta temporada. Es posible que estemos en offseason o la temporada aún no haya comenzado.'
            }), 200
        
        rows = [fplayer(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        
        return jsonify({
            'season': SEASON,
            'count': len(rows),
            'players': rows[:200]
        })
    except Exception as e:
        app.logger.exception(f"Error en api_players: {e}")
        return jsonify({
            'season': SEASON,
            'count': 0,
            'players': [],
            'error': f'nba stats unavailable: {str(e)}'
        }), 200

@app.route('/api/teams')
def api_teams():
    try:
        df = fetch_with_retry(leaguedashteamstats.LeagueDashTeamStats, SEASON, SEASON_TYPE)
        if df is None or df.empty:
            return jsonify({
                'season': SEASON,
                'count': 0,
                'teams': [],
                'warning': 'No hay datos disponibles para esta temporada.'
            }), 200
        
        rows = [fteam(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        
        return jsonify({
            'season': SEASON,
            'count': len(rows),
            'teams': rows
        })
    except Exception as e:
        app.logger.exception(f"Error en api_teams: {e}")
        return jsonify({
            'season': SEASON,
            'count': 0,
            'teams': [],
            'error': f'nba stats unavailable: {str(e)}'
        }), 200

@app.route('/api/leaders/<category>')
def api_leaders(category):
    """Endpoint adicional para líderes por categoría."""
    from nba_api.stats.endpoints import leagueleaders
    valid_cats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT']
    if category.upper() not in valid_cats:
        return jsonify({'error': f'Categoría inválida. Usa: {valid_cats}'}), 400
    
    try:
        ll = leagueleaders.LeagueLeaders(
            season=SEASON,
            season_type_all_star=SEASON_TYPE,
            stat_category_abbreviation=category.upper(),
            per_mode48='PerGame'
        )
        df = ll.get_data_frames()[0]
        rows = [{
            'rank': int(r.get('RANK', 0)),
            'name': r.get('PLAYER'),
            'team': r.get('TEAM'),
            'value': safe_float(r.get(category.upper()))
        } for _, r in df.head(20).iterrows()]
        return jsonify({'category': category, 'leaders': rows})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': str(e)}), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
