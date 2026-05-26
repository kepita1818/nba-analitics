from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats, playergamelog, teamgamelog, commonplayerinfo
from nba_api.stats.static import teams
from collections import defaultdict
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

SEASON = '2025-26'
SEASON_TYPE = 'Regular Season'
TEAM_BY_ID = {}


def setup_logging():
    os.makedirs('logs', exist_ok=True)
    handler = RotatingFileHandler('logs/app.log', maxBytes=10_000_000, backupCount=5)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


setup_logging()


def get_teams_cached():
    global TEAM_BY_ID
    if not TEAM_BY_ID:
        try:
            TEAM_BY_ID = {t['id']: t for t in teams.get_teams()}
        except Exception:
            TEAM_BY_ID = {}
    return TEAM_BY_ID


def safe_float(v, default=0.0):
    try:
        return default if v in (None, '') else float(v)
    except Exception:
        return default


def safe_int(v, default=0):
    try:
        return default if v in (None, '') else int(float(v))
    except Exception:
        return default


def avg_stats(rows, keys):
    if not rows:
        return {k: 0 for k in keys}
    totals = defaultdict(float)
    n = len(rows)
    for row in rows:
        for k in keys:
            totals[k] += safe_float(row.get(k))
    return {k: round(totals[k] / n, 2) for k in keys}


def format_player_stats(row):
    return {
        'id': row.get('PLAYER_ID'),
        'name': row.get('PLAYER_NAME'),
        'team': row.get('TEAM_NAME'),
        'pts': safe_float(row.get('PTS')),
        'reb': safe_float(row.get('REB')),
        'ast': safe_float(row.get('AST')),
        'stl': safe_float(row.get('STL')),
        'blk': safe_float(row.get('BLK')),
        'tov': safe_float(row.get('TOV')),
        'min': safe_float(row.get('MIN')),
        'games': safe_int(row.get('GP'))
    }


def format_team_stats(row):
    return {
        'id': row.get('TEAM_ID'),
        'name': row.get('TEAM_NAME'),
        'w': safe_int(row.get('W')),
        'l': safe_int(row.get('L')),
        'pts': safe_float(row.get('PTS')),
        'reb': safe_float(row.get('REB')),
        'ast': safe_float(row.get('AST')),
        'stl': safe_float(row.get('STL')),
        'blk': safe_float(row.get('BLK')),
        'tov': safe_float(row.get('TOV'))
    }


@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'season': SEASON, 'seasonType': SEASON_TYPE, 'source': 'NBA Official Stats via nba_api'})


@app.route('/api/players')
def api_players():
    try:
        df = leaguedashplayerstats.LeagueDashPlayerStats(season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        rows = [format_player_stats(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        return jsonify({'season': SEASON, 'count': len(rows), 'players': rows[:200]})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'season': SEASON, 'count': 0, 'players': [], 'error': 'official nba stats unavailable'}), 200


@app.route('/api/teams')
def api_teams():
    try:
        df = leaguedashteamstats.LeagueDashTeamStats(season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        rows = [format_team_stats(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        return jsonify({'season': SEASON, 'count': len(rows), 'teams': rows})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'season': SEASON, 'count': 0, 'teams': [], 'error': 'official nba stats unavailable'}), 200


@app.route('/api/player/<int:player_id>')
def api_player(player_id):
    try:
        info_df = commonplayerinfo.CommonPlayerInfo(player_id=player_id).get_data_frames()[0]
        info = info_df.iloc[0].to_dict() if len(info_df) else {}
        log_df = playergamelog.PlayerGameLog(player_id=player_id, season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        logs = log_df.to_dict(orient='records')
        recent = logs[:10]
        return jsonify({
            'season': SEASON,
            'player': {
                'id': player_id,
                'name': info.get('DISPLAY_FIRST_LAST', ''),
                'team': info.get('TEAM_NAME', ''),
                'position': info.get('POSITION', ''),
                'age': info.get('AGE', ''),
                'height': info.get('HEIGHT', ''),
                'weight': info.get('WEIGHT', ''),
                'college': info.get('SCHOOL', ''),
                'experience': info.get('SEASON_EXP', '')
            },
            'recent_games': recent[:20],
            'season_avg': avg_stats(recent, ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'MIN'])
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': 'official nba stats unavailable', 'player': {'id': player_id}, 'recent_games': [], 'season_avg': {}}), 200


@app.route('/api/team/<int:team_id>')
def api_team(team_id):
    try:
        team = get_teams_cached().get(team_id, {})
        log_df = teamgamelog.TeamGameLog(team_id=team_id, season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        logs = log_df.to_dict(orient='records')
        recent = logs[:10]
        return jsonify({
            'season': SEASON,
            'team': {'id': team_id, 'name': team.get('full_name', team.get('name', ''))},
            'recent_games': recent[:20],
            'season_avg': avg_stats(recent, ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'MIN'])
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': 'official nba stats unavailable', 'team': {'id': team_id}, 'recent_games': [], 'season_avg': {}}), 200


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
