from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, teamgamelog, leaguedashplayerstats, leaguedashteamstats, commonplayerinfo
from collections import defaultdict
from datetime import datetime
import os
import math
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

SEASON = '2025-26'
SEASON_TYPE = 'Regular Season'
TEAM_BY_ID = {}
PLAYER_BY_ID = {}


def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs', exist_ok=True)
    handler = RotatingFileHandler('logs/app.log', maxBytes=10_000_000, backupCount=5)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


setup_logging()


def get_players_cached():
    global PLAYER_BY_ID
    if not PLAYER_BY_ID:
        try:
            PLAYER_BY_ID = {p['id']: p for p in players.get_active_players()}
        except Exception:
            PLAYER_BY_ID = {}
    return PLAYER_BY_ID


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
        if v is None or v == '':
            return default
        return float(v)
    except Exception:
        return default


def safe_int(v, default=0):
    try:
        if v is None or v == '':
            return default
        return int(float(v))
    except Exception:
        return default


def parse_matchup(matchup):
    if not matchup:
        return '', '', ''
    parts = matchup.split(' ')
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    return '', '', ''


def avg_stats(rows, keys):
    if not rows:
        return {k: 0 for k in keys}
    totals = defaultdict(float)
    n = 0
    for row in rows:
        n += 1
        for k in keys:
            totals[k] += safe_float(row.get(k), 0)
    return {k: round(totals[k] / max(n, 1), 2) for k in keys}


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
        'wins': safe_int(row.get('W')),
        'losses': safe_int(row.get('L')),
        'pts': safe_float(row.get('PTS')),
        'reb': safe_float(row.get('REB')),
        'ast': safe_float(row.get('AST')),
        'stl': safe_float(row.get('STL')),
        'blk': safe_float(row.get('BLK')),
        'tov': safe_float(row.get('TOV'))
    }


@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'season': SEASON, 'seasonType': SEASON_TYPE})


@app.route('/api/players')
def api_players():
    try:
        app.logger.info('Request: /api/players')
        df = leaguedashplayerstats.LeagueDashPlayerStats(season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        rows = [format_player_stats(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        return jsonify({'season': SEASON, 'count': len(rows), 'players': rows[:200]})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/teams')
def api_teams():
    try:
        app.logger.info('Request: /api/teams')
        df = leaguedashteamstats.LeagueDashTeamStats(season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        rows = [format_team_stats(r) for _, r in df.iterrows()]
        rows.sort(key=lambda x: x['pts'], reverse=True)
        return jsonify({'season': SEASON, 'count': len(rows), 'teams': rows})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/player/<int:player_id>')
def player_detail(player_id):
    try:
        app.logger.info(f'Request: /api/player/{player_id}')
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id).get_normalized_dict().get('CommonPlayerInfo', [])
        info = player_info[0] if player_info else {}
        logs_df = playergamelog.PlayerGameLog(player_id=player_id, season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        logs = logs_df.to_dict(orient='records')
        recent = logs[:10]
        avg = avg_stats(recent, ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'MIN'])
        return jsonify({
            'season': SEASON,
            'player': {
                'id': player_id,
                'name': info.get('DISPLAY_FIRST_LAST', ''),
                'team': info.get('TEAM_NAME', ''),
                'position': info.get('POSITION', ''),
                'experience': info.get('SEASON_EXP', ''),
                'age': info.get('AGE', ''),
                'height': info.get('HEIGHT', ''),
                'weight': info.get('WEIGHT', ''),
                'college': info.get('SCHOOL', '')
            },
            'recent_games': recent[:20],
            'season_avg': avg
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/team/<int:team_id>')
def team_detail(team_id):
    try:
        app.logger.info(f'Request: /api/team/{team_id}')
        team = get_teams_cached().get(team_id, {})
        logs_df = teamgamelog.TeamGameLog(team_id=team_id, season=SEASON, season_type_all_star=SEASON_TYPE).get_data_frames()[0]
        logs = logs_df.to_dict(orient='records')
        recent = logs[:10]
        avg = avg_stats(recent, ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'MIN'])
        return jsonify({
            'season': SEASON,
            'team': {
                'id': team_id,
                'name': team.get('full_name', team.get('name', ''))
            },
            'recent_games': recent[:20],
            'season_avg': avg
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'nba-stats-platform.html')


@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(429)
def too_many_requests(e):
    return jsonify({'error': 'Too many requests'}), 429


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
