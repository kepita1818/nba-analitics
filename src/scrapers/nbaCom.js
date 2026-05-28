const axios = require('axios');
const cacheService = require('../services/cacheService');

const NBA_API_BASE = 'https://stats.nba.com/stats';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'en-US,en;q=0.9',
  'Origin': 'https://www.nba.com',
  'Referer': 'https://www.nba.com/'
};

class NbaComScraper {
  
  async getAllPlayers() {
    const cacheKey = 'nba_all_players';
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const url = `${NBA_API_BASE}/playerindex?LeagueID=00&Season=2024-25`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const players = response.data.resultSets[0].rowSet.map(row => ({
        id: row[0],
        name: row[2],
        team: row[7],
        teamId: row[6],
        position: row[8],
        height: row[10],
        weight: row[11],
        country: row[12],
        lastAffiliation: row[13],
        birthdate: row[14],
        draftYear: row[22],
        draftRound: row[23],
        draftNumber: row[24],
        fromYear: row[26],
        toYear: row[27]
      }));

      const result = {
        count: players.length,
        players,
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 1440);
      return result;
    } catch (error) {
      console.error('Error fetching NBA players:', error.message);
      return { error: error.message };
    }
  }

  async getSchedule(days = 7) {
    const today = new Date();
    const cacheKey = `nba_schedule_${today.toISOString().split('T')[0]}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const gameDate = today.toISOString().split('T')[0];
      
      const url = `${NBA_API_BASE}/scoreboardv2?DayOffset=0&LeagueID=00&gameDate=${gameDate}`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const games = response.data.resultSets[0].rowSet.map(row => ({
        gameId: row[2],
        gameDate: row[0],
        gameTime: row[1],
        status: row[4],
        homeTeam: {
          id: row[6],
          name: row[5],
          score: row[21] || 0,
          record: row[54] || ''
        },
        awayTeam: {
          id: row[7],
          name: row[4],
          score: row[20] || 0,
          record: row[53] || ''
        },
        arena: row[30],
        city: row[31],
        nationalTV: row[11] || ''
      }));

      const result = {
        date: gameDate,
        games,
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 30);
      return result;
    } catch (error) {
      console.error('Error fetching NBA schedule:', error.message);
      return { error: error.message };
    }
  }

  async getPlayerStats(playerId, season = '2024-25') {
    const cacheKey = `nba_player_stats_${playerId}_${season}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const url = `${NBA_API_BASE}/playerdashboardbyyearoveryear?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=00&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=0&PaceAdjust=N&PerMode=PerGame&Period=0&PlayerID=${playerId}&PlusMinus=N&Rank=N&Season=${season}&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&Split=yoy&VsConference=&VsDivision=`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const stats = response.data.resultSets[1].rowSet[0];
      const headers = response.data.resultSets[1].headers;
      
      const playerStats = {};
      headers.forEach((header, index) => {
        playerStats[header] = stats[index];
      });

      const result = {
        playerId,
        season,
        stats: playerStats,
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 120);
      return result;
    } catch (error) {
      console.error(`Error fetching player stats:`, error.message);
      return { error: error.message };
    }
  }

  async getLeagueLeaders(category = 'PTS', season = '2024-25') {
    const cacheKey = `nba_leaders_${category}_${season}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const url = `${NBA_API_BASE}/leagueleaders?LeagueID=00&PerMode=PerGame&Scope=S&Season=${season}&SeasonType=Regular+Season&StatCategory=${category}`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const leaders = response.data.resultSet.rowSet.map((row, index) => ({
        rank: index + 1,
        playerId: row[0],
        name: row[2],
        team: row[3],
        games: row[4],
        minutes: row[5],
        fgm: row[6],
        fga: row[7],
        fgPct: row[8],
        threePm: row[9],
        threePa: row[10],
        threePct: row[11],
        ftm: row[12],
        fta: row[13],
        ftPct: row[14],
        oreb: row[15],
        dreb: row[16],
        reb: row[17],
        ast: row[18],
        stl: row[19],
        blk: row[20],
        tov: row[21],
        pf: row[22],
        pts: row[23],
        eff: row[24]
      }));

      const result = {
        category,
        season,
        leaders: leaders.slice(0, 50),
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 180);
      return result;
    } catch (error) {
      console.error(`Error fetching league leaders:`, error.message);
      return { error: error.message };
    }
  }
}

module.exports = new NbaComScraper();
