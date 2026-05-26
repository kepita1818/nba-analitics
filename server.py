from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats
from nba_api.stats.static import teams
from collections import defaultdict
from logging.handlers import RotatingFileHandler
import logging, os

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)
SEASON='2025-26'
SEASON_TYPE='Regular Season'
TEAM_BY_ID={}

def setup_logging():
    os.makedirs('logs', exist_ok=True)
    h=RotatingFileHandler('logs/app.log', maxBytes=10_000_000, backupCount=5)
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    h.setLevel(logging.INFO)
    app.logger.addHandler(h)
    app.logger.setLevel(logging.INFO)
setup_logging()

def get_teams_cached():
    global TEAM_BY_ID
    if not TEAM_BY_ID:
        try:
            TEAM_BY_ID={t['id']: t for t in teams.get_teams()}
        except Exception:
            TEAM_BY_ID={}
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
    return {'id': r.get('PLAYER_ID'), 'name': r.get('PLAYER_NAME'), 'team': r.get('TEAM_NAME'), 'pts': safe_float(r.get('PTS')), 'reb': safe_float(r.get('REB')), 'ast': safe_float(r.get('AST')), 'stl': safe_float(r.get('STL')), 'blk': safe_float(r.get('BLK')), 'tov': safe_float(r.get('TOV')), 'min': safe_float(r.get('MIN')), 'games': safe_int(r.get('GP'))}

def fteam(r):
    return {'id': r.get('TEAM_ID'), 'name': r.get('TEAM_NAME'), 'w': safe_int(r.get('W')), 'l': safe_int(r.get('L')), 'pts': safe_float(r.get('PTS')), 'reb': safe_float(r.get('REB')), 'ast': safe_float(r.get('AST')), 'stl': safe_float(r.get('STL')), 'blk': safe_float(r.get('BLK')), 'tov': safe_float(r.get('TOV'))}

def avg(rows, keys):
    if not rows: return {k:0 for k in keys}
    out=defaultdict(float)
    for r in rows:
        for k in keys: out[k]+=safe_float(r.get(k))
    n=len(rows)
    return {k: round(out[k]/n,2) for k in keys}

@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'season': SEASON, 'seasonType': SEASON_TYPE, 'source': 'NBA official stats via nba_api'})

@app.route('/api/players')
def api_players():
    try:
        df=leaguedashplayerstats.LeagueDashPlayerStats(season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        rows=[fplayer(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        return jsonify({'season': SEASON, 'count': len(rows), 'players': rows[:200]})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'season': SEASON, 'count': 0, 'players': [], 'error': 'nba stats unavailable'}), 200

@app.route('/api/teams')
def api_teams():
    try:
        df=leaguedashteamstats.LeagueDashTeamStats(season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        rows=[fteam(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        return jsonify({'season': SEASON, 'count': len(rows), 'teams': rows})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'season': SEASON, 'count': 0, 'teams': [], 'error': 'nba stats unavailable'}), 200

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
