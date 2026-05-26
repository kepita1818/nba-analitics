from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, teamgamelog, leaguedashplayerstats, leaguedashteamstats, commonplayerinfo
from collections import defaultdict
from datetime import datetime
import os
import math

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

SEASON = '2024-25'
SEASON_TYPE = 'Regular Season'

PLAYERS = players.get_active_players()
TEAMS = teams.get_teams()
TEAM_BY_ID = {t['id']: t for t in TEAMS}
PLAYER_BY_ID = {p['id']: p for p in PLAYERS}


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
        return {'is_home': None, 'opponent_abbr': ''}
    return {
        'is_home': 'vs.' in matchup,
        'opponent_abbr': matchup.split()[-1]
    }


def split_game_logs(rows):
    home = []
    away = []
    wins = []
    losses = []
    for row in rows:
        m = parse_matchup(row.get('MATCHUP', ''))
        wl = row.get('WL', '')
        if m['is_home']:
            home.append(row)
        else:
            away.append(row)
        if wl == 'W':
            wins.append(row)
        elif wl == 'L':
            losses.append(row)
    return home, away, wins, losses


def avg_stats(rows, fields):
    if not rows:
        return {f: 0 for f in fields}
    result = {}
    for f in fields:
        result[f] = round(sum(safe_float(r.get(f, 0)) for r in rows) / len(rows), 2)
    return result


def simplify_player_row(row):
    return {
        'player_id': safe_int(row.get('PLAYER_ID')),
        'player_name': row.get('PLAYER_NAME', ''),
        'team_abbreviation': row.get('TEAM_ABBREVIATION', ''),
        'age': safe_float(row.get('AGE')),
        'gp': safe_int(row.get('GP')),
        'w': safe_int(row.get('W')),
        'l': safe_int(row.get('L')),
        'min': safe_float(row.get('MIN')),
        'pts': safe_float(row.get('PTS')),
        'reb': safe_float(row.get('REB')),
        'ast': safe_float(row.get('AST')),
        'stl': safe_float(row.get('STL')),
        'blk': safe_float(row.get('BLK')),
        'tov': safe_float(row.get('TOV')),
        'fg_pct': round(safe_float(row.get('FG_PCT')) * 100, 1),
        'fg3_pct': round(safe_float(row.get('FG3_PCT')) * 100, 1),
        'ft_pct': round(safe_float(row.get('FT_PCT')) * 100, 1),
        'plus_minus': safe_float(row.get('PLUS_MINUS')),
        'pra': round(safe_float(row.get('PTS')) + safe_float(row.get('REB')) + safe_float(row.get('AST')), 1),
        'pr': round(safe_float(row.get('PTS')) + safe_float(row.get('REB')), 1),
        'pa': round(safe_float(row.get('PTS')) + safe_float(row.get('AST')), 1),
        'ra': round(safe_float(row.get('REB')) + safe_float(row.get('AST')), 1)
    }


def simplify_team_row(row):
    return {
        'team_id': safe_int(row.get('TEAM_ID')),
        'team_name': row.get('TEAM_NAME', ''),
        'abbreviation': row.get('TEAM_ABBREVIATION', ''),
        'gp': safe_int(row.get('GP')),
        'w': safe_int(row.get('W')),
        'l': safe_int(row.get('L')),
        'w_pct': round(safe_float(row.get('W_PCT')) * 100, 1),
        'min': safe_float(row.get('MIN')),
        'pts': safe_float(row.get('PTS')),
        'reb': safe_float(row.get('REB')),
        'ast': safe_float(row.get('AST')),
        'stl': safe_float(row.get('STL')),
        'blk': safe_float(row.get('BLK')),
        'tov': safe_float(row.get('TOV')),
        'fg_pct': round(safe_float(row.get('FG_PCT')) * 100, 1),
        'fg3_pct': round(safe_float(row.get('FG3_PCT')) * 100, 1),
        'ft_pct': round(safe_float(row.get('FT_PCT')) * 100, 1),
        'plus_minus': safe_float(row.get('PLUS_MINUS'))
    }


@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'season': SEASON, 'seasonType': SEASON_TYPE})


@app.route('/api/players')
def api_players():
    sort_by = request.args.get('sort', 'pts').lower()
    team = request.args.get('team', '').upper().strip()
    search = request.args.get('search', '').lower().strip()

    data = leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star=SEASON_TYPE,
        per_mode_detailed='PerGame'
    ).get_normalized_dict()['LeagueDashPlayerStats']

    rows = [simplify_player_row(r) for r in data]
    if team:
        rows = [r for r in rows if r['team_abbreviation'] == team]
    if search:
        rows = [r for r in rows if search in r['player_name'].lower()]

    rows.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    return jsonify({'season': SEASON, 'count': len(rows), 'players': rows[:200]})


@app.route('/api/teams')
def api_teams():
    sort_by = request.args.get('sort', 'w_pct').lower()
    search = request.args.get('search', '').lower().strip()

    data = leaguedashteamstats.LeagueDashTeamStats(
        season=SEASON,
        season_type_all_star=SEASON_TYPE,
        per_mode_detailed='PerGame'
    ).get_normalized_dict()['LeagueDashTeamStats']

    rows = [simplify_team_row(r) for r in data]
    if search:
        rows = [r for r in rows if search in r['team_name'].lower() or search in r['abbreviation'].lower()]

    rows.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    return jsonify({'season': SEASON, 'count': len(rows), 'teams': rows})


@app.route('/api/player/<int:player_id>')
def api_player_detail(player_id):
    logs = playergamelog.PlayerGameLog(player_id=player_id, season=SEASON, season_type_all_star=SEASON_TYPE).get_normalized_dict()['PlayerGameLog']
    info = commonplayerinfo.CommonPlayerInfo(player_id=player_id).get_normalized_dict()['CommonPlayerInfo'][0]

    game_logs = []
    for row in logs:
        m = parse_matchup(row.get('MATCHUP', ''))
        pts = safe_float(row.get('PTS'))
        reb = safe_float(row.get('REB'))
        ast = safe_float(row.get('AST'))
        game_logs.append({
            'game_id': row.get('Game_ID'),
            'game_date': row.get('GAME_DATE'),
            'matchup': row.get('MATCHUP'),
            'wl': row.get('WL'),
            'is_home': m['is_home'],
            'opponent_abbr': m['opponent_abbr'],
            'min': safe_float(row.get('MIN')),
            'pts': pts,
            'reb': reb,
            'ast': ast,
            'stl': safe_float(row.get('STL')),
            'blk': safe_float(row.get('BLK')),
            'tov': safe_float(row.get('TOV')),
            'fgm': safe_float(row.get('FGM')),
            'fga': safe_float(row.get('FGA')),
            'fg_pct': round(safe_float(row.get('FG_PCT')) * 100, 1),
            'fg3m': safe_float(row.get('FG3M')),
            'fg3a': safe_float(row.get('FG3A')),
            'fg3_pct': round(safe_float(row.get('FG3_PCT')) * 100, 1),
            'ftm': safe_float(row.get('FTM')),
            'fta': safe_float(row.get('FTA')),
            'ft_pct': round(safe_float(row.get('FT_PCT')) * 100, 1),
            'plus_minus': safe_float(row.get('PLUS_MINUS')),
            'pra': round(pts + reb + ast, 1)
        })

    home, away, wins, losses = split_game_logs(logs)
    fields = ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV']

    return jsonify({
        'season': SEASON,
        'profile': {
            'player_id': player_id,
            'name': info.get('DISPLAY_FIRST_LAST', ''),
            'first_name': info.get('FIRST_NAME', ''),
            'last_name': info.get('LAST_NAME', ''),
            'team_name': info.get('TEAM_NAME', ''),
            'team_abbreviation': info.get('TEAM_ABBREVIATION', ''),
            'jersey': info.get('JERSEY', ''),
            'position': info.get('POSITION', ''),
            'height': info.get('HEIGHT', ''),
            'weight': info.get('WEIGHT', ''),
            'country': info.get('COUNTRY', ''),
            'school': info.get('SCHOOL', ''),
            'birthdate': info.get('BIRTHDATE', ''),
            'experience': info.get('SEASON_EXP', ''),
            'draft_year': info.get('DRAFT_YEAR', ''),
            'draft_number': info.get('DRAFT_NUMBER', '')
        },
        'summary': {
            'season_avg': avg_stats(logs, fields),
            'last5_avg': avg_stats(logs[:5], fields),
            'last10_avg': avg_stats(logs[:10], fields),
            'home_avg': avg_stats(home, fields),
            'away_avg': avg_stats(away, fields),
            'wins_avg': avg_stats(wins, fields),
            'losses_avg': avg_stats(losses, fields)
        },
        'games': game_logs
    })


@app.route('/api/team/<int:team_id>')
def api_team_detail(team_id):
    logs = teamgamelog.TeamGameLog(team_id=team_id, season=SEASON, season_type_all_star=SEASON_TYPE).get_normalized_dict()['TeamGameLog']
    team_meta = TEAM_BY_ID.get(team_id, {})

    games = []
    for row in logs:
        m = parse_matchup(row.get('MATCHUP', ''))
        games.append({
            'game_id': row.get('Game_ID'),
            'game_date': row.get('GAME_DATE'),
            'matchup': row.get('MATCHUP'),
            'wl': row.get('WL'),
            'is_home': m['is_home'],
            'opponent_abbr': m['opponent_abbr'],
            'min': safe_float(row.get('MIN')),
            'pts': safe_float(row.get('PTS')),
            'fgm': safe_float(row.get('FGM')),
            'fga': safe_float(row.get('FGA')),
            'fg_pct': round(safe_float(row.get('FG_PCT')) * 100, 1),
            'fg3m': safe_float(row.get('FG3M')),
            'fg3a': safe_float(row.get('FG3A')),
            'fg3_pct': round(safe_float(row.get('FG3_PCT')) * 100, 1),
            'ftm': safe_float(row.get('FTM')),
            'fta': safe_float(row.get('FTA')),
            'ft_pct': round(safe_float(row.get('FT_PCT')) * 100, 1),
            'oreb': safe_float(row.get('OREB')),
            'dreb': safe_float(row.get('DREB')),
            'reb': safe_float(row.get('REB')),
            'ast': safe_float(row.get('AST')),
            'stl': safe_float(row.get('STL')),
            'blk': safe_float(row.get('BLK')),
            'tov': safe_float(row.get('TOV')),
            'plus_minus': safe_float(row.get('PLUS_MINUS'))
        })

    home, away, wins, losses = split_game_logs(logs)
    fields = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV']

    roster_rows = leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star=SEASON_TYPE,
        per_mode_detailed='PerGame'
    ).get_normalized_dict()['LeagueDashPlayerStats']
    roster = [simplify_player_row(r) for r in roster_rows if safe_int(r.get('TEAM_ID')) == team_id]
    roster.sort(key=lambda x: x['pts'], reverse=True)

    return jsonify({
        'season': SEASON,
        'team': {
            'team_id': team_id,
            'name': team_meta.get('full_name', ''),
            'city': team_meta.get('city', ''),
            'nickname': team_meta.get('nickname', ''),
            'abbreviation': team_meta.get('abbreviation', '')
        },
        'summary': {
            'season_avg': avg_stats(logs, fields),
            'last5_avg': avg_stats(logs[:5], fields),
            'last10_avg': avg_stats(logs[:10], fields),
            'home_avg': avg_stats(home, fields),
            'away_avg': avg_stats(away, fields),
            'wins_avg': avg_stats(wins, fields),
            'losses_avg': avg_stats(losses, fields)
        },
        'games': games,
        'roster': roster
    })


@app.route('/')
def root():
    return send_from_directory(app.static_folder, 'nba-stats-platform.html')


@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
